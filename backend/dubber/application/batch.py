"""자동 진행과 음성 대기열 유스케이스(_batch.json).
자동 진행: 드라이브 영상을 차례로 프로젝트로 만들고 자막을 읽어 문장 목록까지 만든다(검수 단계에서 멈춤).
  프로젝트 만들기 -> 자막 영역 자동 감지 -> 자막 찾기 -> AI 읽기 -> AI 문장 정리
음성 대기열: 화면에서 "음성 만들기"를 누른 영상만 넣는다(사람이 검수한 뒤). 음성 -> 내보내기 -> 드라이브 올리기.
음성 줄 VOICE_WORKERS개가 늘 돌며 대기열에서 하나씩 가져가므로 CPU를 다투지 않는다.
자동 진행은 그날 스케줄의 AI 도구로 하고, Claude 사용량이 그날의 한도를 넘으면 쉬어서 사람이 직접 쓸 몫을 남긴다."""
import hashlib
import os
import posixpath
import threading
import time
import traceback

from ..domain import project as rules
from ..domain.errors import UsageLimit

STATE = "_batch.json"
BATCH_MAX_FAILS = 3
BAD_READ = 0.5  # 자막 그림의 이 비율 이상을 못 읽으면 자막 영역이 틀린 것으로 본다
LIMIT_MIN, LIMIT_MARGIN = 60, 120  # 한도에 걸리면 최소 이만큼(초), 풀리는 시각보다 이만큼 더 기다린다


