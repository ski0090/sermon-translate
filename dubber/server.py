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

import export
import gdrive
import project as prj
import tts

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
DRIVE_DIR = os.path.join(prj.ROOT, "_drive")  # 구글 드라이브에서 받은 영상
DRIVE_JOB = "_drive"
IMPORT_MARK = os.path.join(DRIVE_DIR, "_import.json")  # 받는 중인 영상(서버가 꺼졌다 켜지면 다시 받는다)
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
        it["job"] = j.status() if j and not j.done else None
    by_path = {it["drive"]: it for it in projects if it.get("drive")}
    imp = _jobs.get(DRIVE_JOB)
    importing = imp.target if imp and not imp.done else None
    items, used = [], set()
    for f in sorted((f for f in files if "/" not in f["path"]), key=lambda f: _natural(f["path"])):
        path = LIBRARY + "/" + f["path"]
        stem = os.path.splitext(f["path"])[0]
        dubbed = stem + " (한국어 더빙).mp4"
        it = {"name": stem, "path": path, "size": f["size"],
              "drive_done": f"{stem}{export.OUT_SUFFIX}/{dubbed}" in sub or f"{stem}/out/{dubbed}" in sub,
              "legacy": f"{stem}/project.json" in sub,
              "project": by_path.get(path),
              "importing": imp.status() if importing == path else None}
        if it["project"]:
            used.add(it["project"]["dir"])
        items.append(it)
    return {"root": LIBRARY, "items": items, "others": [p for p in projects if p["dir"] not in used],
            "error": _lib["error"], "loading": _lib["files"] is None}


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
    for it in prj.list_projects():
        pid = it["dir"]
        p, lock = get_project(pid)
        run = p.data.get("running_step")
        if not run:
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
        return {"files": files, "drive": p.data["drive_export"]}
    raise ValueError(kind)


class Handler(BaseHTTPRequestHandler):
    server_version = "dubber/0.1"

    def log_message(self, fmt, *args):
        first = str(args[0]) if args else ""
        if ("/api/p/" in first and "/job" in first) or "/api/drive/status" in first or "/api/library" in first:
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
                it["job"] = j.status() if j and not j.done else None
            return self._json(items)
        if path == "/api/library":
            return self._json(library(force=bool(q.get("refresh"))))
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
            d["job"] = job.status() if job else None
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
                return self._json(job.status() if job else None)
            body = self._body()
            kind = body.get("kind")
            try:
                j = start_step(pid, p, lock, kind, body)
            except RuntimeError as e:
                return self._json({"error": str(e)}, 409)
            return self._json(j.status())
        if rest == "/job/cancel" and method == "POST":
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


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # 실제로 보내지 않고 바깥으로 나가는 주소만 고른다
        return s.getsockname()[0]
    except OSError:
        return "<이 PC의 IP>"
    finally:
        s.close()


def main():
    os.makedirs(prj.ROOT, exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    resume_all()
    httpd.daemon_threads = True
    url = f"http://127.0.0.1:{PORT}/"
    print("설교 영상 한국어 더빙:", url, flush=True)
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
