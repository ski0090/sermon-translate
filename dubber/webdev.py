"""Vue로 옮기는 중인 새 화면(web/)을 다른 포트에서 띄우는 개발용 서버.

실행: python webdev.py  ->  http://127.0.0.1:8766/
- web/ 폴더의 파일은 직접 내주고, 나머지(/api/..., /static/...)는 지금 서버(8765)로 넘긴다.
  그래서 지금 서버를 고치거나 다시 켜지 않고 새 화면을 나란히 시험할 수 있다. 데이터와 작업은 같은 서버의 것이다.
- /old 는 지금 화면(8765의 /)이다. 새 화면에 아직 없는 화면(프로젝트 작업, 쇼츠)은 여기로 연다.
- --lan이면 같은 네트워크의 다른 PC에서도 접속을 받는다. 포트는 DUBBER_WEB_PORT, 넘길 서버 포트는 DUBBER_PORT.
"""
import mimetypes
import os
import posixpath
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
PORT = int(os.environ.get("DUBBER_WEB_PORT", "8766"))
UPSTREAM = f"http://127.0.0.1:{int(os.environ.get('DUBBER_PORT', '8765'))}"
HOST = os.environ.get("DUBBER_HOST") or ("0.0.0.0" if "--lan" in sys.argv else "127.0.0.1")
PASS_REQ = ("Content-Type", "Range", "If-Range")
PASS_RES = ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Content-Disposition", "Cache-Control")
mimetypes.add_type("text/javascript", ".js")


class Handler(BaseHTTPRequestHandler):
    server_version = "dubber-web/0.1"

    def log_message(self, fmt, *args):
        pass  # 화면이 몇 초마다 묻는 요청이 많아 남기지 않는다

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_DELETE(self):
        self._handle("DELETE")

    def _handle(self, method):
        path = urllib.parse.urlparse(self.path).path
        if method == "GET" and not path.startswith(("/api/", "/static/")) and path not in ("/old", "/old/"):
            return self._static(path)
        self._proxy(method)

    def _static(self, path):
        rel = posixpath.normpath(urllib.parse.unquote(path)).lstrip("/") or "index.html"
        full = os.path.join(WEB, *rel.split("/"))
        if not full.startswith(WEB + os.sep) or not os.path.isfile(full):
            return self._send(404, b"not found", "text/plain; charset=utf-8")
        with open(full, "rb") as f:
            data = f.read()
        self._send(200, data, mimetypes.guess_type(full)[0] or "application/octet-stream")

    def _send(self, code, data, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")  # 고친 화면이 바로 보이게
        self.end_headers()
        self.wfile.write(data)

    def _proxy(self, method):
        u = urllib.parse.urlparse(self.path)
        path = "/" if u.path in ("/old", "/old/") else self.path
        if u.path in ("/old", "/old/") and u.query:
            path += "?" + u.query
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        req = urllib.request.Request(UPSTREAM + path, data=body, method=method,
                                     headers={k: self.headers[k] for k in PASS_REQ if self.headers.get(k)})
        try:
            res = urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as e:
            res = e  # 4xx/5xx도 본문(오류 JSON)을 그대로 넘긴다
        except OSError as e:
            return self._send(502, f'{{"error": "지금 서버({UPSTREAM})에 연결하지 못했습니다: {e}"}}'.encode(),
                              "application/json; charset=utf-8")
        with res:
            self.send_response(res.status)
            for k in PASS_RES:
                if res.headers.get(k):
                    self.send_header(k, res.headers[k])
            self.end_headers()
            try:
                while True:
                    chunk = res.read(1 << 16)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass  # 영상을 넘기다 브라우저가 끊은 경우


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.daemon_threads = True
    print(f"새 화면(Vue): http://127.0.0.1:{PORT}/ · API는 {UPSTREAM}로 넘김", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