class BatchService:
    def __init__(self, store, projects, jobs, pipeline, library, importer, drive, schedule, ai, voice_workers=4):
        self.store = store        # ports.StateStore
        self.projects = projects  # application.projects.ProjectService
        self.jobs = jobs          # application.jobs.JobBoard
        self.pipeline = pipeline  # application.pipeline.PipelineService
        self.library = library    # application.library.LibraryService
        self.importer = importer  # 받은 영상을 두는 곳
        self.drive = drive        # ports.CloudDrive
        self.schedule = schedule  # application.schedule.ScheduleService
        self.ai = ai              # ports.AiRunner(한도에 걸렸을 때 풀리는 시각)
        self.voice_workers = voice_workers  # 음성 줄 수(tts 스레드 수와 곱해 코어 수쯤)
        self._batch = {"on": False, "queue": [], "items": {}, "voice": "M4", "wait_until": None, "wait_reason": None,
                       "voice_queue": []}  # 음성 대기열: [{"pid", "path"(자동 진행 영상이면), "params", "manual", "worker"}]
        self._threads = {}
        self._voice_threads = {}
        self._voice_fails = {"n": 0}
        self._lock = threading.Lock()

    @property
    def items(self):
        """드라이브 경로 -> 자동 진행 상태."""
        return self._batch["items"]

    def _save(self):
        with self._lock:
            self.store.write(STATE, self._batch)

    # ---------- 단계 하나 ----------
    def _step(self, pid, kind, params):
        """단계를 하나 돌리고 끝날 때까지 기다린다. 이미 돌고 있으면(서버 재시작 뒤 이어 하기 등) 그것을 기다린다."""
        p, lock = self.projects.get(pid)
        try:
            self.pipeline.start_step(pid, p, lock, kind, dict(params, kind=kind))
        except RuntimeError:
            pass
        j = self.jobs.wait(pid)
        if j and j.error:
            if j.error.startswith(UsageLimit.PREFIX):
                raise UsageLimit((self.ai.usage().get("info") or {}).get("resetsAt"))
            raise RuntimeError(j.error)
        if j and j.cancelled:
            raise RuntimeError("작업을 중단했습니다")

    def _prep(self, path, st):
        """자막을 읽고 문장 목록을 만들 때까지. 상태를 보고 필요한 단계만 하므로 몇 번을 다시 해도 된다."""
        pid = self.projects.by_drive(path)
        if not pid:
            st["msg"] = "프로젝트를 만드는 중"
            root = self.library.root
            rel = path[len(root) + 1:] if path.startswith(root + "/") else posixpath.basename(path)
            size = next((f["size"] for f in self.library.files() if f["path"] == rel), -1)
            local = self.drive.download(path, self.importer.dir, size)  # 이미 받아 두었으면 바로 돌려준다
            p = self.projects.create(local, {"drive": {"path": path, "shared": False},
                                             "settings": dict(rules.DEFAULT_SETTINGS, voice=self._batch["voice"])})
            pid = p.id
        st["pid"] = pid
        for _ in range(6):
            p, lock = self.projects.get(pid)
            tool = self.schedule.day_tool()
            if p.settings.get("tool") != tool:  # 자동 진행은 그날 스케줄의 AI 도구로 한다
                with lock:
                    p.settings["tool"] = tool
                    self.projects.save(p)
            j = self.jobs.get(pid)
            if j and not j.done and j.kind in ("tts", "export"):
                # 음성이나 내보내기가 돌고 있으면(사람이 직접 시작한 것 등) 자막은 이미 다 읽은 것이다
                if self.projects.get(pid)[0].data["sentences"]:
                    return
            self.jobs.wait(pid)
            p, lock = self.projects.get(pid)
            caps, sents = p.data["captions"], p.data["sentences"]
            unread = p.unread_ratio()
            if not caps:
                st["msg"] = "자막을 찾고 읽는 중"
                # 자막 영역이 없거나 다시 찾을 때만 자동 감지한다(미리 손으로 맞춘 영역은 그대로 쓴다).
                # 자막 찾기 -> AI 읽기 -> 문장 정리까지 이어진다
                self._step(pid, "scan", {"auto_roi": bool(st.get("rescanned"))})
                st["read_tried"] = True
            elif unread >= BAD_READ and st.get("read_tried"):
                if st.get("rescanned"):
                    raise RuntimeError(f"자막 그림의 {unread:.0%}를 읽지 못했습니다. 자막 영역을 확인한 뒤 다시 하세요")
                st["rescanned"] = True  # 자막 영역이 틀렸을 수 있으니 자동 감지부터 한 번 다시 한다
                st["msg"] = "자막 영역을 다시 찾는 중"
                with lock:
                    p.data["captions"], p.data["sentences"] = [], []
                    self.projects.save(p)
            elif not sents or unread >= BAD_READ:  # 자막은 찾았지만 아직 안 읽었다
                st["msg"] = "자막을 읽는 중"
                self._step(pid, "read", {})
                st["read_tried"] = True
            else:
                if not any(s.get("tts") for s in sents) and p.settings.get("voice") != self._batch["voice"]:
                    with lock:
                        p.settings["voice"] = self._batch["voice"]
                        self.projects.save(p)
                return
        raise RuntimeError("자막 읽기를 여러 번 했지만 문장 목록을 만들지 못했습니다")

    # ---------- 음성 대기열 ----------
    def voice_enqueue(self, pid, params=None, manual=False, path=None):
        """음성 대기열에 넣는다. 직접 누른 것(manual)은 자동 진행이 넣은 것들 앞(직접 누른 것끼리는 누른 순서)에 둔다.
        - 이미 만드는 중이면 그대로 둔다.
        - 이미 기다리는 중이면 자리는 그대로 두고 설정만 바꾼다. 다만 자동 진행으로 기다리던 것을 직접 누르면 앞으로 옮긴다."""
        clean = {k: v for k, v in (params or {}).items() if k != "kind"}
        with self._lock:
            q = self._batch["voice_queue"]
            e = next((x for x in q if x["pid"] == pid), None)
            if e and e.get("worker"):
                return e
            if e and (not manual or e["manual"]):
                if manual:
                    e["params"] = clean
                e["path"] = e["path"] or path
            else:
                if e:
                    q.remove(e)
                else:
                    e = {"pid": pid, "path": None, "params": clean, "manual": False, "worker": None,
                         "queued": time.time()}
                if manual:
                    e["params"] = clean
                e["manual"] = e["manual"] or manual
                e["path"] = e["path"] or path
                if e["manual"]:
                    at = next((k for k, x in enumerate(q) if not x["manual"] and not x.get("worker")), len(q))
                    q.insert(at, e)
                else:
                    q.append(e)
        self._save()
        self.voice_kick()
        return e

    def voice_start(self, pid, body):
        """화면에서 누른 "음성 만들기": 바로 시작하지 않고 음성 대기열에 넣는다(직접 누른 것이 앞)."""
        p, _ = self.projects.get(pid)
        drive = (p.data.get("drive") or {}).get("path")
        self.voice_enqueue(pid, body, manual=True, path=drive if drive in self._batch["items"] else None)

    def voice_waiting(self, pid):
        """대기열에서 기다리는 중이면 앞에 몇 편이 있는지, 아니면 None."""
        with self._lock:
            waiting = [x["pid"] for x in self._batch["voice_queue"] if not x.get("worker")]
        return waiting.index(pid) if pid in waiting else None

    def voice_cancel(self, pid):
        """아직 시작하지 않은 음성을 대기열에서 뺀다."""
        with self._lock:
            e = next((x for x in self._batch["voice_queue"] if x["pid"] == pid and not x.get("worker")), None)
            if e:
                self._batch["voice_queue"].remove(e)
        if e:
            self._save()
            # 서버가 꺼지기 전에 하던 음성이라 '진행 중' 표시가 남아 있으면 지운다(다시 켤 때 대기열에 돌아오지 않게)
            j = self.jobs.get(pid)
            if not (j and not j.done):
                p, lock = self.projects.get(pid)
                if (p.data.get("running_step") or {}).get("kind") in ("tts", "export"):
                    with lock:
                        p.clear_running()
                        self.projects.save(p)
        return bool(e)

    def queued_status(self, pid):
        """대기열에서 기다리는 음성을 작업 상태처럼 보여 준다(화면은 진행 중으로 보고 '중단'으로 뺄 수 있다)."""
        n = self.voice_waiting(pid)
        if n is None:
            return None
        return {"kind": "tts", "progress": 0.0, "msg": f"음성 대기 중 (앞에 {n}편)" if n else "음성 대기 중 (다음 차례)",
                "error": None, "done": False, "cancelled": False, "result": None, "running": True, "resumed": False,
                "queued": True}

    def _voice_run(self, e, st):
        pid = e["pid"]
        p, _ = self.projects.get(pid)
        if st and not e["manual"] and p.data.get("last_export") and p.data.get("drive_export"):
            return  # 이미 끝난 영상
        self._step(pid, "tts", e["params"])  # 음성이 끝나면 내보내기와 드라이브 올리기가 이어진다
        if st:
            p, _ = self.projects.get(pid)
            if not p.data.get("last_export"):
                raise RuntimeError("내보낸 파일이 없습니다")
            if not p.data.get("drive_export"):
                raise RuntimeError("구글 드라이브에 올리지 못했습니다")

    def _voice_worker(self, name):
        """음성 줄 하나. 대기열 앞에서부터 하나씩 맡아 음성 -> 내보내기 -> 드라이브 올리기를 한다."""
        while True:
            with self._lock:
                e = next((x for x in self._batch["voice_queue"] if not x.get("worker")), None)
                if e:
                    e["worker"] = name
            if not e:
                time.sleep(3)
                continue
            st = self._batch["items"].get(e.get("path")) if e.get("path") else None
            if st:
                st.update(stage="voice", msg="음성을 만들고 내보내는 중", error=None, started=time.time())
            self._save()
            try:
                self._voice_run(e, st)
                if st:
                    st.update(stage="done", msg="")
                    self._voice_fails["n"] = 0
            except Exception as ex:  # noqa
                traceback.print_exc()
                if st:
                    st.update(stage="error", error=str(ex), msg="")
                    self._voice_fails["n"] += 1
                    if self._voice_fails["n"] >= BATCH_MAX_FAILS and self._batch["on"]:
                        self.stop(f"음성이 {BATCH_MAX_FAILS}편 연달아 실패해 멈췄습니다. 실패 이유를 확인한 뒤 다시 시작하세요")
            finally:
                with self._lock:
                    if e in self._batch["voice_queue"]:
                        self._batch["voice_queue"].remove(e)
                    if st:
                        st["finished"] = time.time()
                self._save()

    def voice_kick(self):
        for i in range(self.voice_workers):
            name = f"voice-{i}"
            t = self._voice_threads.get(name)
            if not (t and t.is_alive()):
                self._voice_threads[name] = threading.Thread(target=self._voice_worker, args=(name,), daemon=True)
                self._voice_threads[name].start()

    # ---------- 자동 진행 ----------
    def _lane(self):
        """준비 줄. 대기열 순서대로 자막을 읽고 문장을 만든 뒤 음성 대기열에 넣는다."""
        want, busy = "waiting", "prep"
        fails = 0
        while self._batch["on"]:
            with self._lock:
                items = [(p, self._batch["items"][p]) for p in self._batch["queue"]]
                cur = next(((p, st) for p, st in items if st["stage"] == busy), None) \
                    or next(((p, st) for p, st in items if st["stage"] == want), None)
                if cur:
                    cur[1].update(stage=busy, error=None, started=time.time())
            if not cur:
                with self._lock:
                    self._batch["on"] = False  # 자막 읽을 영상을 다 했다(음성은 사람이 검수하고 직접 시작한다)
                self._save()
                return
            path, st = cur
            self._save()
            pause = self.schedule.usage_pause()
            if pause:
                until, why = pause
                st.update(stage=want, msg="")
                self._batch.update(wait_until=until, wait_reason=why)
                self._save()
                while self._batch["on"] and time.time() < until:
                    time.sleep(max(0.5, min(60, until - time.time())))
                    pause = self.schedule.usage_pause()  # 스케줄을 바꾸거나 날이 바뀌면 바로 반영한다
                    if not pause:
                        break
                    until, why = pause
                    self._batch.update(wait_until=until, wait_reason=why)
                self._batch.update(wait_until=None, wait_reason=None)
                continue
            tool = self.schedule.day_tool()
            try:
                self._prep(path, st)
                st.update(stage="ready", msg="")  # 검수 대기: 음성은 화면에서 직접 "음성 만들기"를 눌러 시작한다
                fails = 0
            except UsageLimit as e:
                # 풀리는 시각을 모르면 30분, 이미 지난 시각이면(오래된 정보) 잠깐 기다렸다가 다시 해 본다
                until = max(e.resets_at or time.time() + 1800, time.time() + LIMIT_MIN) + LIMIT_MARGIN
                name = "Codex" if tool == "codex" else "Claude"
                st.update(stage=want, msg=f"{name} 사용량 한도: {time.strftime('%m월 %d일 %H:%M', time.localtime(until))}"
                                          "에 이어서 합니다")
                self._batch.update(wait_until=until, wait_reason=f"{name} 사용량 한도에 걸려")
                self._save()
                # 기다리는 동안 스케줄에서 그날 도구가 바뀌면(날이 바뀌거나 직접 바꿈) 바로 새 도구로 이어 간다
                while self._batch["on"] and time.time() < until and self.schedule.day_tool() == tool:
                    time.sleep(max(0.5, min(30, until - time.time())))
                self._batch.update(wait_until=None, wait_reason=None)
                continue
            except Exception as e:  # noqa
                traceback.print_exc()
                st.update(stage="error", error=str(e), msg="")
                fails += 1
                if fails >= BATCH_MAX_FAILS:  # 모든 영상에 걸리는 문제(드라이브 연결 등)면 줄줄이 실패로 넘기지 않고 멈춘다
                    st["finished"] = time.time()
                    self.stop(f"{BATCH_MAX_FAILS}편이 연달아 실패해 멈췄습니다. 실패 이유를 확인한 뒤 다시 시작하세요")
                    return
            st["finished"] = time.time()
            self._save()

    def kick(self):
        self.voice_kick()
        t = self._threads.get("prep")
        if self._batch["on"] and not (t and t.is_alive()):
            self._threads["prep"] = threading.Thread(target=self._lane, daemon=True)
            self._threads["prep"].start()

    def _same_video_key(self, path):
        """받아 둔 영상 파일의 크기와 앞부분 4MB 해시. 같으면 같은 영상이 이름만 다르게 올라간 것."""
        f = os.path.join(self.importer.dir, posixpath.basename(path))
        if not os.path.isfile(f):
            return None
        with open(f, "rb") as fh:
            head = fh.read(4 << 20)
        return os.path.getsize(f), hashlib.md5(head).hexdigest()

    def _mark_duplicates(self):
        """대기 중인 영상 가운데 앞 영상과 같은 파일은 건너뛴다(같은 설교를 두 번 만들지 않는다)."""
        first = {}
        for p in self._batch["queue"]:
            st = self._batch["items"][p]
            key = self._same_video_key(p)
            if key is None:
                continue
            if key in first and st["stage"] == "waiting":
                st.update(stage="skipped", msg="", error=None,
                          same_as=os.path.splitext(posixpath.basename(first[key]))[0])
            else:
                first.setdefault(key, p)

    def start(self, voice=None):
        """아직 끝나지 않은 목록 영상을 모두 대기열에 넣고 시작한다(번호순). 이미 넣은 영상의 진행 상태는 그대로 둔다."""
        lib = self.library.view(force=True)
        for _ in range(180):  # 서버가 막 켜져 드라이브 목록을 읽는 중이면 다 읽을 때까지 기다린다(바쁠 때는 1분 넘게 걸린다)
            if not lib["loading"] and not self.library.busy:
                break
            time.sleep(1)
            lib = self.library.view()
        if not lib["items"]:
            raise RuntimeError("구글 드라이브 목록을 읽지 못했습니다: " + str(lib.get("error") or "영상이 없습니다"))
        with self._lock:
            if voice:
                self._batch["voice"] = voice
            for it in lib["items"]:
                p = it["project"]
                if (p and p["exported"]) or (not p and it["drive_done"]):
                    continue
                if it["path"] not in self._batch["items"]:
                    self._batch["queue"].append(it["path"])
                    self._batch["items"][it["path"]] = {"stage": "waiting", "msg": "", "error": None}
                elif self._batch["items"][it["path"]]["stage"] == "error":
                    self._batch["items"][it["path"]].update(stage="waiting", error=None, rescanned=False,
                                                            read_tried=False)
            self._batch["on"] = True
            self._batch["stopped_reason"] = None
        self._mark_duplicates()
        self._save()
        self.kick()

    def stop(self, reason=None):
        """새 영상은 더 시작하지 않는다. 지금 하던 단계는 끝까지 한다. (예전에 자동으로 넣은 음성이 남아 있으면 뺀다)"""
        with self._lock:
            self._batch["on"] = False
            self._batch["stopped_reason"] = reason
            self._batch["voice_queue"] = [x for x in self._batch["voice_queue"] if x["manual"] or x.get("worker")]
        self._save()

    def status(self):
        items = [(p, self._batch["items"][p]) for p in self._batch["queue"]]
        count = {}
        for _, st in items:
            count[st["stage"]] = count.get(st["stage"], 0) + 1
        name = lambda p: os.path.splitext(posixpath.basename(p))[0]  # noqa
        vq = list(self._batch["voice_queue"])
        cur = {"prep": next(({"name": name(p), "msg": st.get("msg")} for p, st in items if st["stage"] == "prep"), None),
               "voice": [{"name": x["pid"], "msg": "음성을 만들고 내보내는 중" + (" (직접 넣음)" if x["manual"] else "")}
                         for x in vq if x.get("worker")]}
        return {"on": self._batch["on"], "voice": self._batch["voice"], "count": count, "total": len(items),
                "current": cur,
                "voice_waiting": sum(1 for x in vq if not x.get("worker")),
                "voice_manual": sum(1 for x in vq if not x.get("worker") and x["manual"]),
                "stopped_reason": self._batch.get("stopped_reason"),
                "wait_until": self._batch["wait_until"], "wait_reason": self._batch.get("wait_reason"),
                "errors": [{"name": name(p), "path": p, "error": st["error"]} for p, st in items if st["stage"] == "error"],
                "skipped": [{"name": name(p), "same_as": st.get("same_as")} for p, st in items if st["stage"] == "skipped"]}

    def resume(self, voice=()):
        """서버가 켜질 때 대기열을 불러와 이어 간다. voice: 꺼지기 전에 하던 음성 [(프로젝트, 설정, 드라이브 경로)]."""
        saved = self.store.read(STATE)
        if saved:
            self._batch.update(saved)
            self._batch.update(wait_until=None, wait_reason=None)
            self._batch.setdefault("voice_queue", [])
            for x in self._batch["voice_queue"]:
                x["worker"] = None  # 서버가 새로 켜지면 음성 줄이 다시 나눠 맡는다(하던 음성은 아래에서 이어 간다)
            for st in self._batch["items"].values():
                st.pop("worker", None)
        # 음성은 직접 요청한 것만 만든다: 예전에 자동 진행이 넣고 아직 시작하지 않은 음성은 뺀다
        self._batch["voice_queue"] = [x for x in self._batch["voice_queue"] if x["manual"]]
        if self._batch["on"]:
            print("자동 진행 대기열을 이어 갑니다:", self.status()["count"], "음성 대기", self.status()["voice_waiting"],
                  flush=True)
        self.kick()
        for pid, params, path in voice:  # 대기열을 불러온 뒤에 넣는다. 하던 음성은 직접 요청했던 것이다
            self.voice_enqueue(pid, params, manual=True, path=path if path in self._batch["items"] else None)
