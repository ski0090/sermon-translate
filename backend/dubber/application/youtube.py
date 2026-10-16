"""유튜브 유스케이스: 올리기 대기열(전체 영상, 쇼츠, 음성 영상), 설명·해시태그 설정, 채널에 이미 있는 영상 찾기.
대기열 맨 앞부터 하나씩 올리고, 할당량이 다 떨어지면 다음 날까지 기다렸다가 이어 간다(_youtube.json)."""
import datetime
import os
import posixpath
import threading
import time
import traceback

from ..domain import outputs
from ..domain import youtube as rules
from ..domain.errors import QuotaExceeded
from ..domain.youtube import PRIVACY, SHORT_KEY, SLEEP_KEY

STATE = "_youtube.json"
CHANNEL_TTL = 900  # 채널 영상 목록을 다시 읽는 간격(초). 50개당 1단위라 15분이면 하루 100단위쯤


def quota_reset():
    """유튜브 할당량이 다시 채워지는 시각(태평양 시간 자정) 조금 뒤."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
        return (now + datetime.timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0).timestamp()
    except Exception:  # noqa  시간대 정보가 없으면 한 시간 뒤에 다시 해 본다
        return time.time() + 3600


class YouTubeService:
    def __init__(self, platform, store, projects, drive, playlist, library_root, temp_dir):
        self.platform = platform  # ports.VideoPlatform
        self.store = store        # ports.StateStore
        self.projects = projects  # application.projects.ProjectService
        self.drive = drive        # ports.CloudDrive
        self.playlist = playlist  # 재생목록 이름(DUBBER_YT_PLAYLIST)
        self.library_root = library_root
        self.temp_dir = temp_dir  # 드라이브에서 받아 올린 뒤 지울 파일을 두는 곳
        self.library = None       # 드라이브 목록(bootstrap이 끼운다)
        self.shorts = None        # 쇼츠(bootstrap이 끼운다)
        self.sleep = None         # 음성 영상(bootstrap이 끼운다)
        self._yt = {"items": {}, "queue": [], "settings": {}}
        self._lock = threading.RLock()
        self._run = {"thread": None, "cancel": set()}
        self._ch = {"t": 0.0, "videos": None, "busy": False}
        self._ch_lock = threading.Lock()

    @property
    def items(self):
        """대기열 이름(드라이브 경로, short:..., sleep:...) -> 올리기 상태."""
        return self._yt["items"]

    # ---------- 연결과 설정 ----------
    def status(self):
        return dict(self.platform.status(), playlist=self.playlist, privacy=PRIVACY)

    def connected(self):
        return self.platform.status()["connected"]

    def login(self):
        return self.platform.start_login()

    def settings(self):
        return rules.settings(self._yt["settings"])

    def settings_view(self):
        return dict(self.settings(), preview=rules.meta(self.settings(), rules.PREVIEW_NAME)[0])

    def save_settings(self, body):
        with self._lock:
            for k in rules.DEFAULTS:
                if k in body:
                    self._yt["settings"][k] = str(body[k])
            self._save()

    def _save(self):
        with self._lock:
            self.store.write(STATE, self._yt)

    # ---------- 대기열 ----------
    def enqueue(self, path):
        with self._lock:
            st = self._yt["items"].setdefault(path, {})
            if path in self._yt["queue"]:
                return st
            if st.get("status") == "done":
                raise RuntimeError("이미 유튜브에 올린 영상입니다")
            self._run["cancel"].discard(path)
            st.update(status="queued", error=None, msg="올리기 대기 중", progress=0.0, resumed=False)
            q, at = self._yt["queue"], len(self._yt["queue"])
            if not path.startswith(SHORT_KEY):  # 전체 영상은 기다리는 쇼츠보다 먼저 올린다(올리는 중인 것은 그대로)
                busy = bool(self._run["thread"] and self._run["thread"].is_alive())
                at = next((k for k, x in enumerate(q) if x.startswith(SHORT_KEY) and not (k == 0 and busy)), len(q))
            q.insert(at, path)
            self._save()
        self._kick()
        return st

    def cancel(self, path):
        with self._lock:
            if path not in self._yt["queue"]:
                return
            if self._yt["queue"][0] == path and self._run["thread"] and self._run["thread"].is_alive():
                self._run["cancel"].add(path)  # 올리는 중이면 다음 조각에서 멈춘다
                self._yt["items"][path]["msg"] = "중단하는 중"
            else:
                self._yt["queue"].remove(path)
                self._yt["items"][path].update(status="cancelled", msg="")
                self._save()

    def _kick(self):
        with self._lock:
            t = self._run["thread"]
            if t and t.is_alive():
                return
            self._run["thread"] = threading.Thread(target=self._worker, daemon=True)
            self._run["thread"].start()

    def _worker(self):
        """대기열 맨 앞 영상부터 하나씩 올린다. 할당량이 다 떨어지면 다음 날까지 기다렸다가 이어 간다."""
        while True:
            with self._lock:
                if not self._yt["queue"]:
                    return
                path = self._yt["queue"][0]
                st = self._yt["items"][path]
            cancelled = lambda: path in self._run["cancel"]  # noqa
            try:
                (self._upload_short if path.startswith(SHORT_KEY) else self._upload_sleep
                 if path.startswith(SLEEP_KEY) else self._upload_one)(path, st, cancelled)
                st.update(status="cancelled" if cancelled() else "done", msg="", error=None)
            except QuotaExceeded:
                until = quota_reset()
                st.update(status="queued", msg="오늘 유튜브 할당량을 다 썼습니다. "
                          + time.strftime("%m월 %d일 %H:%M", time.localtime(until)) + "에 이어서 올립니다")
                self._save()
                while time.time() < until and not cancelled():
                    time.sleep(max(0.5, min(30, until - time.time())))
                if not cancelled():
                    continue
                st.update(status="cancelled", msg="")
            except Exception as e:  # noqa
                traceback.print_exc()
                st.update(status="error", error=str(e), msg="")
            with self._lock:
                if self._yt["queue"] and self._yt["queue"][0] == path:
                    self._yt["queue"].pop(0)
                self._run["cancel"].discard(path)
                self._save()

    def resume(self):
        """서버가 켜질 때 대기열을 이어 간다. 올리다 끊긴 영상은 처음부터 다시 올린다(유튜브에 영상이 생기기 전이라
        중복되지 않는다)."""
        saved = self.store.read(STATE)
        if saved:
            self._yt.update(saved)
        if self._yt["queue"]:
            head = self._yt["items"].get(self._yt["queue"][0], {})
            if head.get("status") == "uploading":
                head.update(resumed=True)
            for p in self._yt["queue"]:
                self._yt["items"].setdefault(p, {})["status"] = "queued"
            print("유튜브 올리기 대기열을 이어 갑니다:", len(self._yt["queue"]), "개", flush=True)
            self._kick()

    # ---------- 채널에 이미 있는 영상 ----------
    def _refresh_channel(self):
        try:
            self._ch["videos"] = self.platform.channel_uploads()
        except Exception as e:  # noqa  연결 안 됨, 네트워크 등: 다음에 다시 읽는다
            print("유튜브 채널 영상 목록을 읽지 못했습니다:", e, flush=True)
        finally:
            self._ch["t"], self._ch["busy"] = time.time(), False

    def channel_videos(self, force=False):
        """채널에 이미 있는 영상(직접 올린 것 포함)을 이름으로 찾기 위한 목록. 뒤에서 가끔 새로 읽는다."""
        if not self.connected():
            return []
        with self._ch_lock:
            start = (force or time.time() - self._ch["t"] > CHANNEL_TTL) and not self._ch["busy"]
            if start:
                self._ch["busy"] = True
        if start:
            if force or self._ch["videos"] is None:
                self._refresh_channel()
            else:
                threading.Thread(target=self._refresh_channel, daemon=True).start()
        return self._ch["videos"] or []

    def full_url(self, p, look_channel=False):
        """프로젝트의 전체 더빙 영상이 유튜브에 있으면 그 주소."""
        path = (p.data.get("drive") or {}).get("path")
        full = (self._yt["items"].get(path) or {}).get("url") if path else None
        if not full and look_channel:
            ex = rules.existing(p.name, self.channel_videos())
            full = ex and ex["url"]
        return full

    # ---------- 올리기 ----------
    def _source(self, path, st, cancel, need_video):
        """올릴 더빙 영상과 자막. 이 PC의 결과물을 먼저 쓰고, 없으면 드라이브의 결과 폴더에서 받는다.
        영상이 이미 유튜브에 있으면(need_video=False) 자막만 찾는다. (영상 또는 None, 자막 또는 None, 다 올린 뒤 지울 파일들)"""
        pid = self.projects.by_drive(path)
        if pid:
            p, _ = self.projects.get(pid)
            ex = [f for f in p.data.get("last_export") or [] if os.path.isfile(f)]
            video = next((f for f in ex if f.endswith(outputs.DUBBED)), None)
            if video or not need_video:
                return video, next((f for f in ex if f.endswith(".srt")), None), []
        sizes = {f["path"]: f["size"] for f in self.library.files()}
        stem = os.path.splitext(posixpath.basename(path))[0]

        def prog(done, total, speed):
            st["msg"] = f"구글 드라이브에서 더빙 영상을 받는 중 ({done / 2**20:,.0f} / {total / 2**20:,.0f}MB)"
        for folder in (outputs.out_name(stem), stem + "/out"):
            rel, srt_rel = f"{folder}/{outputs.dubbed(stem)}", f"{folder}/{stem}.srt"
            if rel not in sizes and srt_rel not in sizes:
                continue
            video = None
            if need_video:
                if rel not in sizes:
                    continue
                video = self.drive.download(f"{self.library_root}/{rel}", self.temp_dir, sizes[rel], progress=prog,
                                            cancel=cancel)
            srt = self.drive.download(f"{self.library_root}/{srt_rel}", self.temp_dir, sizes[srt_rel],
                                      cancel=cancel) if srt_rel in sizes else None
            return video, srt, [f for f in (video, srt) if f]
        if need_video:
            raise RuntimeError("더빙된 영상(mp4)을 찾지 못했습니다")
        return None, None, []

    def _upload_one(self, path, st, cancel):
        """영상 올리기 -> 재생목록 -> 자막. 끝난 부분은 기록해 두어 다시 해도 건너뛴다(영상을 두 번 올리지 않게).
        채널에 같은 이름의 영상이 이미 있으면(직접 올린 것 포함) 올리지 않고 그 영상에 재생목록과 자막만 더한다."""
        def save(**kw):
            st.update(**kw)
            self._save()
        stem = os.path.splitext(posixpath.basename(path))[0]
        if not st.get("video_id"):
            save(status="uploading", msg="유튜브에 같은 영상이 있는지 확인하는 중")
            ex = rules.existing(stem, self.channel_videos(force=True))
            if ex:
                save(video_id=ex["id"], url=ex["url"], title=ex["title"], privacy=ex["privacy"], existing=True)
        need_video = not st.get("video_id")
        need_caps = st.get("captions") not in ("done", "none", "existing")
        temp = []
        try:
            video = srt = None
            if need_video or need_caps:
                save(status="uploading", msg="올릴 파일을 준비하는 중")
                video, srt, temp = self._source(path, st, cancel, need_video)
                if cancel():
                    return
            if need_video:
                def prog(done, total):
                    st["progress"] = done / total
                    st["msg"] = f"유튜브에 올리는 중 ({done / 2**20:,.0f} / {total / 2**20:,.0f}MB)"
                save(msg="유튜브에 올리는 중", progress=0.0)
                desc, tags = rules.meta(self.settings(), stem)
                title = f"{stem} (한국어 더빙)"
                vid = self.platform.upload_video(video, title, description=desc, tags=tags, privacy=PRIVACY,
                                                 progress=prog, cancel=cancel)
                if vid is None:
                    return
                save(video_id=vid, url=rules.video_url(vid), title=title, privacy=PRIVACY, uploaded=time.time(),
                     progress=1.0)
                self._ch["t"] = 0  # 다음 목록 새로고침 때 채널 목록도 다시 읽는다
            if not st.get("playlist"):
                save(msg=f"재생목록 \"{self.playlist}\"에 넣는 중")
                pl = self.platform.playlist_id(self.playlist)
                if not self.platform.in_playlist(pl, st["video_id"]):
                    self.platform.add_to_playlist(pl, st["video_id"])
                save(playlist=self.playlist)
            if need_caps:
                if srt and st.get("existing") and self.platform.has_captions(st["video_id"]):
                    save(captions="existing")  # 직접 올린 영상에 이미 한국어 자막이 있으면 덮지 않는다
                elif srt:
                    save(msg="한국어 자막을 올리는 중")
                    self.platform.upload_captions(st["video_id"], srt)
                    save(captions="done")
                else:
                    save(captions="none")
        finally:
            for f in temp:
                if os.path.exists(f):
                    os.remove(f)

    def _upload_file(self, st, f, title, desc, tags, url, cancel):
        """만든 파일(쇼츠, 음성 영상) 하나를 올린다."""
        def prog(done, total):
            st["progress"] = done / total
            st["msg"] = f"유튜브에 올리는 중 ({done / 2**20:,.0f} / {total / 2**20:,.0f}MB)"
        st.update(status="uploading", msg="유튜브에 올리는 중", progress=0.0)
        self._save()
        vid = self.platform.upload_video(f, title, description=desc, tags=tags, privacy=PRIVACY, progress=prog,
                                         cancel=cancel)
        if vid is None:
            return
        st.update(video_id=vid, url=url(vid), title=title, privacy=PRIVACY, uploaded=time.time(), progress=1.0)
        self._save()

    def _upload_short(self, key, st, cancel):
        pid, sid = key[len(SHORT_KEY):].rsplit(":", 1)
        p, it = self.shorts.ready_item(pid, int(sid))
        if st.get("video_id"):
            return
        title, desc, tags = rules.short_meta(self.settings(), p.name, it, self.full_url(p, look_channel=True))
        self._upload_file(st, it["file"], title, desc, tags, rules.short_url, cancel)

    def _upload_sleep(self, key, st, cancel):
        pid = key[len(SLEEP_KEY):]
        p, _ = self.projects.get(pid)
        f = self.sleep.video_path(p)
        if not os.path.isfile(f):
            raise RuntimeError("만든 음성 영상이 없습니다")
        if st.get("video_id"):
            return
        title, desc, tags = rules.sleep_meta(self.settings(), p.name, self.full_url(p))
        self._upload_file(st, f, title, desc, tags, rules.video_url, cancel)
