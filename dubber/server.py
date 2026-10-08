"""로컬 웹 서버: 브라우저 화면(static/index.html)과 JSON API. 표준 라이브러리만 쓴다.
실행: python server.py  ->  http://127.0.0.1:8765"""
import json
import mimetypes
import os
import posixpath
import re
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import ai
import export
import gdrive
import project as prj
import shorts
import tts
import youtube

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
DRIVE_DIR = os.path.join(prj.ROOT, "_drive")  # 구글 드라이브에서 받은 영상
DRIVE_JOB = "_drive"
IMPORT_MARK = os.path.join(DRIVE_DIR, "_import.json")  # 받는 중인 영상(서버가 꺼졌다 켜지면 다시 받는다)
YT_DIR = os.path.join(prj.ROOT, "_youtube")  # 유튜브에 올리려고 드라이브에서 받은 파일(올린 뒤 지운다)
YT_STATE = os.path.join(prj.ROOT, "_youtube.json")  # 영상별 업로드 상태와 대기열
YT_PLAYLIST = os.environ.get("DUBBER_YT_PLAYLIST", "조셉 프린스 더빙")
YT_PRIVACY = "private"
MAX_RESUME = 3  # 같은 단계를 연달아 다시 시작하는 최대 횟수(서버를 죽이는 작업이 무한히 반복되지 않게)
PORT = int(os.environ.get("DUBBER_PORT", "8765"))
# --lan이면 같은 네트워크의 다른 PC에서도 접속을 받는다
HOST = os.environ.get("DUBBER_HOST") or ("0.0.0.0" if "--lan" in sys.argv else "127.0.0.1")
LIBRARY = os.environ.get("DUBBER_LIBRARY", "JP").strip("/")  # 프로젝트 목록에 보여 줄 드라이브 폴더
LIBRARY_TTL = 60

_projects = {}
_locks = {}
_jobs = {}
_glock = threading.Lock()


def get_project(pid):
    with _glock:
        d = os.path.join(prj.ROOT, pid)
        path = os.path.join(d, "project.json")
        if not os.path.exists(path):
            raise FileNotFoundError(pid)
        job = _jobs.get(pid)
        cur = _projects.get(pid)
        # 다른 프로세스(명령줄 실행)가 파일을 바꿨으면 다시 읽는다. 작업 중일 때는 메모리의 것을 유지한다.
        external = cur is not None and os.path.getmtime(path) > cur.mtime + 0.5
        if cur is None or (external and not (job and not job.done)):
            _projects[pid] = prj.Project(d)
            _locks.setdefault(pid, threading.RLock())
        return _projects[pid], _locks[pid]


class Job:
    def __init__(self, kind):
        self.kind = kind
        self.progress = 0.0
        self.msg = ""
        self.error = None
        self.done = False
        self.cancelled = False
        self.result = None
        self.thread = None
        self.target = None
        self.resumed = False

    def status(self):
        return {"kind": self.kind, "progress": round(self.progress, 4), "msg": self.msg, "error": self.error,
                "done": self.done, "cancelled": self.cancelled, "result": self.result, "running": not self.done,
                "resumed": self.resumed}


def start_job(pid, kind, fn):
    with _glock:
        j = _jobs.get(pid)
        if j and not j.done:
            raise RuntimeError("이미 진행 중인 작업이 있습니다")
        job = Job(kind)
        _jobs[pid] = job

    def run():
        try:
            job.result = fn(job)
        except Exception as e:  # noqa
            job.error = str(e)
            traceback.print_exc()
        finally:
            job.done = True
            job.progress = 1.0 if not job.error else job.progress

    job.thread = threading.Thread(target=run, daemon=True)
    job.thread.start()
    return job


def frame_jpeg(video, t, roi=None):
    vf = "scale=720:-2"
    if roi:
        vf = (f"drawbox=x={roi['x']}:y={roi['y']}:w={roi['w']}:h={roi['h']}:color=red@0.9:t=2," + vf)
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                        "-vf", vf, "-f", "image2", "-c:v", "mjpeg", "-q:v", "4", "pipe:1"], capture_output=True)
    return r.stdout


def start_import(params, resumed=False):
    """드라이브 영상 받기를 시작한다. 받는 중이라는 표시를 파일로 남겨, 서버가 중간에 꺼지면 다시 켤 때 처음부터 받는다."""
    def fn(job):
        os.makedirs(DRIVE_DIR, exist_ok=True)
        _write_json(IMPORT_MARK, params)
        try:
            return drive_import_job(job, params)
        finally:
            if os.path.exists(IMPORT_MARK):
                os.remove(IMPORT_MARK)
    j = start_job(DRIVE_JOB, "drive", fn)
    j.target, j.resumed = params.get("path", "").strip("/"), resumed
    return j


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def drive_import_job(job, params):
    """구글 드라이브 영상을 받아 프로젝트를 만든다. 결과는 새 프로젝트 id."""
    def prog(done, total, speed):
        job.progress = 0.97 * done / total
        job.msg = f"구글 드라이브에서 내려받는 중 ({done / 2**20:,.0f} / {total / 2**20:,.0f}MB, {speed / 2**20:.1f}MB/s)"
    job.msg = "구글 드라이브에서 내려받는 중"
    local = gdrive.download(params["path"], DRIVE_DIR, int(params.get("size") or -1), bool(params.get("shared")),
                            progress=prog, cancel=lambda: job.cancelled)
    if local is None:
        return None
    job.msg = "프로젝트를 만드는 중"
    p = prj.Project.create(local, {"drive": {"path": params["path"].strip("/"), "shared": bool(params.get("shared"))}})
    return {"id": os.path.basename(p.dir)}


_lib = {"t": 0.0, "files": None, "error": None, "busy": False}


def _refresh_library():
    try:
        _lib["files"], _lib["error"] = gdrive.list_library(LIBRARY), None
    except Exception as e:  # noqa
        _lib["error"] = str(e)
    finally:
        _lib["t"], _lib["busy"] = time.time(), False


