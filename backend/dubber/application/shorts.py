"""쇼츠 유스케이스: AI로 후보 고르기(suggest)와 영상 만들기(render)를 한 줄에서 하나씩 한다.
상태는 프로젝트의 shorts.json에 두고, 서버가 꺼졌다 켜지면 기다리던 것과 하던 것을 처음부터 다시 한다.
내보내기가 끝나면(설정이 켜져 있으면) 후보 고르기를 자동으로 넣는다. 자동으로 넣은 후보 고르기는 자동 진행처럼
Claude 사용량에 여유가 있을 때만 한다. 유튜브는 화면에서 누른 쇼츠만 유튜브 대기열(전체 영상 뒤)에 넣는다."""
import json
import os
import posixpath
import threading
import time
import traceback

from ..domain import library, outputs, tidy
from ..domain import shorts as rules
from ..domain.errors import NotFound, UsageLimit
from ..domain.youtube import short_key
from . import files
from .reading import TIDY_TIMEOUT

SETTINGS = "_shorts.json"  # 쇼츠 설정(내보내기 뒤 자동으로 후보 고르기)
N = 3  # 한 번에 고르는 후보 수

SUGGEST_PROMPT = """다음은 한국어로 더빙한 설교 한 편의 문장 목록입니다. n은 문장 번호, t는 시작 시각(초), d는 길이(초)입니다.
이 설교에서 유튜브 쇼츠로 만들 구간을 {n}개 고르세요.

조건:
- 이어진 문장들로 된 구간이고, 길이(첫 문장의 t부터 마지막 문장의 t+d까지)는 {lo}~{hi}초입니다. 40~60초가 가장 좋습니다.
- 앞뒤 설명 없이 이 구간만 봐도 이해되고, 메시지가 하나로 분명하며, 마지막 문장에서 깔끔하게 끝나야 합니다.
- 첫 문장이 보는 사람의 관심을 바로 끄는 곳이면 더 좋습니다.
- 성경 구절을 읽기만 하는 부분, 인사, 광고, 찬양, "몇 장을 보세요" 같은 안내는 피하세요.
- 구간끼리 겹치지 않게 하세요.{exclude}

구간마다:
- title: 화면 위에 크게 띄울 제목 두 줄. 줄마다 띄어쓰기를 포함해 12자 이내로, 구간의 핵심 메시지를 짧고 강하게.
- emph: 강조할 구절. 문장 번호를 키로, 그 문장에 있는 글자를 띄어쓰기까지 그대로 옮긴 짧은 구절(2~15자) 목록. 구간 전체에서 3~6개.
- reason: 이 구간을 고른 이유 한 줄.

설명 없이 JSON 배열만 출력하세요:
[{{"start": 첫 문장 번호, "end": 마지막 문장 번호, "title": ["첫 줄", "둘째 줄"], "emph": {{"문장 번호": ["구절"]}}, "reason": "..."}}]

문장 목록:
"""


def _key(pid):
    return f"{pid}/{rules.STATE}"


