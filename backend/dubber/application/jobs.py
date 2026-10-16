"""작업: 오래 걸리는 일 하나의 진행 상태. 키(프로젝트, 드라이브 받기)마다 하나씩만 돌린다."""
import threading
import time
import traceback

from ..domain.errors import Conflict


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


class JobBoard:
    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()

    def get(self, key):
        return self._jobs.get(key)

    def running(self, key):
        j = self._jobs.get(key)
        return j if j and not j.done else None

    def start(self, key, kind, fn):
        """fn(job)을 뒤에서 돌린다. 그 키의 작업이 이미 돌고 있으면 Conflict."""
        with self._lock:
            j = self._jobs.get(key)
            if j and not j.done:
                raise Conflict("이미 진행 중인 작업이 있습니다")
            job = Job(kind)
            self._jobs[key] = job

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

    def wait(self, key):
        """그 키의 작업이 끝날 때까지 기다리고 마지막 작업을 돌려준다."""
        while True:
            j = self._jobs.get(key)
            if not j or j.done:
                return j
            time.sleep(5)
