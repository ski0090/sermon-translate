"""구글 드라이브에서 영상을 둘러보고 내려받고, 결과물을 올린다. rclone 명령줄 도구와 `rclone config`로 만든 리모트(기본 이름 gdrive)를 쓴다.
리모트 이름은 환경 변수 DUBBER_GDRIVE로 바꾼다."""
import glob
import json
import os
import posixpath
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


def list_library(root):
    """root 폴더의 영상과 진행 흔적을 한 번에 읽는다. 작업 폴더(crops 등)는 내려가지 않는다.
    맨 위 영상, <이름>/project.json(이전 작업), <이름> 한국어 더빙/*.mp4, <이름>/out/*.mp4(이전 결과)"""
    inc = [f"/*{e}" for e in VIDEO_EXT] + ["/*/project.json", "/*/*.mp4", "/*/out/*.mp4"]
    args = ["lsjson", REMOTE + root.strip("/"), "-R", "--files-only", "--no-mimetype"]
    for i in inc:
        args += ["--include", i]
    r = _run(args)
    if r.returncode:
        raise RuntimeError(f"구글 드라이브 {root} 폴더를 읽지 못했습니다: " + _err(r.stderr))
    return [{"path": it["Path"], "size": it.get("Size", -1)} for it in json.loads(r.stdout or "[]")]


def _local_path(dest_dir, name, size):
    """같은 이름·같은 크기의 파일은 이미 받은 것으로 보고 다시 쓴다. 이름만 같으면 다른 프로젝트의 영상을 덮지 않도록 새 이름을 붙인다."""
    base, ext = os.path.splitext(name)
    local, n = os.path.join(dest_dir, name), 2
    while os.path.exists(local) and os.path.getsize(local) != size:
        local = os.path.join(dest_dir, f"{base}_{n}{ext}")
        n += 1
    return local


def _copy(src, dst, shared, progress, cancel):
    """rclone copyto 한 번. 끝나면 True, 중단하면 False. progress(보낸 바이트, 전체 바이트, 초당 바이트)"""
    proc = subprocess.Popen(["rclone", "copyto", src, dst, "--stats", "1s", "--stats-log-level", "NOTICE",
                             "--use-json-log", *_flags(shared)],
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
        return False
    if proc.returncode:
        raise RuntimeError(last_err or f"rclone 종료 코드 {proc.returncode}")
    return True


def download(path, dest_dir, size, shared=False, progress=None, cancel=None):
    """드라이브의 영상 하나를 dest_dir에 받고 로컬 경로를 돌려준다. 중단하면 None."""
    os.makedirs(dest_dir, exist_ok=True)
    local = _local_path(dest_dir, os.path.basename(path.rstrip("/")), size)
    if os.path.isfile(local):
        return local
    try:
        ok = _copy(REMOTE + path.strip("/"), local, shared, progress, cancel)
    except RuntimeError as e:
        raise RuntimeError(f"구글 드라이브에서 내려받지 못했습니다: {e}")
    if not ok:
        for f in [local] + glob.glob(glob.escape(local) + ".*partial"):
            if os.path.exists(f):
                os.remove(f)
        return None
    return local


def upload(files, folder, shared=False, progress=None, cancel=None):
    """로컬 파일들을 드라이브 폴더(folder)에 올린다. 같은 이름은 덮어쓴다. 중단하면 False.
    progress(올린 바이트, 전체 바이트, 초당 바이트, 파일 번호, 파일 수)"""
    sizes = [os.path.getsize(f) for f in files]
    total, done = max(sum(sizes), 1), 0
    for i, (f, size) in enumerate(zip(files, sizes)):
        dst = REMOTE + posixpath.join(folder.strip("/"), os.path.basename(f))
        prog = (lambda b, _t, sp, i=i, base=done: progress(base + b, total, sp, i + 1, len(files))) if progress else None
        try:
            ok = _copy(f, dst, shared, prog, cancel)
        except RuntimeError as e:
            raise RuntimeError(f"구글 드라이브에 올리지 못했습니다: {e}")
        if not ok:
            return False
        done += size
    return True
