"""구글 드라이브 영상 받기 유스케이스: 고른 영상을 받아 프로젝트를 만든다.
받는 중이라는 표시를 남겨, 서버가 중간에 꺼지면 다시 켤 때 처음부터 받는다."""
import os

JOB = "_drive"  # 작업 판에서 드라이브 받기를 가리키는 키
DIR = "_drive"  # 받은 영상을 두는 공용 폴더
MARK = "_drive/_import.json"  # 받는 중인 영상


class DriveImportService:
    def __init__(self, drive, projects, jobs, store, repo):
        self.drive = drive        # ports.CloudDrive
        self.projects = projects  # application.projects.ProjectService
        self.jobs = jobs          # application.jobs.JobBoard
        self.store = store        # ports.StateStore
        self.repo = repo          # ports.ProjectRepository(공용 폴더)

    @property
    def dir(self):
        return self.repo.area(DIR)

    def job(self):
        return self.jobs.get(JOB)

    def status(self):
        j = self.jobs.get(JOB)
        return {"available": self.drive.available(), "job": j.status() if j else None}

    def list_dir(self, path, shared):
        return self.drive.list_dir(path, shared)

    def start(self, params, resumed=False):
        """받기를 시작한다. 이미 받는 영상이 있으면 domain.errors.Conflict."""
        def fn(job):
            self.store.write(MARK, params)
            try:
                return self._run(job, params)
            finally:
                self.store.remove(MARK)
        j = self.jobs.start(JOB, "drive", fn)
        j.target, j.resumed = params.get("path", "").strip("/"), resumed
        return j

    def cancel(self):
        j = self.jobs.get(JOB)
        if j and not j.done:
            j.cancelled = True
            j.msg = "중단하는 중"
        return j.status() if j else None

    def _run(self, job, params):
        """구글 드라이브 영상을 받아 프로젝트를 만든다. 결과는 새 프로젝트 id."""
        def prog(done, total, speed):
            job.progress = 0.97 * done / total
            job.msg = f"구글 드라이브에서 내려받는 중 ({done / 2**20:,.0f} / {total / 2**20:,.0f}MB, {speed / 2**20:.1f}MB/s)"
        job.msg = "구글 드라이브에서 내려받는 중"
        local = self.drive.download(params["path"], self.dir, int(params.get("size") or -1), bool(params.get("shared")),
                                    progress=prog, cancel=lambda: job.cancelled)
        if local is None:
            return None
        job.msg = "프로젝트를 만드는 중"
        p = self.projects.create(local, {"drive": {"path": params["path"].strip("/"), "shared": bool(params.get("shared"))}})
        return {"id": p.id}

    def resume(self):
        """끊긴 내려받기의 조각 파일을 지우고, 받던 영상이 있으면 처음부터 다시 받는다."""
        d = self.dir
        for f in os.listdir(d):
            if f.endswith(".partial"):
                os.remove(os.path.join(d, f))
        params = self.store.read(MARK)
        if params is not None:
            print("구글 드라이브에서 받던 영상을 처음부터 다시 받습니다:", params.get("path"), flush=True)
            self.start(params, resumed=True)
