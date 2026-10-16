"""명령줄 입구: 화면 없이 단계별로 돌린다. HTTP와 같은 유스케이스를 쓴다.
  new <영상 경로> | scan <프로젝트> | read <프로젝트> | sentences <프로젝트> | tidy <프로젝트>
<프로젝트>는 프로젝트 폴더 경로나 이름. 서버가 켜져 있으면 바뀐 project.json을 다시 읽는다."""
import os
import sys
import threading

from ... import bootstrap, config

USAGE = __doc__.split("\n")[1].strip()


def main(argv):
    if len(argv) != 2 or argv[0] not in ("new", "scan", "read", "sentences", "tidy"):
        sys.exit("사용법: python backend/cli.py " + USAGE)
    cmd, arg = argv
    app = bootstrap.build(config.load([]))
    bootstrap.load_settings(app)
    if cmd == "new":
        p = app.projects.create(os.path.abspath(arg))
        print(app.projects.workspace(p.id).root)
        return
    pid = os.path.basename(os.path.normpath(arg))
    p, _ = app.projects.get(pid)
    lock = threading.RLock()
    if cmd == "scan":
        n = app.pipeline.scan_captions(p, lock, progress=lambda r: print(f"scan {r * 100:.0f}%", flush=True))
        print("captions", n, "roi", p.data["roi"], "lyrics", p.data["ranges"]["lyrics"], "gaps", p.data["ranges"]["gaps"])
    elif cmd == "read":
        app.pipeline.read_captions(p, lock, progress=lambda d, n: print(f"read {d}/{n}", flush=True))
        print("empty", sum(1 for c in p.data["captions"] if not c["text"]))
    elif cmd == "sentences":
        print("sentences", p.build_sentences())
        app.projects.save(p)
    elif cmd == "tidy":
        merged = app.pipeline.tidy_sentences(p, progress=lambda d, n: print(f"tidy {d}/{n}", flush=True))
        print("sentences", p.build_sentences(merged))
        app.projects.save(p)
        print("check", sum(1 for s in p.data["sentences"] if s["check"]))
