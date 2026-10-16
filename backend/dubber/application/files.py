"""상태 파일 고치기: 프로젝트마다 잠금을 두고 읽고-고치고-쓴다(쇼츠, 음성 영상 상태)."""
import threading


class ProjectLocks:
    def __init__(self):
        self._locks = {}
        self._lock = threading.Lock()

    def __call__(self, pid):
        with self._lock:
            return self._locks.setdefault(pid, threading.RLock())


def change(store, lock, key, empty, fn):
    """key의 상태를 읽고 fn(상태)로 고친 뒤 저장한다. 없으면 empty()로 시작한다. fn의 반환값을 돌려준다."""
    with lock:
        st = store.read(key) or empty()
        out = fn(st)
        store.write(key, st, indent=1)
        return out
