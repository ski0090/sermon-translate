"""음성 영상(자면서 듣는 설교) 유스케이스: 화면은 제목과 이퀄라이저, 소리는 싱크 없이 이은 더빙 음성.
내보내기와 따로 한 줄에서 하나씩 만든다. 상태는 프로젝트의 sleep.json에 두고, 서버가 꺼졌다 켜지면 기다리던 것과
만들던 것을 처음부터 다시 한다."""
import os
import threading
import time
import traceback

from ..domain import library, outputs
from ..domain.youtube import SLEEP_KEY

SETTINGS = "_sleep.json"  # 설정(내보내기 뒤 자동으로 만들기)


def _key(pid):
    return f"{pid}/sleep.json"


class SleepService:
    def __init__(self, projects, store, locks, dub, renderer, drive, pipeline):
        self.projects = projects  # application.projects.ProjectService
        self.store = store        # ports.StateStore
        self.locks = locks        # application.files.ProjectLocks
        self.dub = dub            # ports.DubRenderer(싱크 없이 이은 음성)
        self.renderer = renderer  # ports.SleepRenderer
        self.drive = drive        # ports.CloudDrive
        self.pipeline = pipeline  # 드라이브 결과 폴더
        self.youtube = None       # 유튜브 대기열(bootstrap이 끼운다)
        self._sl = {"auto": True}
        self._q = []
        self._live = {}
        self._run = {"thread": None, "cancel": set()}
        self._lock = threading.Lock()

    def video_path(self, p):
        return os.path.join(self.projects.workspace(p.id).ensure(outputs.out_name(p.name)), outputs.sleep(p.name))

    def state(self, pid):
        return self.store.read(_key(pid)) or {}

    def _set(self, pid, **kw):
        with self.locks(pid):
            self.store.write(_key(pid), dict(self.state(pid), **kw))

    def set_auto(self, on):
        self._sl["auto"] = bool(on)
        self.store.write(SETTINGS, self._sl)

    # ---------- 대기열 ----------
    def enqueue(self, pid):
        p, _ = self.projects.get(pid)
        if not any(s.get("tts") for s in p.data["sentences"]):
            raise RuntimeError("음성을 먼저 만드세요")
        with self._lock:
            if pid in self._q:
                return
            self._q.append(pid)
        self._set(pid, status="queued", error=None)
        with self._lock:
            t = self._run["thread"]
            if t and t.is_alive():
                return
            self._run["thread"] = threading.Thread(target=self._worker, daemon=True)
            self._run["thread"].start()

    def cancel(self, pid):
        with self._lock:
            if pid not in self._q:
                return
            if pid in self._live:
                self._run["cancel"].add(pid)  # 만드는 중이면 멈춘다
                return
            self._q.remove(pid)
        self._set(pid, status="done" if os.path.isfile(self.video_path(self.projects.get(pid)[0])) else "idle")

    def _worker(self):
        while True:
            with self._lock:
                if not self._q:
                    self._run["thread"] = None
                    return
                pid = self._q[0]
            try:
                self._render(pid)
            except Exception:  # noqa
                traceback.print_exc()
            finally:
                with self._lock:
                    if pid in self._q:
                        self._q.remove(pid)
                    self._run["cancel"].discard(pid)
                    self._live.pop(pid, None)

    def _render(self, pid):
        if not self.projects.exists(pid):
            return
        p, _ = self.projects.get(pid)
        live = self._live[pid] = {"progress": 0.0, "msg": "음성을 잇는 중"}
        cancel = lambda: pid in self._run["cancel"]  # noqa
        drive = bool(p.data.get("drive"))
        self._set(pid, status="rendering", error=None)
        try:
            src, length = self.dub.natural_track(p, self.projects.workspace(pid))
            out = self.video_path(p)

            def prog(r):
                live.update(progress=r * (0.9 if drive else 1.0), msg=f"영상을 만드는 중 ({int(r * 100)}%)")
            if not self.renderer.render(src, out, p.name, progress=prog, cancel=cancel):
                self._set(pid, status="done" if os.path.isfile(out) else "idle")
                return
            self._set(pid, status="done", rendered=time.time(), length=round(length), drive=None)
            if drive:
                live.update(progress=0.9, msg="구글 드라이브에 올리는 중")
                folder, shared = self.pipeline.export_folder(p)
                try:
                    ok = self.drive.upload([out], folder, shared, None, cancel)
                    self._set(pid, drive={"folder": folder, "shared": shared} if ok else None)
                except Exception as e:  # noqa  영상은 만들었으니 드라이브 실패만 남긴다
                    self._set(pid, drive={"error": str(e)})
        except Exception as e:  # noqa
            traceback.print_exc()
            self._set(pid, status="error", error=str(e))

    def after_export(self, p):
        """내보내기가 끝났을 때 자동 설정이 켜져 있으면 대기열에 넣는다(내용이 바뀌었을 수 있으니 다시 만든다)."""
        if self._sl["auto"]:
            self.enqueue(p.id)

    def enqueue_missing(self):
        """아직 없는 영상 모두."""
        for x in self.summary()["items"]:
            if not x["has_file"] and x["status"] not in ("queued", "rendering"):
                self.enqueue(x["dir"])

    def resume(self):
        self._sl.update(self.store.read(SETTINGS) or {})
        n = 0
        for it in self.projects.summaries():
            if self.state(it["dir"]).get("status") in ("queued", "rendering"):
                self.enqueue(it["dir"])
                n += 1
        if n:
            print("음성 영상 대기열을 이어 갑니다:", n, "개", flush=True)

    # ---------- 화면 ----------
    def upload(self, pid):
        self.youtube.enqueue(SLEEP_KEY + pid)

    def cancel_upload(self, pid):
        self.youtube.cancel(SLEEP_KEY + pid)

    def video_file(self, pid):
        return self.video_path(self.projects.get(pid)[0])

    def summary(self):
        with self._lock:
            q = list(self._q)
        out = []
        for it in self.projects.summaries():
            if not it["tts"]:
                continue
            pid = it["dir"]
            st = self.state(pid)
            f = self.projects.workspace(pid).path(outputs.out_name(it["name"]), outputs.sleep(it["name"]))
            has = os.path.isfile(f)
            status = st.get("status") or ("done" if has else "idle")
            if status == "done" and not has:
                status = "idle"
            x = {"dir": pid, "name": it["name"], "status": status, "has_file": has,
                 "voice_done": it["tts"] == it["sentences"], "tts": it["tts"], "sentences": it["sentences"],
                 "rendered": st.get("rendered") or (os.path.getmtime(f) if has else None), "length": st.get("length"),
                 "size": os.path.getsize(f) if has else None, "drive": st.get("drive"), "error": st.get("error"),
                 "youtube": self.youtube.items.get(SLEEP_KEY + pid)}
            x.update(self._live.get(pid) or {})
            if pid in q:
                x["ahead"] = q.index(pid)
            out.append(x)
        out.sort(key=lambda x: library.natural(x["name"]))
        return {"items": out, "auto": self._sl["auto"], "yt": self.youtube.connected()}
