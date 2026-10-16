"""유튜브 업로드(YouTube Data API v3). 표준 라이브러리만 쓴다.
OAuth 클라이언트는 rclone의 구글 드라이브 리모트에 넣은 client_id/secret을 같이 쓴다(환경 변수 DUBBER_YT_CLIENT_ID,
DUBBER_YT_CLIENT_SECRET로 바꿀 수 있다). 로그인 토큰은 ~/.config/dubber/youtube.json에 둔다."""
import json
import os
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import gdrive

TOKEN = os.path.join(os.path.expanduser("~"), ".config", "dubber", "youtube.json")
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"
# rclone 클라이언트에 이미 등록된 리디렉션 주소를 그대로 쓴다(콘솔에서 따로 추가할 필요가 없다)
REDIRECT_PORT = 53682
REDIRECT = f"http://127.0.0.1:{REDIRECT_PORT}/"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"
CHUNK = 8 * 1024 * 1024  # 256KB의 배수
QUOTA_REASONS = ("quotaExceeded", "dailyLimitExceeded", "uploadLimitExceeded", "rateLimitExceeded")

_lock = threading.Lock()
login_state = {"busy": False, "error": None}


class QuotaExceeded(RuntimeError):
    pass


class ApiError(RuntimeError):
    def __init__(self, code, msg):
        super().__init__(f"유튜브 API 오류 {code}: {msg}")
        self.code = code


