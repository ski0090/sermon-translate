"""서버 프로세스 지키기: 한 프로젝트 폴더에 서버 하나만, 꺼진 서버가 남긴 ffmpeg 정리."""
import os
import sys


def lock_root(root):
    """한 프로젝트 폴더에는 서버 하나만 띄운다. 둘이면 같은 작업을 동시에 이어 하고 project.json을 서로 덮어쓴다."""
    f = open(os.path.join(root, "_server.lock"), "a+")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f"이 프로젝트 폴더({root})를 쓰는 서버가 이미 실행 중입니다. 먼저 그 서버를 끄세요.")
    return f  # 서버가 끝날 때까지 열어 둔다


def kill_orphans(root):
    """꺼진 서버가 남긴 ffmpeg(내보내기, 쇼츠)를 끈다. 서버를 끄면 ffmpeg는 혼자 계속 돌아서, 다시 시작한 작업과
    같은 파일에 함께 쓰면 결과 영상이 깨진다. 프로젝트 폴더를 쓰는 ffmpeg 중 부모가 파이썬이 아닌 것(고아)만 끈다."""
    if not os.path.isdir("/proc"):
        return
    root = os.path.abspath(root).encode()

    def cmd(pid):
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().split(b"\0")
    for d in os.listdir("/proc"):
        try:
            args = cmd(d) if d.isdigit() else None
            if not args or os.path.basename(args[0]) != b"ffmpeg" or root not in b" ".join(args):
                continue
            with open(f"/proc/{d}/stat", "rb") as f:
                ppid = int(f.read().rsplit(b")", 1)[1].split()[1])
            if b"python" in os.path.basename(cmd(ppid)[0]):
                continue  # 명령줄로 직접 돌리는 작업
            os.kill(int(d), 9)
            print("꺼진 서버가 남긴 ffmpeg를 끕니다:", d, flush=True)
        except (OSError, ValueError, IndexError):
            continue
