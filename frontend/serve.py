"""화면 서버: 브라우저 화면(frontend/, Vue, 빌드 없음)을 내주고 /api/...는 API 서버로 그대로 넘긴다(역방향 프록시).
사용자는 이 서버의 주소 하나만 연다. 표준 라이브러리만 쓴다(Node도 빌드도 필요 없다).
실행: python frontend/serve.py [--port N] [--api URL] [--lan]  ->  http://127.0.0.1:8765"""
import argparse
import email.utils
import http.client
import json
import mimetypes
import os
import posixpath
import socket
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
# 내주는 것은 첫 화면(index.html)과 이 두 폴더뿐이다. serve.py 같은 다른 파일은 내주지 않는다
STATIC_DIRS = ("src", "vendor")
# 윈도우 레지스트리가 .js를 text/plain으로 알려 주면 브라우저가 화면 모듈을 불러오지 않는다
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
CHUNK = 1 << 20  # 영상처럼 큰 응답은 1MB씩 이어 보낸다
TIMEOUT = 900  # API 중에는 몇 분 걸리는 것이 있다(AI 도구 연결 시험은 3분쯤)
# API 서버로 넘기는 요청 머리와 브라우저에 돌려주는 응답 머리. Range가 있어야 영상을 건너뛰며 볼 수 있다
REQ_HEADERS = ("Content-Type", "Content-Length", "Range", "If-Range", "Accept")
RES_HEADERS = ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Content-Disposition",
               "Cache-Control")
GONE = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)  # 브라우저가 먼저 끊음(영상 건너뛰기 등)


def quiet(path):
    """몇 초마다 부르는 요청은 기록하지 않는다(API 서버의 기록 규칙과 같다)."""
    return (("/api/p/" in path and "/job" in path) or "/api/drive/status" in path or "/api/library" in path
            or "/api/usage" in path)


class Handler(BaseHTTPRequestHandler):
    server_version = "dubber-web/0.1"

    def log_request(self, code="-", size="-"):
        # 화면 파일은 실패했을 때만 적는다
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/") and quiet(path):
            return
        if not path.startswith("/api/") and str(code).isdigit() and int(code) < 400:
            return
        super().log_request(code, size)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, obj, code):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_DELETE(self):
        self._handle("DELETE")

    def _handle(self, method):
        try:
            if self.path.startswith("/api/"):
                return self._proxy(method)
            if method != "GET":
                return self._json({"error": "없는 주소"}, 404)
            return self._static()
        except GONE:
            pass

    # ---- 화면 파일 ----
    def _static(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0].split("#", 1)[0])
        rel = posixpath.normpath("/" + path).lstrip("/") or "index.html"  # ..은 맨 위에서 멈춘다
        top = rel.split("/", 1)[0]
        if rel == "index.html":
            full = os.path.join(HERE, "index.html")
        elif top in STATIC_DIRS and "/" in rel and "\\" not in rel and "\0" not in rel:
            full = os.path.abspath(os.path.join(HERE, *rel.split("/")))
            if not full.startswith(os.path.join(HERE, top) + os.sep):
                full = None
        else:
            full = None
        if not full or not os.path.isfile(full):
            return self._json({"error": "없는 주소"}, 404)
        st = os.stat(full)
        # 화면을 고친 뒤 브라우저가 예전 화면을 쓰지 않게 매번 확인하고, 바뀌지 않았으면 304로 끝낸다.
        # vendor(Vue)는 바뀌지 않으므로 하루 동안 기억해 둔다
        modified = email.utils.formatdate(int(st.st_mtime), usegmt=True)
        cache = "max-age=86400" if top == "vendor" else "no-cache"
        since = self.headers.get("If-Modified-Since")
        if since and since == modified:
            self.send_response(304)
            self.send_header("Cache-Control", cache)
            self.send_header("Last-Modified", modified)
            self.end_headers()
            return
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(full)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.send_header("Last-Modified", modified)
        self.end_headers()
        self.wfile.write(data)

    # ---- API 넘기기 ----
    def _proxy(self, method):
        api = self.server.api
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        headers = {k: self.headers[k] for k in REQ_HEADERS if self.headers.get(k) is not None}
        # 연결은 금방 끝나야 하고, 응답은 오래 기다린다
        conn = (http.client.HTTPSConnection if api.scheme == "https" else http.client.HTTPConnection)(
            api.hostname, api.port, timeout=10)
        try:
            try:
                conn.connect()
                conn.sock.settimeout(TIMEOUT)
                conn.request(method, api.path.rstrip("/") + self.path, body=body, headers=headers)
                r = conn.getresponse()
            except OSError:
                return self._json({"error": f"API 서버({self.server.api_url})에 연결하지 못했습니다"}, 502)
            self.send_response(r.status, r.reason)
            for k in RES_HEADERS:
                v = r.getheader(k)
                if v is not None:
                    self.send_header(k, v)
            self.end_headers()
            try:
                while True:
                    chunk = r.read1(CHUNK)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except OSError:
                return  # 브라우저가 끊었거나(영상 건너뛰기) API 서버가 도중에 끊었다
        finally:
            conn.close()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], GONE):
            return  # 브라우저가 먼저 끊은 것은 오류가 아니다
        super().handle_error(request, client_address)


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
    ap = argparse.ArgumentParser(description="설교 영상 한국어 더빙 화면 서버")
    ap.add_argument("--port", type=int, default=int(os.environ.get("DUBBER_PORT", "8765")), help="화면 서버 포트")
    ap.add_argument("--api", default=os.environ.get("DUBBER_API", "http://127.0.0.1:8766"), help="API 서버 주소")
    ap.add_argument("--lan", action="store_true", help="같은 네트워크의 다른 PC에서도 접속을 받는다")
    args = ap.parse_args()
    host = os.environ.get("DUBBER_HOST") or ("0.0.0.0" if args.lan else "127.0.0.1")
    httpd = Server((host, args.port), Handler)
    httpd.api_url = args.api.rstrip("/")
    httpd.api = urllib.parse.urlsplit(httpd.api_url)
    print(f"설교 영상 한국어 더빙: http://127.0.0.1:{args.port}/ · API 서버: {httpd.api_url}", flush=True)
    if host != "127.0.0.1":
        print(f"다른 PC에서 접속: http://{lan_ip()}:{args.port}/ (같은 네트워크의 누구나 접속할 수 있습니다)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