def client():
    cid, sec = os.environ.get("DUBBER_YT_CLIENT_ID"), os.environ.get("DUBBER_YT_CLIENT_SECRET")
    if cid and sec:
        return cid, sec
    r = subprocess.run(["rclone", "config", "dump"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    conf = json.loads(r.stdout or "{}").get(gdrive.REMOTE.rstrip(":"), {})
    if conf.get("client_id") and conf.get("client_secret"):
        return conf["client_id"], conf["client_secret"]
    raise RuntimeError("OAuth 클라이언트를 찾지 못했습니다. rclone gdrive 리모트에 client_id를 넣었는지 확인하세요")


# ---------- 토큰 ----------
def _load():
    try:
        with open(TOKEN, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save(tok):
    os.makedirs(os.path.dirname(TOKEN), exist_ok=True)
    fd = os.open(TOKEN, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(tok, f)


def _post_form(url, data):
    req = urllib.request.Request(url, urllib.parse.urlencode(data).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"구글 로그인 오류 {e.code}: {body[:300]}")


def access_token():
    with _lock:
        tok = _load()
        if not tok or not tok.get("refresh_token"):
            raise RuntimeError("유튜브가 연결되어 있지 않습니다. 시작 화면에서 \"유튜브 연결\"을 누르세요")
        if tok.get("expires_at", 0) < time.time() + 60:
            cid, sec = client()
            new = _post_form(TOKEN_URL, {"client_id": cid, "client_secret": sec, "grant_type": "refresh_token",
                                         "refresh_token": tok["refresh_token"]})
            tok["access_token"], tok["expires_at"] = new["access_token"], time.time() + new.get("expires_in", 3600)
            _save(tok)
        return tok["access_token"]


def status():
    tok = _load()
    return {"connected": bool(tok and tok.get("refresh_token")), "channel": (tok or {}).get("channel"),
            "login": dict(login_state)}


# ---------- 로그인 ----------
def start_login():
    """구글 로그인 주소를 돌려주고, 로그인이 끝나 돌아올 127.0.0.1:53682를 잠시 연다(10분).
    리디렉션이 127.0.0.1이라 서버 PC의 브라우저에서 로그인해야 한다."""
    cid, sec = client()
    state = secrets.token_urlsafe(16)
    done = {"v": False}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if q.get("state") != state:
                return self._page(400, "잘못된 요청입니다.")
            if q.get("error"):
                login_state["error"] = "로그인이 취소되었거나 거부되었습니다: " + q["error"]
                done["v"] = True
                return self._page(400, login_state["error"])
            try:
                tok = _post_form(TOKEN_URL, {"code": q.get("code", ""), "client_id": cid, "client_secret": sec,
                                             "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
                if not tok.get("refresh_token"):
                    raise RuntimeError("갱신 토큰을 받지 못했습니다. 다시 연결해 주세요")
                tok["expires_at"] = time.time() + tok.get("expires_in", 3600)
                _save(tok)
                try:
                    tok["channel"] = channel_title()
                    _save(tok)
                except Exception as e:  # noqa  채널 이름을 못 읽어도 연결은 된 것
                    tok["channel"] = None
                    login_state["error"] = str(e)
                self._page(200, f"유튜브 채널 \"{tok.get('channel') or '?'}\"에 연결되었습니다. 이 창을 닫아도 됩니다.")
            except Exception as e:  # noqa
                login_state["error"] = str(e)
                self._page(500, str(e))
            done["v"] = True

        def _page(self, code, msg):
            body = f"<!doctype html><meta charset=utf-8><body style='font-family:sans-serif;padding:40px'>{msg}".encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if login_state["busy"]:
        raise RuntimeError("이미 로그인 창이 열려 있습니다. 끝내거나 10분 뒤에 다시 시도하세요")
    try:
        srv = HTTPServer(("127.0.0.1", REDIRECT_PORT), H)
    except OSError:
        raise RuntimeError(f"{REDIRECT_PORT}번 포트를 쓰고 있습니다(rclone 로그인 중인지 확인하세요)")
    srv.timeout = 1
    login_state.update(busy=True, error=None)

    def serve():
        end = time.time() + 600
        try:
            while not done["v"] and time.time() < end:
                srv.handle_request()
        finally:
            srv.server_close()
            login_state["busy"] = False
    threading.Thread(target=serve, daemon=True).start()
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPES, "state": state,
        "access_type": "offline", "prompt": "consent select_account"})


# ---------- API ----------
def _req(method, url, body=None, data=None, headers=None, ok=(200, 201)):
    h = {"Authorization": "Bearer " + access_token()}
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json; charset=UTF-8"
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        if e.code in ok:  # 이어 올리기의 308
            return e.code, e.headers, e.read()
        raw = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(raw)["error"]
            msg, reason = err.get("message", raw), (err.get("errors") or [{}])[0].get("reason", "")
        except (ValueError, KeyError, TypeError):
            msg, reason = raw[:300], ""
        if reason in QUOTA_REASONS:
            raise QuotaExceeded(msg)
        raise ApiError(e.code, msg)


def _json(method, url, body=None):
    _, _, raw = _req(method, url, body=body)
    return json.loads(raw or b"{}")


def channel_title():
    items = _json("GET", API + "/channels?part=snippet&mine=true").get("items") or []
    if not items:
        raise RuntimeError("이 구글 계정에는 유튜브 채널이 없습니다")
    return items[0]["snippet"]["title"]


def channel_uploads():
    """내 채널에 올린 영상 전체(비공개 포함). [{"id", "title", "privacy"}] 50개당 1단위."""
    ch = _json("GET", API + "/channels?part=contentDetails&mine=true").get("items") or []
    if not ch:
        return []
    up = ch[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    out, page = [], ""
    while True:
        r = _json("GET", API + f"/playlistItems?part=snippet,status&playlistId={up}&maxResults=50"
                  + (f"&pageToken={page}" if page else ""))
        for it in r.get("items", []):
            out.append({"id": it["snippet"]["resourceId"]["videoId"], "title": it["snippet"]["title"],
                        "privacy": it.get("status", {}).get("privacyStatus")})
        page = r.get("nextPageToken")
        if not page:
            return out


def in_playlist(playlist, video):
    try:
        r = _json("GET", API + f"/playlistItems?part=id&playlistId={playlist}&videoId={video}")
    except ApiError as e:
        if e.code == 404:  # 방금 만든 재생목록은 잠시 "없음"으로 답한다
            return False
        raise
    return bool(r.get("items"))


def has_captions(video, language="ko"):
    """이미 그 언어 자막이 있는지(50단위)."""
    r = _json("GET", API + f"/captions?part=snippet&videoId={video}")
    return any(c["snippet"].get("language", "").split("-")[0] == language for c in r.get("items", []))


def upload_video(path, title, description="", privacy="private", progress=None, cancel=None, tags=None):
    """영상을 이어 올리기 방식으로 올리고 영상 id를 돌려준다. 중단하면 None."""
    size = os.path.getsize(path)
    meta = {"snippet": {"title": title[:100], "description": description, "tags": tags or [], "categoryId": "22",
                        "defaultLanguage": "ko", "defaultAudioLanguage": "ko"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    _, h, _ = _req("POST", UPLOAD + "/videos?uploadType=resumable&part=snippet,status", body=meta,
                   headers={"X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"})
    loc = h["Location"]
    off, fails = 0, 0
    with open(path, "rb") as f:
        while True:
            if cancel and cancel():
                return None
            f.seek(off)
            chunk = f.read(CHUNK)
            try:
                code, h, raw = _req("PUT", loc, data=chunk, ok=(200, 201, 308), headers={
                    "Content-Type": "video/mp4", "Content-Range": f"bytes {off}-{off + len(chunk) - 1}/{size}"})
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                fails += 1
                if fails > 5:
                    raise RuntimeError(f"유튜브에 올리는 중 연결이 계속 끊겼습니다: {e}")
                time.sleep(5 * fails)
                code, h, raw = _req("PUT", loc, data=b"", ok=(200, 201, 308),
                                    headers={"Content-Range": f"bytes */{size}"})
            if code in (200, 201):
                return json.loads(raw)["id"]
            rng = h.get("Range")
            off = int(rng.rsplit("-", 1)[1]) + 1 if rng else 0
            if progress:
                progress(off, size)


def playlist_id(title):
    """내 채널에서 제목이 같은 재생목록을 찾고, 없으면 비공개로 만든다."""
    page = ""
    while True:
        r = _json("GET", API + "/playlists?part=snippet&mine=true&maxResults=50" + (f"&pageToken={page}" if page else ""))
        for it in r.get("items", []):
            if it["snippet"]["title"] == title:
                return it["id"]
        page = r.get("nextPageToken")
        if not page:
            break
    return _json("POST", API + "/playlists?part=snippet,status",
                 {"snippet": {"title": title}, "status": {"privacyStatus": "private"}})["id"]


def add_to_playlist(playlist, video):
    for attempt in range(4):
        try:
            _json("POST", API + "/playlistItems?part=snippet",
                  {"snippet": {"playlistId": playlist, "resourceId": {"kind": "youtube#video", "videoId": video}}})
            return
        except ApiError as e:
            if e.code != 404 or attempt == 3:  # 방금 만든 재생목록이 아직 안 보이면 잠시 뒤 다시
                raise
            time.sleep(10 * (attempt + 1))


def upload_captions(video, srt_path, language="ko", name="한국어"):
    boundary = "dubber" + secrets.token_hex(8)
    meta = json.dumps({"snippet": {"videoId": video, "language": language, "name": name, "isDraft": False}})
    with open(srt_path, "rb") as f:
        srt = f.read()
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
            f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + srt + f"\r\n--{boundary}--\r\n".encode()
    _req("POST", UPLOAD + "/captions?uploadType=multipart&part=snippet", data=body,
         headers={"Content-Type": f"multipart/related; boundary={boundary}"})