def _natural(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def library(force=False):
    """LIBRARY 폴더의 영상마다 진행 상태를 붙인다. 드라이브 목록은 LIBRARY_TTL초마다 뒤에서 새로 읽는다."""
    with _glock:
        start = (force or time.time() - _lib["t"] > LIBRARY_TTL) and not _lib["busy"]
        if start:
            _lib["busy"] = True
    if start:
        if _lib["files"] is None:
            _refresh_library()  # 처음 한 번은 기다린다
        else:
            threading.Thread(target=_refresh_library, daemon=True).start()
    files = _lib["files"] or []
    sub = {f["path"] for f in files if "/" in f["path"]}
    projects = prj.list_projects()
    for it in projects:
        j = _jobs.get(it["dir"])
        it["job"] = j.status() if j and not j.done else queued_status(it["dir"])
    by_path = {it["drive"]: it for it in projects if it.get("drive")}
    imp = _jobs.get(DRIVE_JOB)
    importing = imp.target if imp and not imp.done else None
    videos = channel_videos(force)
    items, used = [], set()
    for f in sorted((f for f in files if "/" not in f["path"]), key=lambda f: _natural(f["path"])):
        path = LIBRARY + "/" + f["path"]
        stem = os.path.splitext(f["path"])[0]
        dubbed = stem + " (한국어 더빙).mp4"
        it = {"name": stem, "path": path, "size": f["size"],
              "drive_done": f"{stem}{export.OUT_SUFFIX}/{dubbed}" in sub or f"{stem}/out/{dubbed}" in sub,
              "legacy": f"{stem}/project.json" in sub,
              "project": by_path.get(path),
              "importing": imp.status() if importing == path else None,
              "youtube": _yt["items"].get(path),
              "batch": (_batch["items"].get(path) or {}).get("stage"),
              "yt_existing": yt_existing(stem, videos)}
        it["yt_ready"] = it["drive_done"] or bool(it["project"] and it["project"]["exported"])
        if it["project"]:
            used.add(it["project"]["dir"])
        items.append(it)
    return {"root": LIBRARY, "items": items, "others": [p for p in projects if p["dir"] not in used],
            "error": _lib["error"], "loading": _lib["files"] is None}


# ---------- 유튜브 업로드 대기열 ----------
_yt = {"items": {}, "queue": [], "settings": {}}
# 영상 설명과 해시태그 기본값. 시작 화면의 "설명·해시태그"에서 바꾼다. {이름}은 영상 이름으로 바뀐다
YT_DEFAULTS = {"description": "조셉 프린스 목사님 설교 \"{이름}\"의 한국어 더빙입니다.",
               "hashtags": "#조셉프린스 #JosephPrince #한국어더빙 #설교 #은혜",
               # 쇼츠: {제목}은 쇼츠 제목 두 줄, {링크}는 유튜브에 올린 전체 영상(없으면 그 줄을 뺀다)
               "shorts_title": "{제목} | 조셉 프린스 설교 (한국어 더빙)",
               "shorts_description": "조셉 프린스 목사님 설교 \"{이름}\" 중에서 (한국어 더빙)\n전체 영상: {링크}"}


def yt_settings():
    return {k: _yt["settings"].get(k, v) for k, v in YT_DEFAULTS.items()}


def yt_meta(stem, desc=None, extra_tags=()):
    """올릴 영상의 설명과 태그. 해시태그는 설명 끝에 붙이고(앞의 3개가 제목 위에 보인다) 태그로도 넣는다."""
    s = yt_settings()
    tags = list(extra_tags) + [t.lstrip("#") for t in re.split(r"[\s,]+", s["hashtags"]) if t.strip("#")]
    desc = (s["description"] if desc is None else desc).replace("{이름}", stem).strip()
    if tags:
        desc += "\n\n" + " ".join("#" + t for t in tags)
    # 유튜브 제한: 설명 5,000바이트, 꺾쇠 괄호 금지, 태그 합계 500자
    desc = desc.replace("<", "(").replace(">", ")").encode("utf-8")[:5000].decode("utf-8", "ignore")
    out, n = [], 0
    for t in tags:
        n += len(t) + 1
        if n > 500:
            break
        out.append(t)
    return desc, out
_yt_lock = threading.RLock()
_yt_run = {"thread": None, "cancel": set()}


def _yt_save():
    with _yt_lock:
        tmp = YT_STATE + ".tmp"
        _write_json(tmp, _yt)
        os.replace(tmp, YT_STATE)


def yt_enqueue(path):
    with _yt_lock:
        st = _yt["items"].setdefault(path, {})
        if path in _yt["queue"]:
            return st
        if st.get("status") == "done":
            raise RuntimeError("이미 유튜브에 올린 영상입니다")
        _yt_run["cancel"].discard(path)
        st.update(status="queued", error=None, msg="올리기 대기 중", progress=0.0, resumed=False)
        q, at = _yt["queue"], len(_yt["queue"])
        if not path.startswith(SHORT_KEY):  # 전체 영상은 기다리는 쇼츠보다 먼저 올린다(올리는 중인 것은 그대로)
            busy = bool(_yt_run["thread"] and _yt_run["thread"].is_alive())
            at = next((k for k, x in enumerate(q) if x.startswith(SHORT_KEY) and not (k == 0 and busy)), len(q))
        q.insert(at, path)
        _yt_save()
    _yt_kick()
    return st


def yt_cancel(path):
    with _yt_lock:
        if path not in _yt["queue"]:
            return
        if _yt["queue"][0] == path and _yt_run["thread"] and _yt_run["thread"].is_alive():
            _yt_run["cancel"].add(path)  # 올리는 중이면 다음 조각에서 멈춘다
            _yt["items"][path]["msg"] = "중단하는 중"
        else:
            _yt["queue"].remove(path)
            _yt["items"][path].update(status="cancelled", msg="")
            _yt_save()


def _yt_kick():
    with _yt_lock:
        t = _yt_run["thread"]
        if t and t.is_alive():
            return
        _yt_run["thread"] = threading.Thread(target=_yt_worker, daemon=True)
        _yt_run["thread"].start()


def _quota_reset():
    """유튜브 할당량이 다시 채워지는 시각(태평양 시간 자정) 조금 뒤."""
    try:
        import datetime
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
        return (now + datetime.timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0).timestamp()
    except Exception:  # noqa  시간대 정보가 없으면 한 시간 뒤에 다시 해 본다
        return time.time() + 3600


def _yt_worker():
    """대기열 맨 앞 영상부터 하나씩 올린다. 할당량이 다 떨어지면 다음 날까지 기다렸다가 이어 간다."""
    while True:
        with _yt_lock:
            if not _yt["queue"]:
                return
            path = _yt["queue"][0]
            st = _yt["items"][path]
        cancelled = lambda: path in _yt_run["cancel"]  # noqa
        try:
            (_yt_upload_short if path.startswith(SHORT_KEY) else _yt_upload_one)(path, st, cancelled)
            st.update(status="cancelled" if cancelled() else "done", msg="", error=None)
        except youtube.QuotaExceeded:
            until = _quota_reset()
            st.update(status="queued", msg="오늘 유튜브 할당량을 다 썼습니다. "
                      + time.strftime("%m월 %d일 %H:%M", time.localtime(until)) + "에 이어서 올립니다")
            _yt_save()
            while time.time() < until and not cancelled():
                time.sleep(max(0.5, min(30, until - time.time())))
            if not cancelled():
                continue
            st.update(status="cancelled", msg="")
        except Exception as e:  # noqa
            traceback.print_exc()
            st.update(status="error", error=str(e), msg="")
        with _yt_lock:
            if _yt["queue"] and _yt["queue"][0] == path:
                _yt["queue"].pop(0)
            _yt_run["cancel"].discard(path)
            _yt_save()


_ytch = {"t": 0.0, "videos": None, "busy": False}
YT_CHANNEL_TTL = 900  # 채널 영상 목록을 다시 읽는 간격(초). 50개당 1단위라 15분이면 하루 100단위쯤


def _yt_norm(title):
    """제목 비교용: "한국어 더빙", 괄호, 띄어쓰기, 문장 부호를 뺀다."""
    t = re.sub(r"한국어\s*더빙", "", title)
    return re.sub(r"[\s()\[\]{}<>.,_\-–:;'\"“”‘’!?]", "", t)


def _refresh_channel():
    try:
        _ytch["videos"] = youtube.channel_uploads()
    except Exception as e:  # noqa  연결 안 됨, 네트워크 등: 다음에 다시 읽는다
        print("유튜브 채널 영상 목록을 읽지 못했습니다:", e, flush=True)
    finally:
        _ytch["t"], _ytch["busy"] = time.time(), False


def channel_videos(force=False):
    """채널에 이미 있는 영상(직접 올린 것 포함)을 이름으로 찾기 위한 목록. 뒤에서 가끔 새로 읽는다."""
    if not youtube.status()["connected"]:
        return []
    with _glock:
        start = (force or time.time() - _ytch["t"] > YT_CHANNEL_TTL) and not _ytch["busy"]
        if start:
            _ytch["busy"] = True
    if start:
        if force or _ytch["videos"] is None:
            _refresh_channel()
        else:
            threading.Thread(target=_refresh_channel, daemon=True).start()
    return _ytch["videos"] or []


def yt_existing(stem, videos):
    key = _yt_norm(stem)
    v = next((v for v in videos if _yt_norm(v["title"]) == key), None)
    return v and dict(v, url=f"https://www.youtube.com/watch?v={v['id']}")


def _yt_source(path, st, cancel, need_video):
    """올릴 더빙 영상과 자막. 이 PC의 결과물을 먼저 쓰고, 없으면 드라이브의 결과 폴더에서 받는다.
    영상이 이미 유튜브에 있으면(need_video=False) 자막만 찾는다. (영상 또는 None, 자막 또는 None, 다 올린 뒤 지울 파일들)"""
    for it in prj.list_projects():
        if it.get("drive") == path:
            p, _ = get_project(it["dir"])
            ex = [f for f in p.data.get("last_export") or [] if os.path.isfile(f)]
            video = next((f for f in ex if f.endswith(" (한국어 더빙).mp4")), None)
            if video or not need_video:
                return video, next((f for f in ex if f.endswith(".srt")), None), []
    if _lib["files"] is None:
        _refresh_library()
    sizes = {f["path"]: f["size"] for f in _lib["files"] or []}
    stem = os.path.splitext(posixpath.basename(path))[0]

    def prog(done, total, speed):
        st["msg"] = f"구글 드라이브에서 더빙 영상을 받는 중 ({done / 2**20:,.0f} / {total / 2**20:,.0f}MB)"
    for folder in (stem + export.OUT_SUFFIX, stem + "/out"):
        rel, srt_rel = f"{folder}/{stem} (한국어 더빙).mp4", f"{folder}/{stem}.srt"
        if rel not in sizes and srt_rel not in sizes:
            continue
        video = None
        if need_video:
            if rel not in sizes:
                continue
            video = gdrive.download(f"{LIBRARY}/{rel}", YT_DIR, sizes[rel], progress=prog, cancel=cancel)
        srt = gdrive.download(f"{LIBRARY}/{srt_rel}", YT_DIR, sizes[srt_rel], cancel=cancel) if srt_rel in sizes else None
        return video, srt, [f for f in (video, srt) if f]
    if need_video:
        raise RuntimeError("더빙된 영상(mp4)을 찾지 못했습니다")
    return None, None, []


def _yt_upload_one(path, st, cancel):
    """영상 올리기 -> 재생목록 -> 자막. 끝난 부분은 기록해 두어 다시 해도 건너뛴다(영상을 두 번 올리지 않게).
    채널에 같은 이름의 영상이 이미 있으면(직접 올린 것 포함) 올리지 않고 그 영상에 재생목록과 자막만 더한다."""
    def save(**kw):
        st.update(**kw)
        _yt_save()
    stem = os.path.splitext(posixpath.basename(path))[0]
    if not st.get("video_id"):
        save(status="uploading", msg="유튜브에 같은 영상이 있는지 확인하는 중")
        ex = yt_existing(stem, channel_videos(force=True))
        if ex:
            save(video_id=ex["id"], url=ex["url"], title=ex["title"], privacy=ex["privacy"], existing=True)
    need_video = not st.get("video_id")
    need_caps = st.get("captions") not in ("done", "none", "existing")
    temp = []
    try:
        video = srt = None
        if need_video or need_caps:
            save(status="uploading", msg="올릴 파일을 준비하는 중")
            video, srt, temp = _yt_source(path, st, cancel, need_video)
            if cancel():
                return
        if need_video:
            def prog(done, total):
                st["progress"] = done / total
                st["msg"] = f"유튜브에 올리는 중 ({done / 2**20:,.0f} / {total / 2**20:,.0f}MB)"
            save(msg="유튜브에 올리는 중", progress=0.0)
            desc, tags = yt_meta(stem)
            vid = youtube.upload_video(video, f"{stem} (한국어 더빙)", description=desc, tags=tags, privacy=YT_PRIVACY,
                                       progress=prog, cancel=cancel)
            if vid is None:
                return
            save(video_id=vid, url=f"https://www.youtube.com/watch?v={vid}", title=f"{stem} (한국어 더빙)",
                 privacy=YT_PRIVACY, uploaded=time.time(), progress=1.0)
            _ytch["t"] = 0  # 다음 목록 새로고침 때 채널 목록도 다시 읽는다
        if not st.get("playlist"):
            save(msg=f"재생목록 \"{YT_PLAYLIST}\"에 넣는 중")
            pl = youtube.playlist_id(YT_PLAYLIST)
            if not youtube.in_playlist(pl, st["video_id"]):
                youtube.add_to_playlist(pl, st["video_id"])
            save(playlist=YT_PLAYLIST)
        if need_caps:
            if srt and st.get("existing") and youtube.has_captions(st["video_id"]):
                save(captions="existing")  # 직접 올린 영상에 이미 한국어 자막이 있으면 덮지 않는다
            elif srt:
                save(msg="한국어 자막을 올리는 중")
                youtube.upload_captions(st["video_id"], srt)
                save(captions="done")
            else:
                save(captions="none")
    finally:
        for f in temp:
            if os.path.exists(f):
                os.remove(f)


# ---------- 쇼츠 ----------
# 쇼츠 대기열: Claude로 후보 고르기(suggest)와 영상 만들기(render)를 한 줄에서 하나씩 한다.
# 상태는 프로젝트의 shorts.json에 두고, 서버가 꺼졌다 켜지면 기다리던 것과 하던 것을 처음부터 다시 한다.
# 내보내기가 끝나면(설정이 켜져 있으면) 후보 고르기를 자동으로 넣는다. 자동으로 넣은 후보 고르기는 자동 진행처럼
# Claude 사용량에 여유가 있을 때만 한다. 유튜브는 화면에서 누른 쇼츠만 유튜브 대기열(전체 영상 뒤)에 넣는다.
SHORTS_STATE = os.path.join(prj.ROOT, "_shorts.json")  # 쇼츠 설정
SHORTS_N = 3
SHORT_KEY = "short:"  # 유튜브 대기열에서 쇼츠를 가리키는 이름: "short:<프로젝트>:<번호>"
_sh = {"auto": True}
_sh_q = []     # [{"pid", "kind": "suggest" | "render", "id", "auto"}]
_sh_live = {}  # (pid, 번호 또는 "suggest") -> {"progress", "msg"}: 하는 중인 일의 진행
_sh_run = {"thread": None, "cancel": set()}


def short_key(pid, sid):
    return f"{SHORT_KEY}{pid}:{sid}"


def _pdir(pid):
    return os.path.join(prj.ROOT, pid)


def shorts_enqueue(pid, kind, sid=None, auto=False):
    with _glock:
        e = next((x for x in _sh_q if x["pid"] == pid and x["kind"] == kind and x["id"] == sid), None)
        if e and not (e["auto"] and not auto):
            return
        if e:
            e["auto"] = False  # 자동으로 넣어 사용량을 기다리던 것을 직접 누르면 바로 한다
        else:
            _sh_q.append({"pid": pid, "kind": kind, "id": sid, "auto": auto})

    def mark(st):
        if kind == "suggest":
            st["suggest"] = {"status": "queued", "auto": auto, "error": None}
        elif shorts.find(st, sid):
            shorts.find(st, sid).update(status="queued", error=None)
    shorts.change(_pdir(pid), mark)
    _sh_kick()


def _sh_kick():
    with _glock:
        t = _sh_run["thread"]
        if t and t.is_alive():
            return
        _sh_run["thread"] = threading.Thread(target=_sh_worker, daemon=True)
        _sh_run["thread"].start()


def _sh_worker():
    while True:
        paused = bool(_usage_pause())
        with _glock:
            if not _sh_q:
                _sh_run["thread"] = None  # 잠금 안에서 비워야 그사이 들어온 일을 _sh_kick이 새 줄로 시작한다
                return
            x = next((x for x in _sh_q if not (x["kind"] == "suggest" and x["auto"] and paused)), None)
        if not x:
            time.sleep(10)  # 자동 후보 고르기만 남았고 Claude 사용량이 넉넉하지 않다
            continue
        key = (x["pid"], x["id"] if x["kind"] == "render" else "suggest")
        try:
            (_sh_suggest if x["kind"] == "suggest" else _sh_render)(x)
        except Exception:  # noqa  각 일이 실패를 상태에 남긴다. 여기는 예상 못 한 오류만
            traceback.print_exc()
        finally:
            with _glock:
                if x in _sh_q:
                    _sh_q.remove(x)
                _sh_run["cancel"].discard(key)
                _sh_live.pop(key, None)


def _set_item(d, sid, **kw):
    shorts.change(d, lambda st: (shorts.find(st, sid) or {}).update(**kw))


def _sh_suggest(x):
    pid, d = x["pid"], _pdir(x["pid"])
    if not os.path.isdir(d):
        return
    p, _ = get_project(pid)
    _sh_live[(pid, "suggest")] = {"msg": "Claude가 쇼츠로 만들 구간을 고르는 중"}
    shorts.change(d, lambda st: st["suggest"].update(status="running", error=None))
    try:
        taken = [(i["start"], i["end"]) for i in shorts.load(d)["items"]]
        got = shorts.suggest(p, SHORTS_N, p.data["settings"].get("tool", "claude"), taken)
    except Exception as e:  # noqa  사용량 한도도 여기서 실패로 남긴다(화면에서 다시 누른다)
        traceback.print_exc()
        msg = str(e)
        shorts.change(d, lambda st: st["suggest"].update(status="error", error=msg))
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
    for sid in shorts.change(d, add):
        shorts_enqueue(pid, "render", sid)


def _sh_drive_upload(p, f, cancel):
    """결과 폴더 아래 "쇼츠" 폴더에 올린다. 내보내기 때 올린 폴더가 있으면 그 폴더를 쓴다."""
    ex = p.data.get("drive_export") or {}
    folder, shared = (ex["folder"], ex.get("shared", False)) if ex.get("folder") else drive_folder(p)
    try:
        ok = gdrive.upload([f], posixpath.join(folder, "쇼츠"), shared, None, cancel)
    except RuntimeError:
        if not shared:
            raise
        folder, shared = posixpath.basename(folder), False  # 공유 폴더에 쓸 수 없으면 내 드라이브에
        ok = gdrive.upload([f], posixpath.join(folder, "쇼츠"), False, None, cancel)
    return {"folder": posixpath.join(folder, "쇼츠"), "shared": shared} if ok else None


def _sh_render(x):
    pid, sid, d = x["pid"], x["id"], _pdir(x["pid"])
    it = shorts.find(shorts.load(d), sid) if os.path.isdir(d) else None
    if not it:
        return
    p, _ = get_project(pid)
    key = (pid, sid)
    live = _sh_live[key] = {"progress": 0.0, "msg": "쇼츠를 만드는 중"}
    cancel = lambda: key in _sh_run["cancel"]  # noqa
    drive = bool(p.data.get("drive"))
    _set_item(d, sid, status="rendering", error=None)
    try:
        live["msg"] = "준비하는 중"
        box = shorts_box(p)
        sig = shorts.signature(p, it)
        out = shorts.out_path(p, it)

        def prog(r):
            live.update(progress=r * (0.9 if drive else 1.0), msg=f"쇼츠를 만드는 중 ({int(r * 100)}%)")
        if not shorts.render(p, it, out, box, prog, cancel):
            _set_item(d, sid, status="done" if it.get("file") else "draft")
            return
        _set_item(d, sid, status="done", file=out, rendered=time.time(), rendered_sig=sig, error=None, drive=None)
        if drive:
            live.update(progress=0.9, msg="구글 드라이브에 올리는 중")
            try:
                _set_item(d, sid, drive=_sh_drive_upload(p, out, cancel))
            except Exception as e:  # noqa  영상은 만들었으니 드라이브 실패만 따로 남긴다
                _set_item(d, sid, drive={"error": str(e)})
    except Exception as e:  # noqa
        traceback.print_exc()
        _set_item(d, sid, status="error", error=str(e))


def shorts_box(p):
    """원본의 검은 테두리를 뺀 영역. 한 번 찾으면 shorts.json에 둔다."""
    box = shorts.load(p.dir).get("box")
    if not box:
        box = shorts.content_box(p)
        shorts.change(p.dir, lambda s: s.update(box=box))
    return box


def shorts_after_export(p):
    """내보내기가 끝났을 때, 자동 설정이 켜져 있고 아직 후보를 고른 적이 없으면 후보 고르기를 넣는다."""
    st = shorts.load(p.dir)
    if _sh["auto"] and not st["items"] and st["suggest"].get("status") in (None, "idle"):
        shorts_enqueue(os.path.basename(p.dir), "suggest", auto=True)


def shorts_new(pid, at):
    """직접 추가: 더빙 영상의 at초에서 시작하는 문장부터 40초쯤을 새 쇼츠로 만든다(만들기 전 상태)."""
    p, _ = get_project(pid)
    tl = shorts.timeline(p)
    k = next((k for k, s in enumerate(tl) if s["t"] is not None and s["t"] + s["d"] > at), None)
    if k is None:
        raise ValueError("그 시각 뒤에 음성이 있는 문장이 없습니다")
    e = k
    while e + 1 < len(tl) and tl[e + 1]["t"] is not None and tl[e]["t"] + tl[e]["d"] - tl[k]["t"] < 40:
        e += 1

    def add(st):
        st["items"].append({"id": st["next_id"], "start": tl[k]["id"], "end": tl[e]["id"], "title": ["", ""],
                            "emph": {}, "reason": "직접 추가", "xpos": 0.5, "status": "draft", "created": time.time()})
        st["next_id"] += 1
    shorts.change(p.dir, add)


def shorts_update(pid, sid, body):
    """구간, 제목, 강조, 가로 위치를 고친다. 영상은 '다시 만들기'를 눌러야 바뀐다."""
    p, _ = get_project(pid)
    tl = shorts.timeline(p)

    def upd(st):
        it = shorts.find(st, sid)
        if not it:
            raise ValueError("없는 쇼츠입니다")
        new = dict(it)
        for k in ("start", "end"):
            if k in body:
                new[k] = int(body[k])
        if "title" in body:
            new["title"] = ([str(x).strip()[:30] for x in body["title"] or []] + ["", ""])[:2]
        if "emph" in body:
            new["emph"] = {str(k): [str(v).strip() for v in vs if str(v).strip()]
                           for k, vs in (body["emph"] or {}).items() if vs}
        if "xpos" in body:
            new["xpos"] = min(1.0, max(0.0, float(body["xpos"])))
        inf = shorts.info(p, new, tl)
        if "invalid" in inf:
            raise ValueError(inf["invalid"])
        if inf["len"] > shorts.LIMIT_LEN:
            raise ValueError("쇼츠는 3분을 넘을 수 없습니다")
        it.update(new)  # 구간 밖 문장의 강조는 남겨 둔다(구간을 다시 넓히면 되살아난다)
    shorts.change(p.dir, upd)


def shorts_delete(pid, sid):
    key = (pid, sid)
    with _glock:
        for x in list(_sh_q):
            if x["pid"] == pid and x["kind"] == "render" and x["id"] == sid:
                if key in _sh_live:
                    _sh_run["cancel"].add(key)  # 만드는 중이면 멈춘다
                else:
                    _sh_q.remove(x)

    def rm(st):
        it = shorts.find(st, sid)
        if it:
            st["items"].remove(it)
        return it
    it = shorts.change(_pdir(pid), rm)
    if it and it.get("file") and os.path.exists(it["file"]):
        os.remove(it["file"])


def shorts_view(pid, lite=False):
    """쇼츠 화면에 보일 프로젝트 하나의 쇼츠 목록. lite가 아니면 문장 목록(구간 고치기용)도 넣는다."""
    p, _ = get_project(pid)
    st = shorts.load(p.dir)
    tl = shorts.timeline(p)
    with _glock:
        order = [(x["pid"], x["kind"], x["id"]) for x in _sh_q]
    items = []
    for it in st["items"]:
        x = dict(it, **shorts.info(p, it, tl))
        x["has_file"] = bool(it.get("file")) and os.path.isfile(it["file"])
        x["dirty"] = x["has_file"] and shorts.signature(p, it, tl) != it.get("rendered_sig")
        x.update(_sh_live.get((pid, it["id"])) or {})
        if (pid, "render", it["id"]) in order:
            x["ahead"] = order.index((pid, "render", it["id"]))
        x["youtube"] = _yt["items"].get(short_key(pid, it["id"]))
        items.append(x)
    sug = dict(st["suggest"], **(_sh_live.get((pid, "suggest")) or {}))
    if sug.get("status") == "queued":
        if (pid, "suggest", None) in order:
            sug["ahead"] = order.index((pid, "suggest", None))
        if sug.get("auto") and _usage_pause():
            sug["msg"] = "Claude 사용량에 여유가 생기면 고릅니다"
    out = {"id": pid, "name": p.data["name"], "items": items, "suggest": sug, "auto": _sh["auto"],
           "drive": bool(p.data.get("drive"))}
    if not lite:
        out["sentences"] = [{"id": s["id"], "text": s["text"], "t": s["t"], "d": s["d"]} for s in tl]
    return out


def shorts_list():
    """쇼츠를 만들 수 있는 프로젝트(음성을 다 만든 것)와 쇼츠가 있는 프로젝트."""
    with _glock:
        busy = {x["pid"] for x in _sh_q}
    out = []
    for it in prj.list_projects():
        d = _pdir(it["dir"])
        has = os.path.exists(os.path.join(d, shorts.STATE))
        voice_done = bool(it["sentences"]) and it["tts"] == it["sentences"]
        if not (has or voice_done or it["exported"]):
            continue
        st = shorts.load(d)
        items, sug = st["items"], st["suggest"]
        out.append({"dir": it["dir"], "name": it["name"], "voice_done": voice_done, "count": len(items),
                    "done": sum(1 for x in items if x.get("file")),
                    "uploaded": sum(1 for x in items if (_yt["items"].get(short_key(it["dir"], x["id"])) or {})
                                    .get("status") == "done"),
                    "busy": it["dir"] in busy, "suggest": sug.get("status"),
                    "error": sug.get("error") if sug.get("status") == "error" else None})
    out.sort(key=lambda x: _natural(x["name"]))
    return {"items": out, "auto": _sh["auto"]}


def shorts_resume():
    """서버가 켜질 때 기다리던 쇼츠 일과 하던 일을 다시 대기열에 넣는다."""
    if os.path.exists(SHORTS_STATE):
        with open(SHORTS_STATE, encoding="utf-8") as f:
            _sh.update(json.load(f))
    n = 0
    for it in prj.list_projects():
        d = _pdir(it["dir"])
        if not os.path.exists(os.path.join(d, shorts.STATE)):
            continue
        st = shorts.load(d)
        if st["suggest"].get("status") in ("queued", "running"):
            shorts_enqueue(it["dir"], "suggest", auto=st["suggest"].get("auto", False))
            n += 1
        for x in st["items"]:
            if x.get("status") in ("queued", "rendering"):
                shorts_enqueue(it["dir"], "render", x["id"])
                n += 1
    if n:
        print("쇼츠 대기열을 이어 갑니다:", n, "개", flush=True)


def yt_short_meta(p, it):
    """쇼츠의 유튜브 제목, 설명, 태그. 전체 영상이 유튜브에 있으면 설명에 링크를 넣는다."""
    stem, s = p.data["name"], yt_settings()
    head = " ".join(x for x in it.get("title") or [] if x).strip() or stem
    title = s["shorts_title"].replace("{제목}", head).replace("{이름}", stem)
    title = title.replace("<", "(").replace(">", ")").strip()[:100]
    path = (p.data.get("drive") or {}).get("path")
    full = (_yt["items"].get(path) or {}).get("url") if path else None
    if not full:
        ex = yt_existing(stem, channel_videos())
        full = ex and ex["url"]
    lines = [ln.replace("{링크}", full or "") for ln in s["shorts_description"].split("\n") if full or "{링크}" not in ln]
    desc, tags = yt_meta(stem, "\n".join(lines), extra_tags=["Shorts"])
    return title, desc, tags


def _yt_upload_short(key, st, cancel):
    pid, sid = key[len(SHORT_KEY):].rsplit(":", 1)
    p, _ = get_project(pid)
    it = shorts.find(shorts.load(p.dir), int(sid))
    if not it or not it.get("file") or not os.path.isfile(it["file"]):
        raise RuntimeError("만든 쇼츠 영상이 없습니다")
    if shorts.signature(p, it) != it.get("rendered_sig"):
        raise RuntimeError("고친 내용이 영상에 아직 반영되지 않았습니다. 다시 만든 뒤 올리세요")
    if st.get("video_id"):
        return

    def prog(done, total):
        st["progress"] = done / total
        st["msg"] = f"유튜브에 올리는 중 ({done / 2**20:,.0f} / {total / 2**20:,.0f}MB)"
    title, desc, tags = yt_short_meta(p, it)
    st.update(status="uploading", msg="유튜브에 올리는 중", progress=0.0)
    _yt_save()
    vid = youtube.upload_video(it["file"], title, description=desc, tags=tags, privacy=YT_PRIVACY, progress=prog,
                               cancel=cancel)
    if vid is None:
        return
    st.update(video_id=vid, url=f"https://www.youtube.com/shorts/{vid}", title=title, privacy=YT_PRIVACY,
              uploaded=time.time(), progress=1.0)
    _yt_save()


# ---------- 자동 진행 대기열 ----------
# 자동 진행: 드라이브 영상을 차례로 프로젝트로 만들고 자막을 읽어 문장 목록까지 만든다(검수 단계에서 멈춤).
#   프로젝트 만들기 -> 자막 영역 자동 감지 -> 자막 찾기 -> AI 읽기 -> AI 문장 정리 (Claude 사용)
# 음성 대기열: 화면에서 "음성 만들기"를 누른 영상만 넣는다(사람이 검수한 뒤). 음성 -> 내보내기 -> 드라이브 올리기.
# 음성 줄 VOICE_WORKERS개가 늘 돌며 대기열에서 하나씩 가져가므로 CPU를 다투지 않는다.
# 자동 진행은 Claude 사용량이 USAGE_RESERVE를 넘으면 그 창이 초기화될 때까지 쉬어서, 사람이 Claude를 직접 쓸
# 몫을 남긴다.
BATCH_STATE = os.path.join(prj.ROOT, "_batch.json")
USAGE_RESERVE = {"seven_day": 0.8, "five_hour": 0.5}
# 음성 줄을 몇 개 동시에 돌릴지(tts.THREADS와 곱해 코어 수쯤)
VOICE_WORKERS = int(os.environ.get("DUBBER_VOICE_WORKERS", "4"))
BATCH_MAX_FAILS = 3
BAD_READ = 0.5  # 자막 그림의 이 비율 이상을 못 읽으면 자막 영역이 틀린 것으로 본다
LIMIT_MIN, LIMIT_MARGIN = 60, 120  # 한도에 걸리면 최소 이만큼(초), 풀리는 시각보다 이만큼 더 기다린다
_batch = {"on": False, "queue": [], "items": {}, "voice": "M4", "wait_until": None, "wait_reason": None,
          "voice_queue": []}  # 음성 대기열: [{"pid", "path"(자동 진행 영상이면), "params", "manual", "worker"}]
_batch_threads = {}
_voice_threads = {}
_voice_fails = {"n": 0}


def _batch_save():
    with _glock:
        tmp = BATCH_STATE + ".tmp"
        _write_json(tmp, _batch)
        os.replace(tmp, BATCH_STATE)


def _project_of(path):
    return next((it["dir"] for it in prj.list_projects() if it.get("drive") == path), None)


def _wait_job(pid):
    while True:
        j = _jobs.get(pid)
        if not j or j.done:
            return j
        time.sleep(5)


def _batch_step(pid, kind, params):
    """단계를 하나 돌리고 끝날 때까지 기다린다. 이미 돌고 있으면(서버 재시작 뒤 이어 하기 등) 그것을 기다린다."""
    p, lock = get_project(pid)
    try:
        start_step(pid, p, lock, kind, dict(params, kind=kind))
    except RuntimeError:
        pass
    j = _wait_job(pid)
    if j and j.error:
        if j.error.startswith(ai.UsageLimit.PREFIX):
            raise ai.UsageLimit((ai.load_usage().get("info") or {}).get("resetsAt"))
        raise RuntimeError(j.error)
    if j and j.cancelled:
        raise RuntimeError("작업을 중단했습니다")


def _batch_prep(path, st):
    """자막을 읽고 문장 목록을 만들 때까지. 상태를 보고 필요한 단계만 하므로 몇 번을 다시 해도 된다."""
    pid = _project_of(path)
    if not pid:
        st["msg"] = "프로젝트를 만드는 중"
        if _lib["files"] is None:
            _refresh_library()
        rel = path[len(LIBRARY) + 1:] if path.startswith(LIBRARY + "/") else posixpath.basename(path)
        size = next((f["size"] for f in _lib["files"] or [] if f["path"] == rel), -1)
        local = gdrive.download(path, DRIVE_DIR, size)  # 이미 받아 두었으면 바로 돌려준다
        p = prj.Project.create(local, {"drive": {"path": path, "shared": False},
                                       "settings": dict(prj.DEFAULT_SETTINGS, voice=_batch["voice"])})
        pid = os.path.basename(p.dir)
    st["pid"] = pid
    for _ in range(6):
        j = _jobs.get(pid)
        if j and not j.done and j.kind in ("tts", "export"):
            # 음성이나 내보내기가 돌고 있으면(사람이 직접 시작한 것 등) 자막은 이미 다 읽은 것이다
            if get_project(pid)[0].data["sentences"]:
                return
        _wait_job(pid)
        p, lock = get_project(pid)
        caps, sents = p.data["captions"], p.data["sentences"]
        unread = sum(1 for c in caps if not (c.get("text") or "").strip()) / max(len(caps), 1)
        if not caps:
            st["msg"] = "자막을 찾고 읽는 중"
            # 자막 영역이 없거나 다시 찾을 때만 자동 감지한다(미리 손으로 맞춘 영역은 그대로 쓴다).
            # 자막 찾기 -> AI 읽기 -> 문장 정리까지 이어진다
            _batch_step(pid, "scan", {"auto_roi": bool(st.get("rescanned"))})
            st["read_tried"] = True
        elif unread >= BAD_READ and st.get("read_tried"):
            if st.get("rescanned"):
                raise RuntimeError(f"자막 그림의 {unread:.0%}를 읽지 못했습니다. 자막 영역을 확인한 뒤 다시 하세요")
            st["rescanned"] = True  # 자막 영역이 틀렸을 수 있으니 자동 감지부터 한 번 다시 한다
            st["msg"] = "자막 영역을 다시 찾는 중"
            with lock:
                p.data["captions"], p.data["sentences"] = [], []
                p.save()
        elif not sents or unread >= BAD_READ:  # 자막은 찾았지만 아직 안 읽었다
            st["msg"] = "자막을 읽는 중"
            _batch_step(pid, "read", {})
            st["read_tried"] = True
        else:
            if not any(s.get("tts") for s in sents) and p.data["settings"].get("voice") != _batch["voice"]:
                with lock:
                    p.data["settings"]["voice"] = _batch["voice"]
                    p.save()
            return
    raise RuntimeError("자막 읽기를 여러 번 했지만 문장 목록을 만들지 못했습니다")


def voice_enqueue(pid, params=None, manual=False, path=None):
    """음성 대기열에 넣는다. 직접 누른 것(manual)은 자동 진행이 넣은 것들 앞(직접 누른 것끼리는 누른 순서)에 둔다.
    - 이미 만드는 중이면 그대로 둔다.
    - 이미 기다리는 중이면 자리는 그대로 두고 설정만 바꾼다. 다만 자동 진행으로 기다리던 것을 직접 누르면 앞으로 옮긴다."""
    clean = {k: v for k, v in (params or {}).items() if k != "kind"}
    with _glock:
        q = _batch["voice_queue"]
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
                e = {"pid": pid, "path": None, "params": clean, "manual": False, "worker": None, "queued": time.time()}
            if manual:
                e["params"] = clean
            e["manual"] = e["manual"] or manual
            e["path"] = e["path"] or path
            if e["manual"]:
                at = next((k for k, x in enumerate(q) if not x["manual"] and not x.get("worker")), len(q))
                q.insert(at, e)
            else:
                q.append(e)
    _batch_save()
    voice_kick()
    return e


def voice_waiting(pid):
    """대기열에서 기다리는 중이면 앞에 몇 편이 있는지, 아니면 None."""
    with _glock:
        waiting = [x["pid"] for x in _batch["voice_queue"] if not x.get("worker")]
    return waiting.index(pid) if pid in waiting else None


def voice_cancel(pid):
    """아직 시작하지 않은 음성을 대기열에서 뺀다."""
    with _glock:
        e = next((x for x in _batch["voice_queue"] if x["pid"] == pid and not x.get("worker")), None)
        if e:
            _batch["voice_queue"].remove(e)
    if e:
        _batch_save()
        # 서버가 꺼지기 전에 하던 음성이라 '진행 중' 표시가 남아 있으면 지운다(다시 켤 때 대기열에 돌아오지 않게)
        j = _jobs.get(pid)
        if not (j and not j.done):
            p, lock = get_project(pid)
            if (p.data.get("running_step") or {}).get("kind") in ("tts", "export"):
                with lock:
                    p.data.pop("running_step", None)
                    p.save()
    return bool(e)


def queued_status(pid):
    """대기열에서 기다리는 음성을 작업 상태처럼 보여 준다(화면은 진행 중으로 보고 '중단'으로 뺄 수 있다)."""
    n = voice_waiting(pid)
    if n is None:
        return None
    return {"kind": "tts", "progress": 0.0, "msg": f"음성 대기 중 (앞에 {n}편)" if n else "음성 대기 중 (다음 차례)",
            "error": None, "done": False, "cancelled": False, "result": None, "running": True, "resumed": False,
            "queued": True}


def job_status(pid):
    j = _jobs.get(pid)
    if j and not j.done:
        return j.status()
    return queued_status(pid) or (j.status() if j else None)


def _voice_run(e, st):
    pid = e["pid"]
    p, _ = get_project(pid)
    if st and not e["manual"] and p.data.get("last_export") and p.data.get("drive_export"):
        return  # 이미 끝난 영상
    _batch_step(pid, "tts", e["params"])  # 음성이 끝나면 내보내기와 드라이브 올리기가 이어진다
    if st:
        p, _ = get_project(pid)
        if not p.data.get("last_export"):
            raise RuntimeError("내보낸 파일이 없습니다")
        if not p.data.get("drive_export"):
            raise RuntimeError("구글 드라이브에 올리지 못했습니다")


def _voice_worker(name):
    """음성 줄 하나. 대기열 앞에서부터 하나씩 맡아 음성 -> 내보내기 -> 드라이브 올리기를 한다."""
    while True:
        with _glock:
            e = next((x for x in _batch["voice_queue"] if not x.get("worker")), None)
            if e:
                e["worker"] = name
        if not e:
            time.sleep(3)
            continue
        st = _batch["items"].get(e.get("path")) if e.get("path") else None
        if st:
            st.update(stage="voice", msg="음성을 만들고 내보내는 중", error=None, started=time.time())
        _batch_save()
        try:
            _voice_run(e, st)
            if st:
                st.update(stage="done", msg="")
                _voice_fails["n"] = 0
        except Exception as ex:  # noqa
            traceback.print_exc()
            if st:
                st.update(stage="error", error=str(ex), msg="")
                _voice_fails["n"] += 1
                if _voice_fails["n"] >= BATCH_MAX_FAILS and _batch["on"]:
                    batch_stop(f"음성이 {BATCH_MAX_FAILS}편 연달아 실패해 멈췄습니다. 실패 이유를 확인한 뒤 다시 시작하세요")
        finally:
            with _glock:
                if e in _batch["voice_queue"]:
                    _batch["voice_queue"].remove(e)
                if st:
                    st["finished"] = time.time()
            _batch_save()


def voice_kick():
    for i in range(VOICE_WORKERS):
        name = f"voice-{i}"
        t = _voice_threads.get(name)
        if not (t and t.is_alive()):
            _voice_threads[name] = threading.Thread(target=_voice_worker, args=(name,), daemon=True)
            _voice_threads[name].start()


def _usage_pause():
    """Claude 사용량이 USAGE_RESERVE를 넘었으면 (쉴 때까지의 시각, 이유). 사용량은 마지막 Claude 호출 때의 값이다."""
    info = ai.load_usage().get("info") or {}
    names = {"seven_day": "주간", "five_hour": "5시간"}
    for k, limit in USAGE_RESERVE.items():
        w = (info.get("unifiedWindows") or {}).get(k) or {}
        if w.get("utilization", 0) >= limit and w.get("resetsAt", 0) > time.time():
            return w["resetsAt"] + 120, f"Claude {names[k]} 사용량이 {w['utilization']:.0%}라 {limit:.0%}를 넘어"
    return None


def _batch_lane():
    """준비 줄. 대기열 순서대로 자막을 읽고 문장을 만든 뒤 음성 대기열에 넣는다."""
    want, busy = "waiting", "prep"
    fails = 0
    while _batch["on"]:
        with _glock:
            items = [(p, _batch["items"][p]) for p in _batch["queue"]]
            cur = next(((p, st) for p, st in items if st["stage"] == busy), None) \
                or next(((p, st) for p, st in items if st["stage"] == want), None)
            if cur:
                cur[1].update(stage=busy, error=None, started=time.time())
        if not cur:
            with _glock:
                _batch["on"] = False  # 자막 읽을 영상을 다 했다(음성은 사람이 검수하고 직접 시작한다)
            _batch_save()
            return
        path, st = cur
        _batch_save()
        pause = _usage_pause()
        if pause:
            until, why = pause
            st.update(stage=want, msg="")
            _batch.update(wait_until=until, wait_reason=why)
            _batch_save()
            while _batch["on"] and time.time() < until:
                time.sleep(max(0.5, min(60, until - time.time())))
            _batch.update(wait_until=None, wait_reason=None)
            continue
        try:
            _batch_prep(path, st)
            st.update(stage="ready", msg="")  # 검수 대기: 음성은 화면에서 직접 "음성 만들기"를 눌러 시작한다
            fails = 0
        except ai.UsageLimit as e:
            # 풀리는 시각을 모르면 30분, 이미 지난 시각이면(오래된 정보) 잠깐 기다렸다가 다시 해 본다
            until = max(e.resets_at or time.time() + 1800, time.time() + LIMIT_MIN) + LIMIT_MARGIN
            st.update(stage=want, msg=f"Claude 사용량 한도: {time.strftime('%m월 %d일 %H:%M', time.localtime(until))}에 이어서 합니다")
            _batch.update(wait_until=until, wait_reason="Claude 사용량 한도에 걸려")
            _batch_save()
            while _batch["on"] and time.time() < until:
                time.sleep(max(0.5, min(30, until - time.time())))
            _batch.update(wait_until=None, wait_reason=None)
            continue
        except Exception as e:  # noqa
            traceback.print_exc()
            st.update(stage="error", error=str(e), msg="")
            fails += 1
            if fails >= BATCH_MAX_FAILS:  # 모든 영상에 걸리는 문제(드라이브 연결 등)면 줄줄이 실패로 넘기지 않고 멈춘다
                st["finished"] = time.time()
                batch_stop(f"{BATCH_MAX_FAILS}편이 연달아 실패해 멈췄습니다. 실패 이유를 확인한 뒤 다시 시작하세요")
                return
        st["finished"] = time.time()
        _batch_save()


def batch_kick():
    voice_kick()
    t = _batch_threads.get("prep")
    if _batch["on"] and not (t and t.is_alive()):
        _batch_threads["prep"] = threading.Thread(target=_batch_lane, daemon=True)
        _batch_threads["prep"].start()


def _same_video_key(path):
    """받아 둔 영상 파일의 크기와 앞부분 4MB 해시. 같으면 같은 영상이 이름만 다르게 올라간 것."""
    f = os.path.join(DRIVE_DIR, posixpath.basename(path))
    if not os.path.isfile(f):
        return None
    with open(f, "rb") as fh:
        head = fh.read(4 << 20)
    import hashlib
    return os.path.getsize(f), hashlib.md5(head).hexdigest()


def _mark_duplicates():
    """대기 중인 영상 가운데 앞 영상과 같은 파일은 건너뛴다(같은 설교를 두 번 만들지 않는다)."""
    first = {}
    for p in _batch["queue"]:
        st = _batch["items"][p]
        key = _same_video_key(p)
        if key is None:
            continue
        if key in first and st["stage"] == "waiting":
            st.update(stage="skipped", msg="", error=None,
                      same_as=os.path.splitext(posixpath.basename(first[key]))[0])
        else:
            first.setdefault(key, p)


def batch_start(voice=None):
    """아직 끝나지 않은 JP 영상을 모두 대기열에 넣고 시작한다(번호순). 이미 넣은 영상의 진행 상태는 그대로 둔다."""
    lib = library(force=True)
    for _ in range(180):  # 서버가 막 켜져 드라이브 목록을 읽는 중이면 다 읽을 때까지 기다린다(바쁠 때는 1분 넘게 걸린다)
        if not lib["loading"] and not _lib["busy"]:
            break
        time.sleep(1)
        lib = library()
    if not lib["items"]:
        raise RuntimeError("구글 드라이브 목록을 읽지 못했습니다: " + str(lib.get("error") or "영상이 없습니다"))
    with _glock:
        if voice:
            _batch["voice"] = voice
        for it in lib["items"]:
            p = it["project"]
            if (p and p["exported"]) or (not p and it["drive_done"]):
                continue
            if it["path"] not in _batch["items"]:
                _batch["queue"].append(it["path"])
                _batch["items"][it["path"]] = {"stage": "waiting", "msg": "", "error": None}
            elif _batch["items"][it["path"]]["stage"] == "error":
                _batch["items"][it["path"]].update(stage="waiting", error=None, rescanned=False, read_tried=False)
        _batch["on"] = True
        _batch["stopped_reason"] = None
    _mark_duplicates()
    _batch_save()
    batch_kick()


def batch_stop(reason=None):
    """새 영상은 더 시작하지 않는다. 지금 하던 단계는 끝까지 한다. (예전에 자동으로 넣은 음성이 남아 있으면 뺀다)"""
    with _glock:
        _batch["on"] = False
        _batch["stopped_reason"] = reason
        _batch["voice_queue"] = [x for x in _batch["voice_queue"] if x["manual"] or x.get("worker")]
    _batch_save()


def batch_status():
    items = [(p, _batch["items"][p]) for p in _batch["queue"]]
    count = {}
    for _, st in items:
        count[st["stage"]] = count.get(st["stage"], 0) + 1
    name = lambda p: os.path.splitext(posixpath.basename(p))[0]  # noqa
    vq = list(_batch["voice_queue"])
    cur = {"prep": next(({"name": name(p), "msg": st.get("msg")} for p, st in items if st["stage"] == "prep"), None),
           "voice": [{"name": x["pid"], "msg": "음성을 만들고 내보내는 중" + (" (직접 넣음)" if x["manual"] else "")}
                     for x in vq if x.get("worker")]}
    return {"on": _batch["on"], "voice": _batch["voice"], "count": count, "total": len(items), "current": cur,
            "voice_waiting": sum(1 for x in vq if not x.get("worker")),
            "voice_manual": sum(1 for x in vq if not x.get("worker") and x["manual"]),
            "stopped_reason": _batch.get("stopped_reason"),
            "wait_until": _batch["wait_until"], "wait_reason": _batch.get("wait_reason"),
            "errors": [{"name": name(p), "path": p, "error": st["error"]} for p, st in items if st["stage"] == "error"],
            "skipped": [{"name": name(p), "same_as": st.get("same_as")} for p, st in items if st["stage"] == "skipped"]}


def batch_resume():
    if os.path.exists(BATCH_STATE):
        with open(BATCH_STATE, encoding="utf-8") as f:
            _batch.update(json.load(f))
        _batch.update(wait_until=None, wait_reason=None)
        _batch.setdefault("voice_queue", [])
        for x in _batch["voice_queue"]:
            x["worker"] = None  # 서버가 새로 켜지면 음성 줄이 다시 나눠 맡는다(하던 음성은 resume_all이 이어 간다)

        for st in _batch["items"].values():
            st.pop("worker", None)
    # 음성은 직접 요청한 것만 만든다: 예전에 자동 진행이 넣고 아직 시작하지 않은 음성은 뺀다
    _batch["voice_queue"] = [x for x in _batch["voice_queue"] if x["manual"]]
    if _batch["on"]:
        print("자동 진행 대기열을 이어 갑니다:", batch_status()["count"], "음성 대기", batch_status()["voice_waiting"], flush=True)
    batch_kick()


def yt_resume():
    """서버가 켜질 때 대기열을 이어 간다. 올리다 끊긴 영상은 처음부터 다시 올린다(유튜브에 영상이 생기기 전이라 중복되지 않는다)."""
    if os.path.exists(YT_STATE):
        with open(YT_STATE, encoding="utf-8") as f:
            _yt.update(json.load(f))
    if _yt["queue"]:
        head = _yt["items"].get(_yt["queue"][0], {})
        if head.get("status") == "uploading":
            head.update(resumed=True)
        for p in _yt["queue"]:
            _yt["items"].setdefault(p, {})["status"] = "queued"
        print("유튜브 올리기 대기열을 이어 갑니다:", len(_yt["queue"]), "개", flush=True)
        _yt_kick()


def drive_folder(p):
    """결과를 올릴 드라이브 폴더와 공유 문서함 여부. 공유 문서함 맨 위에 있는 파일은 상위 폴더가 없으니 내 드라이브에 둔다."""
    src = p.data["drive"]
    parent = posixpath.dirname(src["path"])
    return posixpath.join(parent, export.out_name(p)), bool(src.get("shared")) and bool(parent)


def upload_results(p, files, job, start):
    def prog(done, total, speed, i, n):
        job.progress = start + (1 - start) * done / total
        job.msg = f"구글 드라이브에 올리는 중 ({i}/{n} 파일, {done / 2**20:,.0f} / {total / 2**20:,.0f}MB)"
    job.msg = "구글 드라이브에 올리는 중"
    cancel = lambda: job.cancelled  # noqa
    folder, shared = drive_folder(p)
    try:
        ok = gdrive.upload(files, folder, shared, prog, cancel)
    except RuntimeError:
        if not shared:
            raise
        # 공유받은 폴더에 쓸 권한이 없으면 내 드라이브에 같은 이름의 폴더를 만든다
        folder, shared = posixpath.basename(folder), False
        ok = gdrive.upload(files, folder, False, prog, cancel)
    return {"folder": folder, "shared": shared, "files": [os.path.basename(f) for f in files]} if ok else None


def start_step(pid, p, lock, kind, params, restarts=0):
    """단계 작업을 시작한다. project.json에 진행 중인 단계를 남겨 두고, 끝나면(성공, 실패, 중단) 지운다.
    서버가 중간에 꺼지면 표시가 남으므로 다시 켤 때 resume_all이 그 단계를 처음부터 다시 한다."""
    def fn(job):
        with lock:
            p.data["running_step"] = {"kind": kind, "params": params, "restarts": restarts}
            p.save()
        try:
            return run_pipeline_job(p, lock, kind, job, params)
        finally:
            with lock:
                p.data.pop("running_step", None)
                p.save()
    j = start_job(pid, kind, fn)
    j.resumed = restarts > 0
    return j


def _mark_step(p, lock, kind, params):
    """한 작업 안에서 다음 단계로 넘어갈 때 진행 중 표시를 바꾼다(다음 단계에서 꺼지면 그 단계부터 다시 하도록)."""
    with lock:
        p.data["running_step"] = {"kind": kind, "params": params, "restarts": 0}
        p.save()


def resume_all():
    """서버가 켜질 때, 꺼지기 전에 하던 단계와 받던 영상을 처음부터 다시 시작한다."""
    if os.path.isdir(DRIVE_DIR):
        for f in os.listdir(DRIVE_DIR):  # 끊긴 내려받기의 조각 파일
            if f.endswith(".partial"):
                os.remove(os.path.join(DRIVE_DIR, f))
    if os.path.exists(IMPORT_MARK):
        with open(IMPORT_MARK, encoding="utf-8") as f:
            params = json.load(f)
        print("구글 드라이브에서 받던 영상을 처음부터 다시 받습니다:", params.get("path"), flush=True)
        start_import(params, resumed=True)
    voice = []  # 끊긴 음성(내보내기 포함)은 바로 시작하지 않고 음성 대기열에 넣는다(동시에 VOICE_WORKERS개까지)
    for it in prj.list_projects():
        pid = it["dir"]
        p, lock = get_project(pid)
        run = p.data.get("running_step")
        if not run:
            continue
        if run["kind"] in ("tts", "export"):
            print(f"{pid}: 꺼지기 전에 하던 음성을 음성 대기열에 넣습니다", flush=True)
            voice.append((pid, {k: v for k, v in (run.get("params") or {}).items() if k == "force"},
                          (p.data.get("drive") or {}).get("path")))
            continue
        restarts = run.get("restarts", 0) + 1
        if restarts > MAX_RESUME:
            print(f"{pid}: {run['kind']} 단계가 {MAX_RESUME}번 연달아 끊겨 다시 시작하지 않습니다", flush=True)
            with lock:
                p.data.pop("running_step", None)
                p.save()
            continue
        print(f"{pid}: 꺼지기 전에 하던 {run['kind']} 단계를 처음부터 다시 합니다", flush=True)
        start_step(pid, p, lock, run["kind"], run.get("params") or {}, restarts)
    return voice


def run_pipeline_job(p, lock, kind, job, params):
    """단계 작업. progress는 0~1, msg는 사람이 읽는 진행 설명."""
    cancel = lambda: job.cancelled  # noqa
    if kind == "scan":
        if params.get("auto_roi") or not p.data.get("roi"):
            job.msg = "자막 영역을 찾는 중"
            p.detect_roi()
        job.msg = "자막이 바뀌는 순간을 찾는 중"

        def prog(r):
            job.progress = r * 0.98
            job.msg = f"자막이 바뀌는 순간을 찾는 중 ({int(r * 100)}%)"
        n = p.scan(progress=prog, cancel=cancel)
        with lock:
            p.set_step("scan")
            p.save()
        if job.cancelled:
            return {"captions": n}
        # 자막 바뀜 찾기가 끝나면 AI 읽기로 바로 이어 간다(브라우저를 닫아도 이어진다)
        job.kind, job.progress = "read", 0.0
        _mark_step(p, lock, "read", {})
        return run_pipeline_job(p, lock, "read", job, {})
    if kind == "read":
        total = (len(p.data["captions"]) + p.data["settings"]["per_strip"] - 1) // max(p.data["settings"]["per_strip"], 1)

        tidy = p.data["settings"].get("ai_tidy")
        share = 0.85 if tidy else 1.0

        def prog(d, n):
            job.progress = share * d / max(n, 1)
            job.msg = f"AI가 자막 그림을 읽는 중 ({d}/{n} 묶음)"
        job.msg = f"AI가 자막 그림을 읽는 중 (0/{total} 묶음)"
        p.read(progress=prog, cancel=cancel)
        if job.cancelled:
            return None
        merged = None
        if tidy:
            def prog2(d, k):
                job.progress = share + (1 - share) * d / max(k, 1)
                job.msg = f"AI가 문장을 정리하는 중 ({d}/{k} 묶음)"
            job.msg = "AI가 문장을 정리하는 중"
            merged = p.tidy(progress=prog2, cancel=cancel)
        with lock:
            return {"sentences": p.build_sentences(merged)}
    if kind == "tidy":
        def prog2(d, k):
            job.progress = d / max(k, 1)
            job.msg = f"AI가 문장을 정리하는 중 ({d}/{k} 묶음)"
        job.msg = "AI가 문장을 정리하는 중"
        merged = p.tidy(progress=prog2, cancel=cancel)
        if merged is None:
            return None
        with lock:
            return {"sentences": p.build_sentences(merged)}
    if kind == "tts":
        def prog(d, n):
            job.progress = d / max(n, 1)
            job.msg = f"음성을 만드는 중 ({d}/{n} 문장)"
        job.msg = "음성 엔진을 준비하는 중"
        tts.run_all(p, progress=prog, cancel=cancel, force=bool(params.get("force")))
        with lock:
            p.set_step("tts")
            p.data["settings"]["orig_audio"] = "remove"
            p.save()
        if job.cancelled:
            return {}
        # 음성이 끝나면 모든 결과물을 원음 제거로 바로 내보낸다(브라우저를 닫아도 이어진다)
        job.kind = "export"
        params = {"want": ["video", "audio", "srt", "txt"], "orig_audio": "remove"}
        _mark_step(p, lock, "export", params)
        return run_pipeline_job(p, lock, "export", job, params)
    if kind == "export":
        want = set(params.get("want") or ["video", "srt"])
        names = {"track": "음성 트랙을 합치는 중", "video": "영상을 만드는 중", "audio": "오디오 파일을 만드는 중"}

        drive = bool(p.data.get("drive"))
        scale = 0.8 if drive else 1.0  # 남은 0.2는 드라이브 올리기

        def prog(stage, r):
            weights = {"track": (0.0, 0.15), "video": (0.15, 0.75), "audio": (0.9, 0.1)}
            a, w = weights.get(stage, (0, 1))
            job.progress = scale * (a + w * r)
            job.msg = f"{names.get(stage, stage)} ({int(r * 100)}%)"
        files, placements = export.run(p, want, orig_audio=params.get("orig_audio") or p.data["settings"]["orig_audio"],
                                       progress=prog, cancel=cancel)
        with lock:
            p.set_step("export")
            p.data["last_export"] = files
            p.data["drive_export"] = None
            p.save()
        if drive and files and not job.cancelled:
            uploaded = upload_results(p, files, job, scale)
            with lock:
                p.data["drive_export"] = uploaded
                p.save()
        if "video" in want and files and not job.cancelled:
            try:
                shorts_after_export(p)
            except Exception:  # noqa  쇼츠 때문에 내보내기가 실패로 보이지 않게
                traceback.print_exc()
        return {"files": files, "drive": p.data["drive_export"]}
    raise ValueError(kind)


class Handler(BaseHTTPRequestHandler):
    server_version = "dubber/0.1"

    def log_message(self, fmt, *args):
        first = str(args[0]) if args else ""
        if ("/api/p/" in first and "/job" in first) or "/api/drive/status" in first or "/api/library" in first or "/api/usage" in first:
            return
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, DELETE, HEAD, OPTIONS")
        self.end_headers()

    # ---- helpers ----
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, data, ctype, code=200, cache=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if cache:
            self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path, cache=False, download=False):
        if not os.path.isfile(path):
            return self._json({"error": "없는 파일"}, 404)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    if m.group(2):
                        end = min(int(m.group(2)), size - 1)
                elif m.group(2):
                    start = max(size - int(m.group(2)), 0)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if cache:
            self.send_header("Cache-Control", "max-age=86400")
        elif path.endswith((".html", ".js", ".css")):
            self.send_header("Cache-Control", "no-cache")  # 서버를 고친 뒤 브라우저가 예전 화면을 쓰지 않게
        if download:
            self.send_header("Content-Disposition",
                             "attachment; filename*=UTF-8''" + urllib.parse.quote(os.path.basename(path)))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    return
                left -= len(chunk)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    # ---- routing ----
    def do_GET(self):
        try:
            self._route("GET")
        except Exception as e:  # noqa
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        try:
            self._route("POST")
        except Exception as e:  # noqa
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def do_DELETE(self):
        try:
            self._route("DELETE")
        except Exception as e:  # noqa
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def _route(self, method):
        u = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(u.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if method == "GET" and path in ("/", "/index.html"):
            return self._file(os.path.join(STATIC, "index.html"))
        if method == "GET" and path.startswith("/static/"):
            return self._file(os.path.join(STATIC, os.path.basename(path)), cache=False)
        if path == "/api/projects" and method == "GET":
            items = prj.list_projects()
            for it in items:
                j = _jobs.get(it["dir"])
                it["job"] = j.status() if j and not j.done else queued_status(it["dir"])
            return self._json(items)
        if path == "/api/library":
            return self._json(library(force=bool(q.get("refresh"))))
        if path == "/api/batch":
            if method == "POST":
                body = self._body()
                if body.get("action") == "start":
                    try:
                        batch_start(body.get("voice"))
                    except RuntimeError as e:
                        return self._json({"error": str(e)}, 409)
                elif body.get("action") == "stop":
                    batch_stop()
            return self._json(batch_status())
        if path == "/api/usage":
            return self._json(ai.load_usage())
        if path == "/api/usage/check" and method == "POST":
            return self._json(ai.check_usage())
        if path == "/api/youtube/status":
            return self._json(dict(youtube.status(), playlist=YT_PLAYLIST, privacy=YT_PRIVACY))
        if path == "/api/youtube/login" and method == "POST":
            try:
                return self._json({"url": youtube.start_login()})
            except RuntimeError as e:
                return self._json({"error": str(e)}, 409)
        if path == "/api/youtube/upload" and method == "POST":
            try:
                return self._json(yt_enqueue(self._body()["path"]))
            except RuntimeError as e:
                return self._json({"error": str(e)}, 409)
        if path == "/api/youtube/settings":
            if method == "POST":
                body = self._body()
                with _yt_lock:
                    for k in YT_DEFAULTS:
                        if k in body:
                            _yt["settings"][k] = str(body[k])
                    _yt_save()
            return self._json(dict(yt_settings(), preview=yt_meta("218 선생이 아닌 구세주 예수")[0]))
        if path == "/api/youtube/cancel" and method == "POST":
            yt_cancel(self._body()["path"])
            return self._json({"ok": True})
        if path == "/api/shorts":
            if method == "POST":
                body = self._body()
                if "auto" in body:
                    _sh["auto"] = bool(body["auto"])
                    _write_json(SHORTS_STATE, _sh)
            return self._json(shorts_list())
        if path == "/api/drive/status":
            j = _jobs.get(DRIVE_JOB)
            return self._json({"available": gdrive.available(), "job": j.status() if j else None})
        if path == "/api/drive/list":
            return self._json(gdrive.list_dir(q.get("path", ""), bool(q.get("shared"))))
        if path == "/api/drive/import" and method == "POST":
            try:
                j = start_import(self._body())
            except RuntimeError:
                return self._json({"error": "이미 내려받는 영상이 있습니다"}, 409)
            return self._json(j.status())
        if path == "/api/drive/cancel" and method == "POST":
            j = _jobs.get(DRIVE_JOB)
            if j and not j.done:
                j.cancelled = True
                j.msg = "중단하는 중"
            return self._json(j.status() if j else None)
        if path == "/api/voices":
            return self._json(tts.VOICES)
        if path.startswith("/api/voice-sample/"):
            voice = os.path.basename(path)
            if voice not in tts.VOICES:
                return self._json({"error": "없는 목소리"}, 404)
            return self._file(tts.voice_sample(voice, os.path.join(HERE, "projects", "_samples")), cache=True)
        m = re.match(r"^/api/p/([^/]+)(/.*)?$", path)
        if not m:
            return self._json({"error": "없는 주소"}, 404)
        pid, rest = m.group(1), m.group(2) or ""
        p, lock = get_project(pid)
        job = _jobs.get(pid)

        if rest == "" and method == "GET":
            d = dict(p.data)
            d["sentences"] = [dict(s, reading_auto=p.reading_of(s)) for s in p.data["sentences"]]
            d["job"] = job_status(pid)
            d["id"] = pid
            return self._json(d)
        if rest == "/video":
            return self._file(p.data["video"])
        if rest.startswith("/crop/"):
            return self._file(os.path.join(p.dir, "crops", os.path.basename(rest)), cache=True)
        if rest.startswith("/tts/") and method == "GET":
            return self._file(os.path.join(p.dir, "tts", os.path.basename(rest)))
        if rest == "/frame":
            t = float(q.get("t", "0"))
            roi = p.data.get("roi") if q.get("roi") else None
            return self._bytes(frame_jpeg(p.data["video"], t, roi), "image/jpeg")
        if rest == "/job":
            if method == "GET":
                return self._json(job_status(pid))
            body = self._body()
            kind = body.get("kind")
            if kind == "tts":  # 음성은 바로 시작하지 않고 음성 대기열에 넣는다(직접 누른 것이 앞)
                drive = (p.data.get("drive") or {}).get("path")
                voice_enqueue(pid, body, manual=True, path=drive if drive in _batch["items"] else None)
                return self._json(job_status(pid))
            try:
                j = start_step(pid, p, lock, kind, body)
            except RuntimeError as e:
                return self._json({"error": str(e)}, 409)
            return self._json(j.status())
        if rest == "/job/cancel" and method == "POST":
            if voice_cancel(pid):
                return self._json(job_status(pid))
            if job and not job.done:
                job.cancelled = True
                job.msg = "중단하는 중 (진행 중인 AI 호출이 끝나면 멈춥니다. 최대 5분)"
            return self._json(job.status() if job else None)
        if rest == "/roi" and method == "POST":
            body = self._body()
            with lock:
                if body.get("auto"):
                    roi = p.detect_roi()
                else:
                    import captions
                    roi = captions.even_roi({k: int(body[k]) for k in ("x", "y", "w", "h")},
                                            p.data["info"]["width"], p.data["info"]["height"])
                    p.data["roi"] = roi
                    p.save()
            return self._json(roi)
        if rest == "/settings" and method == "POST":
            body = self._body()
            with lock:
                for k, v in body.items():
                    if k in prj.DEFAULT_SETTINGS:
                        p.data["settings"][k] = v
                if "min_gap" in body:
                    p.update_ranges()
                if "voice" in body or "speed" in body or "tts_steps" in body:
                    for s in p.data["sentences"]:
                        s["tts"], s["tts_dur"] = None, None
                p.save()
            return self._json(p.data["settings"])
        if rest == "/cuts" and method == "POST":
            with lock:
                cuts = p.set_cuts(self._body().get("cuts") or [])
            return self._json({"cuts": cuts, "sentences": p.data["sentences"]})
        if rest == "/plan":
            return self._json(export.plan(p))
        if rest.startswith("/shorts"):
            return self._shorts(pid, p, rest[len("/shorts"):], method, q)
        if rest == "/download":
            f = q.get("path")
            if not (f and os.path.abspath(f) in [os.path.abspath(x) for x in p.data.get("last_export", [])]):
                return self._json({"error": "없는 파일"}, 404)
            return self._file(f, download=True)
        sm = re.match(r"^/sentence/(\d+)(/.*)?$", rest)
        if sm:
            sid, action = int(sm.group(1)), sm.group(2) or ""
            with lock:
                if method == "DELETE":
                    p.delete_sentence(sid)
                    return self._json({"ok": True})
                if action == "" and method == "POST":
                    return self._json(p.update_sentence(sid, **self._body()))
                if action == "/split":
                    return self._json(p.split_sentence(sid, int(self._body()["cap"])) or {})
                if action == "/merge":
                    return self._json(p.merge_next(sid) or {})
                if action == "/tts":
                    _, s = p.find(sid)
                    body = self._body()
                    if "reading" in body or "speed" in body:
                        p.update_sentence(sid, **{k: body[k] for k in ("reading", "speed") if k in body})
                    tts.ensure(p, s, force=True)
                    p.save()
                    return self._json(s)
        return self._json({"error": "없는 주소"}, 404)

    def _shorts(self, pid, p, rest, method, q):
        """/api/p/<pid>/shorts... : 쇼츠 목록, 후보 고르기, 직접 추가, 고치기, 다시 만들기, 지우기, 영상, 유튜브."""
        view = lambda: self._json(shorts_view(pid, lite=True))  # noqa
        try:
            if rest == "" and method == "GET":
                return self._json(shorts_view(pid, lite=bool(q.get("lite"))))
            if rest == "/suggest" and method == "POST":
                shorts_enqueue(pid, "suggest")
                return view()
            if rest == "/new" and method == "POST":
                shorts_new(pid, float(self._body().get("at") or 0))
                return view()
            m = re.match(r"^/(\d+)(/.*)?$", rest)
            if not m:
                return self._json({"error": "없는 주소"}, 404)
            sid, action = int(m.group(1)), m.group(2) or ""
            it = shorts.find(shorts.load(p.dir), sid)
            if not it:
                return self._json({"error": "없는 쇼츠입니다"}, 404)
            if action == "/video" and method == "GET":
                return self._file(it.get("file") or "", download=bool(q.get("dl")))
            if action == "/frame" and method == "GET":
                t = float(q["t"]) if q.get("t") else None
                return self._bytes(shorts.preview(p, it, shorts_box(p), t), "image/jpeg")
            if action == "" and method == "DELETE":
                shorts_delete(pid, sid)
                return view()
            if action == "" and method == "POST":
                shorts_update(pid, sid, self._body())
                return view()
            if action == "/render" and method == "POST":
                shorts_enqueue(pid, "render", sid)
                return view()
            if action == "/youtube" and method == "POST":
                if shorts.signature(p, it) != it.get("rendered_sig"):
                    return self._json({"error": "고친 내용을 영상에 반영하려면 먼저 다시 만드세요"}, 409)
                yt_enqueue(short_key(pid, sid))
                return view()
            if action == "/youtube/cancel" and method == "POST":
                yt_cancel(short_key(pid, sid))
                return view()
        except (ValueError, RuntimeError) as e:
            return self._json({"error": str(e)}, 409)
        return self._json({"error": "없는 주소"}, 404)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # 실제로 보내지 않고 바깥으로 나가는 주소만 고른다
        return s.getsockname()[0]
    except OSError:
        return "<이 PC의 IP>"
    finally:
        s.close()


def kill_orphans():
    """꺼진 서버가 남긴 ffmpeg(내보내기, 쇼츠)를 끈다. 서버를 끄면 ffmpeg는 혼자 계속 돌아서, 다시 시작한 작업과
    같은 파일에 함께 쓰면 결과 영상이 깨진다. 프로젝트 폴더를 쓰는 ffmpeg 중 부모가 파이썬이 아닌 것(고아)만 끈다."""
    if not os.path.isdir("/proc"):
        return
    root = os.path.abspath(prj.ROOT).encode()

    def cmd(pid):
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().split(b"\0")
    for d in os.listdir("/proc"):
        try:
            args = cmd(d) if d.isdigit() else None
            if not args or os.path.basename(args[0]) != b"ffmpeg" or root not in b" ".join(args):
                continue
            with open(f"/proc/{d}/stat", "rb") as f:
                ppid = int(f.read().rsplit(b")", 1)[1].split()[1])
            if b"python" in os.path.basename(cmd(ppid)[0]):
                continue  # 명령줄로 직접 돌리는 작업
            os.kill(int(d), 9)
            print("꺼진 서버가 남긴 ffmpeg를 끕니다:", d, flush=True)
        except (OSError, ValueError, IndexError):
            continue


def lock_root():
    """한 프로젝트 폴더에는 서버 하나만 띄운다. 둘이면 같은 작업을 동시에 이어 하고 project.json을 서로 덮어쓴다."""
    f = open(os.path.join(prj.ROOT, "_server.lock"), "a+")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f"이 프로젝트 폴더({prj.ROOT})를 쓰는 서버가 이미 실행 중입니다. 먼저 그 서버를 끄세요.")
    return f  # 서버가 끝날 때까지 열어 둔다


def main():
    os.makedirs(prj.ROOT, exist_ok=True)
    _root_lock = lock_root()  # noqa
    kill_orphans()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    voice = resume_all()
    yt_resume()
    batch_resume()
    shorts_resume()
    for pid, params, path in voice:  # 음성 대기열을 불러온 뒤에 넣는다. 하던 음성은 직접 요청했던 것이다
        voice_enqueue(pid, params, manual=True, path=path if path in _batch["items"] else None)
    httpd.daemon_threads = True
    url = f"http://127.0.0.1:{PORT}/"
    print("설교 영상 한국어 더빙:", url, "· 프로젝트 폴더:", prj.ROOT, flush=True)
    if HOST != "127.0.0.1":
        print(f"다른 PC에서 접속: http://{lan_ip()}:{PORT}/ (같은 네트워크의 누구나 접속할 수 있습니다)", flush=True)
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
