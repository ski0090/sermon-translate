"""API 서버 진입점(표준 라이브러리 HTTP). 화면 없이 /api/... JSON과 파일만 내준다.
실행: python backend/main.py [--port 8766] [--lan]  ->  http://127.0.0.1:8766/api/projects
화면은 frontend/serve.py가 내주고 /api를 이 서버로 넘긴다(둘을 함께 띄우려면 저장소 루트의 run.py)."""
import os

from dubber import bootstrap, config
from dubber.adapters.inbound.http import api, server
from dubber.adapters.outbound import process_guard


def main(argv=None):
    cfg = config.load(argv)
    os.makedirs(cfg.projects, exist_ok=True)
    _root_lock = process_guard.lock_root(cfg.projects)  # noqa  서버가 끝날 때까지 쥐고 있는다
    process_guard.kill_orphans(cfg.projects)
    app = bootstrap.build(cfg)
    bootstrap.load_settings(app)
    httpd = server.serve(cfg.host, cfg.port, api.build(app))  # 포트를 먼저 잡는다(이미 쓰고 있으면 이어 하기 전에 멈춘다)
    bootstrap.resume(app)
    print(f"설교 영상 한국어 더빙 API: http://{cfg.host}:{cfg.port}/api/ · 프로젝트 폴더: {cfg.projects}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