class ShortsService:
    def __init__(self, projects, store, locks, ai, renderer, drive, pipeline):
        self.projects = projects  # application.projects.ProjectService
        self.store = store        # ports.StateStore
        self.locks = locks        # application.files.ProjectLocks
        self.ai = ai              # ports.AiRunner
        self.renderer = renderer  # ports.ShortsRenderer
        self.drive = drive        # ports.CloudDrive
        self.pipeline = pipeline  # 드라이브 결과 폴더
        self.youtube = None       # 유튜브 대기열(bootstrap이 끼운다)
        self.schedule = None      # 자동 작업이 쉬어야 하는지, 그날의 AI 도구(bootstrap이 끼운다)
        self._sh = {"auto": True}
        self._q = []     # [{"pid", "kind": "suggest" | "render", "id", "auto"}]
        self._live = {}  # (pid, 번호 또는 "suggest") -> {"progress", "msg"}: 하는 중인 일의 진행
        self._run = {"thread": None, "cancel": set()}
        self._lock = threading.Lock()

    # ---------- 상태 파일 ----------
    def load(self, pid):
        return self.store.read(_key(pid)) or rules.empty_state()

    def change(self, pid, fn):
        return files.change(self.store, self.locks(pid), _key(pid), rules.empty_state, fn)

    def _set_item(self, pid, sid, **kw):
        self.change(pid, lambda st: (rules.find(st, sid) or {}).update(**kw))

    def item(self, pid, sid):
        it = rules.find(self.load(pid), sid)
        if not it:
            raise NotFound("없는 쇼츠입니다")
        return it

    def out_path(self, p, item):
        """결과: "<영상 이름> 한국어 더빙/쇼츠/<영상 이름> 쇼츠 <번호>.mp4" (제목을 고쳐도 이름은 그대로)."""
        d = self.projects.workspace(p.id).ensure(outputs.out_name(p.name), "쇼츠")
        return os.path.join(d, outputs.short(p.name, item["id"]))

    def box(self, p):
        """원본의 검은 테두리를 뺀 영역. 한 번 찾으면 shorts.json에 둔다."""
        box = self.load(p.id).get("box")
        if not box:
            box = self.renderer.content_box(p.data["video"], p.data["info"])
            self.change(p.id, lambda s: s.update(box=box))
        return box

    def set_auto(self, on):
        self._sh["auto"] = bool(on)
        self.store.write(SETTINGS, self._sh)

    # ---------- 대기열 ----------
    def enqueue(self, pid, kind, sid=None, auto=False):
        with self._lock:
            e = next((x for x in self._q if x["pid"] == pid and x["kind"] == kind and x["id"] == sid), None)
            if e and not (e["auto"] and not auto):
                return
            if e:
                e["auto"] = False  # 자동으로 넣어 사용량을 기다리던 것을 직접 누르면 바로 한다
            else:
                self._q.append({"pid": pid, "kind": kind, "id": sid, "auto": auto})

        def mark(st):
            if kind == "suggest":
                st["suggest"] = {"status": "queued", "auto": auto, "error": None}
            elif rules.find(st, sid):
                rules.find(st, sid).update(status="queued", error=None)
        self.change(pid, mark)
        self._kick()

    def _kick(self):
        with self._lock:
            t = self._run["thread"]
            if t and t.is_alive():
                return
            self._run["thread"] = threading.Thread(target=self._worker, daemon=True)
            self._run["thread"].start()

    def _worker(self):
        while True:
            paused = bool(self.schedule.usage_pause())
            with self._lock:
                if not self._q:
                    self._run["thread"] = None  # 잠금 안에서 비워야 그사이 들어온 일을 _kick이 새 줄로 시작한다
                    return
                x = next((x for x in self._q if not (x["kind"] == "suggest" and x["auto"] and paused)), None)
            if not x:
                time.sleep(10)  # 자동 후보 고르기만 남았고 Claude 사용량이 넉넉하지 않다
                continue
            key = (x["pid"], x["id"] if x["kind"] == "render" else "suggest")
            try:
                (self._suggest if x["kind"] == "suggest" else self._render)(x)
            except Exception:  # noqa  각 일이 실패를 상태에 남긴다. 여기는 예상 못 한 오류만
                traceback.print_exc()
            finally:
                with self._lock:
                    if x in self._q:
                        self._q.remove(x)
                    self._run["cancel"].discard(key)
                    self._live.pop(key, None)

    def suggest(self, p, n=N, tool="claude", taken=()):
        """AI에게 쇼츠 구간 n개를 고르게 한다. taken: 이미 있는 구간 [(start, end)]. 반환: 항목 목록."""
        tl = rules.timeline(p)
        rows = [{"n": s["id"], "t": round(s["t"], 1), "d": round(s["d"], 1), "text": s["text"]} for s in tl
                if s["t"] is not None]
        if not rows:
            raise RuntimeError("음성이 있는 문장이 없습니다")
        taken = list(taken)
        exclude = ("\n- 이미 고른 구간과도 겹치지 않게 하세요: " + ", ".join(f"{s}~{e}번" for s, e in taken)) if taken else ""
        prompt = SUGGEST_PROMPT.format(n=n, lo=rules.MIN_LEN, hi=rules.MAX_LEN, exclude=exclude) + "\n".join(
            json.dumps(r, ensure_ascii=False) for r in rows)
        err = None
        for _ in range(2):
            try:
                arr = tidy.parse_json_array(self.ai.run(prompt, tool, timeout=TIDY_TIMEOUT))
            except UsageLimit:
                raise
            except Exception as e:  # noqa  형식이 틀리면 한 번 더 묻는다
                err = e
                continue
            got = [c for c in (rules.candidate(tl, a, taken) for a in arr if isinstance(a, dict)) if c]
            if got:
                return got[:n]
            err = RuntimeError("AI가 고른 구간이 조건에 맞지 않습니다")
        raise RuntimeError(f"쇼츠 후보를 고르지 못했습니다: {err}")

    def _suggest(self, x):
        pid = x["pid"]
        if not self.projects.exists(pid):
            return
        p, _ = self.projects.get(pid)
        self._live[(pid, "suggest")] = {"msg": "Claude가 쇼츠로 만들 구간을 고르는 중"}
        self.change(pid, lambda st: st["suggest"].update(status="running", error=None))
        try:
            taken = [(i["start"], i["end"]) for i in self.load(pid)["items"]]
            tool = self.schedule.day_tool() if x["auto"] else p.settings.get("tool", "claude")
            got = self.suggest(p, N, tool, taken)
        except Exception as e:  # noqa  사용량 한도도 여기서 실패로 남긴다(화면에서 다시 누른다)
            traceback.print_exc()
            msg = str(e)
            self.change(pid, lambda st: st["suggest"].update(status="error", error=msg))
            return

        def add(st):
            ids = []
            for c in got:
                c.update(id=st["next_id"], status="queued", created=time.time())
                st["next_id"] += 1
                st["items"].append(c)
                ids.append(c["id"])
            st["suggest"].update(status="done", error=None, t=time.time())
            return ids
        for sid in self.change(pid, add):
            self.enqueue(pid, "render", sid)

    def _drive_upload(self, p, f, cancel):
        """결과 폴더 아래 "쇼츠" 폴더에 올린다. 내보내기 때 올린 폴더가 있으면 그 폴더를 쓴다."""
        folder, shared = self.pipeline.export_folder(p)
        try:
            ok = self.drive.upload([f], posixpath.join(folder, "쇼츠"), shared, None, cancel)
        except RuntimeError:
            if not shared:
                raise
            folder, shared = posixpath.basename(folder), False  # 공유 폴더에 쓸 수 없으면 내 드라이브에
            ok = self.drive.upload([f], posixpath.join(folder, "쇼츠"), False, None, cancel)
        return {"folder": posixpath.join(folder, "쇼츠"), "shared": shared} if ok else None

    def _render(self, x):
        pid, sid = x["pid"], x["id"]
        it = rules.find(self.load(pid), sid) if self.projects.exists(pid) else None
        if not it:
            return
        p, _ = self.projects.get(pid)
        key = (pid, sid)
        live = self._live[key] = {"progress": 0.0, "msg": "쇼츠를 만드는 중"}
        cancel = lambda: key in self._run["cancel"]  # noqa
        drive = bool(p.data.get("drive"))
        self._set_item(pid, sid, status="rendering", error=None)
        try:
            live["msg"] = "준비하는 중"
            box = self.box(p)
            sig = rules.signature(p, it)
            out = self.out_path(p, it)

            def prog(r):
                live.update(progress=r * (0.9 if drive else 1.0), msg=f"쇼츠를 만드는 중 ({int(r * 100)}%)")
            if not self.renderer.render(p, self.projects.workspace(pid), it, box, out, prog, cancel):
                self._set_item(pid, sid, status="done" if it.get("file") else "draft")
                return
            self._set_item(pid, sid, status="done", file=out, rendered=time.time(), rendered_sig=sig, error=None,
                           drive=None)
            if drive:
                live.update(progress=0.9, msg="구글 드라이브에 올리는 중")
                try:
                    self._set_item(pid, sid, drive=self._drive_upload(p, out, cancel))
                except Exception as e:  # noqa  영상은 만들었으니 드라이브 실패만 따로 남긴다
                    self._set_item(pid, sid, drive={"error": str(e)})
        except Exception as e:  # noqa
            traceback.print_exc()
            self._set_item(pid, sid, status="error", error=str(e))

    def after_export(self, p):
        """내보내기가 끝났을 때, 자동 설정이 켜져 있고 아직 후보를 고른 적이 없으면 후보 고르기를 넣는다."""
        st = self.load(p.id)
        if self._sh["auto"] and not st["items"] and st["suggest"].get("status") in (None, "idle"):
            self.enqueue(p.id, "suggest", auto=True)

    def resume(self):
        """서버가 켜질 때 기다리던 쇼츠 일과 하던 일을 다시 대기열에 넣는다."""
        self._sh.update(self.store.read(SETTINGS) or {})
        n = 0
        for it in self.projects.summaries():
            pid = it["dir"]
            if not self.store.exists(_key(pid)):
                continue
            st = self.load(pid)
            if st["suggest"].get("status") in ("queued", "running"):
                self.enqueue(pid, "suggest", auto=st["suggest"].get("auto", False))
                n += 1
            for x in st["items"]:
                if x.get("status") in ("queued", "rendering"):
                    self.enqueue(pid, "render", x["id"])
                    n += 1
        if n:
            print("쇼츠 대기열을 이어 갑니다:", n, "개", flush=True)

    # ---------- 화면에서 하는 일 ----------
    def new(self, pid, at):
        """직접 추가: 원본 영상의 at초에서 시작하는 문장부터 40초쯤을 새 쇼츠로 만든다(만들기 전 상태)."""
        p, _ = self.projects.get(pid)
        item = rules.manual_item(rules.timeline(p), at)

        def add(st):
            st["items"].append(dict({"id": st["next_id"]}, **item))
            st["next_id"] += 1
        self.change(pid, add)

    def update(self, pid, sid, body):
        """구간, 제목, 강조, 가로 위치를 고친다. 영상은 '다시 만들기'를 눌러야 바뀐다."""
        p, _ = self.projects.get(pid)
        tl = rules.timeline(p)

        def upd(st):
            it = rules.find(st, sid)
            if not it:
                raise ValueError("없는 쇼츠입니다")
            rules.edit_item(p, it, body, tl)
        self.change(pid, upd)

    def delete(self, pid, sid):
        key = (pid, sid)
        with self._lock:
            for x in list(self._q):
                if x["pid"] == pid and x["kind"] == "render" and x["id"] == sid:
                    if key in self._live:
                        self._run["cancel"].add(key)  # 만드는 중이면 멈춘다
                    else:
                        self._q.remove(x)

        def rm(st):
            it = rules.find(st, sid)
            if it:
                st["items"].remove(it)
            return it
        it = self.change(pid, rm)
        if it and it.get("file") and os.path.exists(it["file"]):
            os.remove(it["file"])

    def render(self, pid, sid):
        self.enqueue(pid, "render", sid)

    def suggest_now(self, pid):
        self.enqueue(pid, "suggest")

    def preview(self, pid, sid, t=None):
        p, _ = self.projects.get(pid)
        return self.renderer.preview(p, self.projects.workspace(pid), self.item(pid, sid), self.box(p), t)

    def video_file(self, pid, sid):
        return self.item(pid, sid).get("file") or ""

    def is_current(self, pid, sid):
        """만든 영상에 고친 내용이 모두 반영되었는지."""
        p, _ = self.projects.get(pid)
        it = self.item(pid, sid)
        return rules.signature(p, it) == it.get("rendered_sig")

    def ready_item(self, pid, sid):
        """유튜브에 올릴 쇼츠: (프로젝트, 항목). 영상이 없거나 고친 내용이 반영되지 않았으면 RuntimeError."""
        p, _ = self.projects.get(pid)
        it = rules.find(self.load(pid), sid)
        if not it or not it.get("file") or not os.path.isfile(it["file"]):
            raise RuntimeError("만든 쇼츠 영상이 없습니다")
        if rules.signature(p, it) != it.get("rendered_sig"):
            raise RuntimeError("고친 내용이 영상에 아직 반영되지 않았습니다. 다시 만든 뒤 올리세요")
        return p, it

    def upload(self, pid, sid):
        if not self.is_current(pid, sid):
            raise RuntimeError("고친 내용을 영상에 반영하려면 먼저 다시 만드세요")
        self.youtube.enqueue(short_key(pid, sid))

    def cancel_upload(self, pid, sid):
        self.youtube.cancel(short_key(pid, sid))

    # ---------- 화면에 보일 것 ----------
    def view(self, pid, lite=False):
        """쇼츠 화면에 보일 프로젝트 하나의 쇼츠 목록. lite가 아니면 문장 목록(구간 고치기용)도 넣는다."""
        p, _ = self.projects.get(pid)
        st = self.load(pid)
        tl = rules.timeline(p)
        with self._lock:
            order = [(x["pid"], x["kind"], x["id"]) for x in self._q]
        items = []
        for it in st["items"]:
            x = dict(it, **rules.info(p, it, tl))
            x["has_file"] = bool(it.get("file")) and os.path.isfile(it["file"])
            x["dirty"] = x["has_file"] and rules.signature(p, it, tl) != it.get("rendered_sig")
            x.update(self._live.get((pid, it["id"])) or {})
            if (pid, "render", it["id"]) in order:
                x["ahead"] = order.index((pid, "render", it["id"]))
            x["youtube"] = self.youtube.items.get(short_key(pid, it["id"]))
            items.append(x)
        sug = dict(st["suggest"], **(self._live.get((pid, "suggest")) or {}))
        if sug.get("status") == "queued":
            if (pid, "suggest", None) in order:
                sug["ahead"] = order.index((pid, "suggest", None))
            if sug.get("auto") and self.schedule.usage_pause():
                sug["msg"] = "Claude 사용량에 여유가 생기면 고릅니다"
        out = {"id": pid, "name": p.name, "items": items, "suggest": sug, "auto": self._sh["auto"],
               "drive": bool(p.data.get("drive"))}
        if not lite:
            out["sentences"] = [{"id": s["id"], "text": s["text"], "t": s["t"], "d": s["d"]} for s in tl]
        return out

    def summary(self):
        """쇼츠를 만들 수 있는 프로젝트(문장 목록이 있는 것)와 쇼츠가 있는 프로젝트. done은 지금 설정대로 만든
        쇼츠 수, stale은 영상은 있지만 고친 내용이 반영되지 않아 다시 만들어야 하는 수."""
        with self._lock:
            busy = {x["pid"] for x in self._q}
        out = []
        for it in self.projects.summaries():
            pid = it["dir"]
            has = self.store.exists(_key(pid))
            voice_done = bool(it["sentences"]) and it["tts"] == it["sentences"]
            if not (has or it["sentences"]):  # 원본 음성을 쓰므로 문장만 있으면 만들 수 있다
                continue
            st = self.load(pid)
            items, sug = st["items"], st["suggest"]
            made = [x for x in items if x.get("file")]
            done = self._current_count(pid, made) if made else 0
            out.append({"dir": pid, "name": it["name"], "voice_done": voice_done, "count": len(items),
                        "done": done, "stale": len(made) - done,
                        "uploaded": sum(1 for x in items if (self.youtube.items.get(short_key(pid, x["id"])) or {})
                                        .get("status") == "done"),
                        "busy": pid in busy, "suggest": sug.get("status"),
                        "error": sug.get("error") if sug.get("status") == "error" else None})
        out.sort(key=lambda x: library.natural(x["name"]))
        return {"items": out, "auto": self._sh["auto"]}

    def _current_count(self, pid, made):
        """만든 쇼츠 중 고친 내용(화면 모양이 바뀐 것 포함)이 모두 반영된 것의 수. 나머지는 다시 만들어야 한다."""
        p, _ = self.projects.get(pid)
        tl = rules.timeline(p)
        return sum(1 for x in made if rules.signature(p, x, tl) == x.get("rendered_sig"))
