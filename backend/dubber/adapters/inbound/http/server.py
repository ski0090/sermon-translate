"""HTTP 서버 바탕: 경로표(Router), 요청, 응답(JSON, 파일 이어 받기, 바이트). 표준 라이브러리만 쓴다.
경로마다 처리 함수는 응답 객체를 돌려주고, 오류는 종류에 따라 상태 코드로 바꾼다."""
import json
import mimetypes
import os
import re
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ....domain.errors import Conflict, NotFound

# 윈도우 레지스트리가 형식을 엉뚱하게 알려 주는 일이 있어 화면에서 쓰는 형식은 직접 정해 둔다
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
# 오류 종류 -> 상태 코드(경로마다 더 정할 수 있다). 여기에 없는 오류는 500
ERRORS = {NotFound: 404, Conflict: 409}
QUIET = re.compile(r"/api/p/.*/job|/api/drive/status|/api/library|/api/usage")  # 몇 초마다 묻는 주소는 기록하지 않는다


class Json:
    def __init__(self, obj, code=200):
        self.obj, self.code = obj, code


class Bytes:
    def __init__(self, data, ctype, cache=False):
        self.data, self.ctype, self.cache = data, ctype, cache


class File:
    def __init__(self, path, cache=False, download=False):
        self.path, self.cache, self.download = path, cache, download


def not_found():
    return Json({"error": "없는 주소"}, 404)


class Request:
    def __init__(self, method, path, query, headers, rfile):
        self.method, self.path, self.query, self.headers = method, path, query, headers
        self._rfile = rfile
        self._body = None

    def body(self):
        if self._body is None:
            n = int(self.headers.get("Content-Length") or 0)
            self._body = json.loads(self._rfile.read(n).decode("utf-8")) if n else {}
        return self._body


class Router:
    def __init__(self):
        self.routes = []

    def route(self, methods, pattern, errors=None):
        """methods: "GET", "POST", "GET POST" 또는 None(모두). pattern: 경로 정규식(이름 없는 묶음이 인자로 간다).
        errors: {오류 종류: 상태 코드 또는 (상태 코드, 알림 글)} 이 경로에서만 쓰는 것."""
        def deco(fn):
            self.routes.append((set(methods.split()) if methods else None, re.compile(pattern + "$"), fn, errors or {}))
            return fn
        return deco

    def dispatch(self, req):
        for methods, rx, fn, errors in self.routes:
            m = rx.match(req.path)
            if not m or (methods and req.method not in methods):
                continue
            try:
                return fn(req, *m.groups())
            except Exception as e:  # noqa
                for kind, code in list(errors.items()) + list(ERRORS.items()):
                    if isinstance(e, kind):
                        code, msg = code if isinstance(code, tuple) else (code, str(e))
                        return Json({"error": msg}, code)
                raise
        return not_found()


def make_handler(router):
    class Handler(BaseHTTPRequestHandler):
        server_version = "dubber-api/0.2"

        def log_message(self, fmt, *args):
            first = str(args[0]) if args else ""
            if QUIET.search(first):
                return
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Allow", "GET, POST, DELETE, OPTIONS")
            self.end_headers()

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_DELETE(self):
            self._handle("DELETE")

        def _handle(self, method):
            u = urllib.parse.urlparse(self.path)
            req = Request(method, urllib.parse.unquote(u.path), dict(urllib.parse.parse_qsl(u.query)), self.headers,
                          self.rfile)
            try:
                res = router.dispatch(req)
            except Exception as e:  # noqa
                traceback.print_exc()
                res = Json({"error": str(e)}, 500)
            if isinstance(res, File):
                return self._file(res)
            if isinstance(res, Bytes):
                return self._bytes(res)
            if not isinstance(res, Json):
                res = Json(res)
            self._json(res.obj, res.code)

        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _bytes(self, res):
            self.send_response(200)
            self.send_header("Content-Type", res.ctype)
            self.send_header("Content-Length", str(len(res.data)))
            if res.cache:
                self.send_header("Cache-Control", "max-age=86400")
            self.end_headers()
            self.wfile.write(res.data)

        def _file(self, res):
            """파일을 보낸다. Range를 받으면 그 부분만(영상 넘겨 보기)."""
            path = res.path
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
            if res.cache:
                self.send_header("Cache-Control", "max-age=86400")
            if res.download:
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
    return Handler


def serve(host, port, router):
    httpd = ThreadingHTTPServer((host, port), make_handler(router))
    httpd.daemon_threads = True
    return httpd
