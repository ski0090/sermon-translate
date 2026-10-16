"""작은 상태 파일(ports.StateStore): 프로젝트들이 있는 폴더 아래의 JSON 파일. 다 쓴 뒤 바꿔 넣는다."""
import json
import os
import tempfile


class JsonStateStore:
    def __init__(self, root):
        self.root = root

    def _path(self, key):
        return os.path.join(self.root, *key.split("/"))

    def read(self, key, default=None):
        try:
            with open(self._path(key), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    def write(self, key, obj, indent=None):
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=os.path.basename(path) + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=indent)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def exists(self, key):
        return os.path.exists(self._path(key))

    def remove(self, key):
        if os.path.exists(self._path(key)):
            os.remove(self._path(key))
