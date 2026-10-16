"""API 서버(backend)와 화면 서버(frontend)를 함께 띄운다. 하나가 끝나면 다른 하나도 끈다.
실행: python run.py [--lan] [--no-browser]  ->  http://127.0.0.1:8765
- 화면 주소의 포트는 DUBBER_PORT(기본 8765), API 포트는 DUBBER_API_PORT(기본 8766)
- --lan이면 같은 네트워크의 다른 PC에서도 화면에 접속할 수 있다(API는 이 PC에서만 받고 화면 서버가 넘겨준다)"""
import os
import subprocess
import sys
import threading
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    web_port = int(os.environ.get("DUBBER_PORT", "8765"))
    api_port = int(os.environ.get("DUBBER_API_PORT", "8766"))
    api = [sys.executable, "-u", os.path.join(HERE, "backend", "main.py"), "--port", str(api_port)]
    web = [sys.executable, "-u", os.path.join(HERE, "frontend", "serve.py"), "--port", str(web_port),
           "--api", f"http://127.0.0.1:{api_port}"] + (["--lan"] if "--lan" in sys.argv else [])
    procs = [subprocess.Popen(api), subprocess.Popen(web)]
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{web_port}/")).start()
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
    sys.exit(max((p.returncode or 0) for p in procs))


if __name__ == "__main__":
    main()
