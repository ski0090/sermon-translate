"""구글 드라이브에서 영상을 둘러보고 내려받는다. rclone 명령줄 도구와 `rclone config`로 만든 리모트(기본 이름 gdrive)를 쓴다.
리모트 이름은 환경 변수 DUBBER_GDRIVE로 바꾼다."""
import glob
import json
import os
import shutil
import subprocess

REMOTE = os.environ.get("DUBBER_GDRIVE", "gdrive").rstrip(":") + ":"
VIDEO_EXT = (".mp4", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".ts")


def _run(args, timeout=120):
    return subprocess.run(["rclone", *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


def _flags(shared):
    # 공유 문서함(다른 사람이 공유한 파일)은 별도 플래그로 본다
    return ["--drive-shared-with-me"] if shared else []


def _err(stderr):
    lines = [x.strip() for x in (stderr or "").splitlines() if x.strip()]
    return lines[-1] if lines else "알 수 없는 오류"


def available():
    if not shutil.which("rclone"):
        return False
    try:
        r = _run(["listremotes"], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return REMOTE in r.stdout.split()


def list_dir(path="", shared=False):
    """폴더와 영상 파일만 돌려준다. 폴더가 먼저, 이름순."""
    r = _run(["lsjson", REMOTE + path.strip("/"), "--no-mimetype", *_flags(shared)])
    if r.returncode:
        raise RuntimeError("구글 드라이브 목록을 읽지 못했습니다: " + _err(r.stderr))
    items = []
    for it in json.loads(r.stdout or "[]"):
        if it.get("IsDir"):
            items.append({"name": it["Name"], "dir": True})
        elif it["Name"].lower().endswith(VIDEO_EXT):
            items.append({"name": it["Name"], "dir": False, "size": it.get("Size", -1)})
    items.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    return items


def _local_path(dest_dir, name, size):
    """같은 이름·같은 크기의 파일은 이미 받은 것으로 보고 다시 쓴다. 이름만 같으면 다른 프로젝트의 영상을 덮지 않도록 새 이름을 붙인다."""
    base, ext = os.path.splitext(name)
    local, n = os.path.join(dest_dir, name), 2
    while os.path.exists(local) and os.path.getsize(local) != size:
        local = os.path.join(dest_dir, f"{base}_{n}{ext}")
        n += 1
    return local


def download(path, dest_dir, size, shared=False, progress=None, cancel=None):
    """드라이브의 영상 하나를 dest_dir에 받고 로컬 경로를 돌려준다. 중단하면 None.
    progress(받은 바이트, 전체 바이트, 초당 바이트)"""
    os.makedirs(dest_dir, exist_ok=True)
    local = _local_path(dest_dir, os.path.basename(path.rstrip("/")), size)
    if os.path.isfile(local):
        return local
    proc = subprocess.Popen(["rclone", "copyto", REMOTE + path.strip("/"), local, "--stats", "1s",
                             "--stats-log-level", "NOTICE", "--use-json-log", *_flags(shared)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace")
    last_err = ""
    for line in proc.stderr:
        if cancel and cancel():
            proc.terminate()
            break
        try:
            j = json.loads(line)
        except ValueError:
            continue
        st = j.get("stats")
        if st:
            if progress and st.get("totalBytes"):
                progress(st.get("bytes", 0), st["totalBytes"], st.get("speed") or 0)
        elif j.get("level") in ("error", "critical"):
            last_err = (j.get("msg") or "").strip()
    proc.wait()
    if cancel and cancel():
        for f in [local] + glob.glob(glob.escape(local) + ".*partial"):
            if os.path.exists(f):
                os.remove(f)
        return None
    if proc.returncode or not os.path.isfile(local):
        raise RuntimeError("구글 드라이브에서 내려받지 못했습니다: " + (last_err or f"rclone 종료 코드 {proc.returncode}"))
    return local
