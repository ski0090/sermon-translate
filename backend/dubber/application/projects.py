"""프로젝트 유스케이스: 불러오기(메모리에 두고 프로젝트마다 잠금), 만들기, 문장·설정·자막 영역·잘라내기 고치기, 파일."""
import os
import threading

from ..domain import placement
from ..domain.captions import even_roi
from ..domain.errors import NotFound
from ..domain.project import folder_name, new_data


class ProjectService:
    def __init__(self, repo, jobs, video):
        self.repo = repo    # ports.ProjectRepository
        self.jobs = jobs    # application.jobs.JobBoard
        self.video = video  # ports.VideoAnalyzer
        self._projects = {}
        self._locks = {}
        self._lock = threading.Lock()

    def get(self, pid):
        """(프로젝트, 잠금). 다른 프로세스(명령줄 실행)가 파일을 바꿨으면 다시 읽는다. 작업 중일 때는 메모리의 것을
        유지한다."""
        with self._lock:
            if not self.repo.exists(pid):
                raise NotFound(f"프로젝트를 찾지 못했습니다: {pid}")
            job = self.jobs.get(pid)
            cur = self._projects.get(pid)
            external = cur is not None and self.repo.is_stale(cur)
            if cur is None or (external and not (job and not job.done)):
                self._projects[pid] = self.repo.load(pid)
                self._locks.setdefault(pid, threading.RLock())
            return self._projects[pid], self._locks[pid]

    def save(self, p):
        self.repo.save(p)

    def workspace(self, pid):
        return self.repo.workspace(pid)

    def summaries(self):
        return self.repo.summaries()

    def exists(self, pid):
        return self.repo.exists(pid)

    def by_drive(self, path):
        """드라이브 경로로 만든 프로젝트의 id."""
        return next((it["dir"] for it in self.repo.summaries() if it.get("drive") == path), None)

    def create(self, video, extra=None):
        """영상으로 새 프로젝트를 만든다. 영상이 아니면 probe에서 실패하므로 빈 폴더를 남기지 않도록 먼저 읽는다."""
        name = os.path.splitext(os.path.basename(video))[0]
        info = self.video.probe(video)
        return self.repo.create(folder_name(name), new_data(name, video, info, extra))

    def _edit(self, pid, fn):
        p, lock = self.get(pid)
        with lock:
            out = fn(p)
            self.save(p)
            return out

    # ---------- 고치기 ----------
    def update_sentence(self, pid, sid, fields):
        return self._edit(pid, lambda p: p.update_sentence(sid, **fields))

    def split_sentence(self, pid, sid, cap):
        return self._edit(pid, lambda p: p.split_sentence(sid, cap))

    def merge_next(self, pid, sid):
        return self._edit(pid, lambda p: p.merge_next(sid))

    def delete_sentence(self, pid, sid):
        self._edit(pid, lambda p: p.delete_sentence(sid))

    def set_roi(self, pid, body):
        """자막 영역: auto면 자동 감지, 아니면 x, y, w, h를 짝수로 맞춰 화면 안에 넣는다."""
        def fn(p):
            if body.get("auto"):
                p.set_roi(self.video.detect_band(p.data["video"], p.data["info"]))
            else:
                p.set_roi(even_roi({k: int(body[k]) for k in ("x", "y", "w", "h")},
                                   p.data["info"]["width"], p.data["info"]["height"]))
            return p.data["roi"]
        return self._edit(pid, fn)

    def apply_settings(self, pid, body):
        return self._edit(pid, lambda p: p.apply_settings(body))

    def set_cuts(self, pid, cuts):
        return self._edit(pid, lambda p: {"cuts": p.set_cuts(cuts), "sentences": p.data["sentences"]})

    def plan(self, pid):
        return placement.plan(self.get(pid)[0])

    def frame(self, pid, t, with_roi=False):
        p, _ = self.get(pid)
        return self.video.frame(p.data["video"], t, p.data.get("roi") if with_roi else None)

    # ---------- 파일 ----------
    def video_file(self, pid):
        return self.get(pid)[0].data["video"]

    def crop_file(self, pid, name):
        return self.workspace(pid).path("crops", os.path.basename(name))

    def tts_file(self, pid, name):
        return self.workspace(pid).path("tts", os.path.basename(name))

    def export_file(self, pid, path):
        """내보낸 파일 가운데 하나(그 밖의 경로는 NotFound)."""
        p, _ = self.get(pid)
        if not (path and os.path.abspath(path) in [os.path.abspath(x) for x in p.data.get("last_export", [])]):
            raise NotFound("없는 파일")
        return path
