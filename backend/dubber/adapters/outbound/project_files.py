"""프로젝트 저장소(ports.ProjectRepository): projects/<프로젝트>/project.json과 그 폴더의 작업 파일."""
import json
import os
import tempfile

from ...domain.errors import NotFound
from ...domain.project import Project, summary


class FileWorkspace:
    def __init__(self, root):
        self.root = root

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def ensure(self, *parts):
        p = os.path.join(self.root, *parts)
        os.makedirs(p, exist_ok=True)
        return p


class FileProjectRepository:
    def __init__(self, root):
        self.root = root
        self._summary_cache = {}  # project.json 경로 -> (수정 시각, 크기, 요약). 바뀐 파일만 다시 읽는다

    def _file(self, pid):
        if not pid or pid in (".", "..") or "/" in pid or "\\" in pid:
            raise NotFound(f"프로젝트를 찾지 못했습니다: {pid}")
        return os.path.join(self.root, pid, "project.json")

    def _summary(self, d, p):
        st = os.stat(p)
        hit = self._summary_cache.get(p)
        if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
            return hit[2]
        with open(p, encoding="utf-8") as f:
            j = json.load(f)
        out = summary(d, j, st.st_mtime)
        self._summary_cache[p] = (st.st_mtime, st.st_size, out)
        return out

    def summaries(self):
        out = []
        if not os.path.isdir(self.root):
            return out
        for d in os.listdir(self.root):
            p = os.path.join(self.root, d, "project.json")
            if os.path.exists(p):
                try:
                    out.append(dict(self._summary(d, p)))
                except Exception:  # noqa  고장 난 프로젝트는 목록에서 뺀다
                    pass
        out.sort(key=lambda x: -x["updated"])
        return out

    def exists(self, pid):
        try:
            return os.path.exists(self._file(pid))
        except NotFound:
            return False

    def load(self, pid):
        path = self._file(pid)
        if not os.path.exists(path):
            raise NotFound(f"프로젝트를 찾지 못했습니다: {pid}")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return Project(pid, data, stamp=os.path.getmtime(path))

    def is_stale(self, project):
        return os.path.getmtime(self._file(project.id)) > (project.stamp or 0) + 0.5

    def save(self, project):
        d = os.path.join(self.root, project.id)
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(project.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(d, "project.json"))
        project.stamp = os.path.getmtime(os.path.join(d, "project.json"))

    def create(self, folder, data):
        d = os.path.join(self.root, folder)
        n = 2
        while os.path.exists(d):
            d = os.path.join(self.root, f"{folder}_{n}")
            n += 1
        os.makedirs(d)
        with open(os.path.join(d, "project.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return self.load(os.path.basename(d))

    def workspace(self, pid):
        return FileWorkspace(os.path.join(self.root, pid))

    def area(self, name):
        p = os.path.join(self.root, name)
        os.makedirs(p, exist_ok=True)
        return p
