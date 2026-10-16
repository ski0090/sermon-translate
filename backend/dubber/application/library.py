"""영상 목록 유스케이스: 구글 드라이브 목록 폴더(기본 JP)의 영상마다 진행 상태를 붙인다.
드라이브 목록은 TTL초마다 뒤에서 새로 읽는다."""
import threading
import time

from ..domain import library as rules

TTL = 60


class LibraryService:
    def __init__(self, drive, pipeline, importer, root):
        self.drive = drive        # ports.CloudDrive
        self.pipeline = pipeline  # 프로젝트 목록(작업 상태 포함)
        self.importer = importer  # 받는 중인 영상
        self.root = root          # 목록 폴더(DUBBER_LIBRARY)
        self.youtube = None       # 유튜브 상태와 채널 영상(bootstrap이 끼운다)
        self.batch = None         # 자동 진행 상태(bootstrap이 끼운다)
        self._lib = {"t": 0.0, "files": None, "error": None, "busy": False}
        self._lock = threading.Lock()

    def _refresh(self):
        try:
            self._lib["files"], self._lib["error"] = self.drive.list_library(self.root), None
        except Exception as e:  # noqa
            self._lib["error"] = str(e)
        finally:
            self._lib["t"], self._lib["busy"] = time.time(), False

    @property
    def busy(self):
        return self._lib["busy"]

    def files(self):
        """드라이브 목록(아직 한 번도 읽지 않았으면 기다려서 읽는다)."""
        if self._lib["files"] is None:
            self._refresh()
        return self._lib["files"] or []

    def view(self, force=False):
        with self._lock:
            start = (force or time.time() - self._lib["t"] > TTL) and not self._lib["busy"]
            if start:
                self._lib["busy"] = True
        if start:
            if self._lib["files"] is None:
                self._refresh()  # 처음 한 번은 기다린다
            else:
                threading.Thread(target=self._refresh, daemon=True).start()
        imp = self.importer.job()
        importing = imp.target if imp and not imp.done else None
        items, others = rules.build(self.root, self._lib["files"] or [], self.pipeline.summaries(), importing,
                                    imp.status() if importing else None, self.youtube.items,
                                    self.batch.items, self.youtube.channel_videos(force))
        return {"root": self.root, "items": items, "others": others, "error": self._lib["error"],
                "loading": self._lib["files"] is None}
