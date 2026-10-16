"""설정: 환경 변수와 명령줄을 한곳에서 읽는다. 어댑터와 유스케이스는 이 값만 받는다."""
import argparse
import os
from dataclasses import dataclass

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 저장소 루트


@dataclass(frozen=True)
class Config:
    projects: str        # 작업 데이터 폴더(DUBBER_PROJECTS, 기본 저장소의 projects/)
    host: str            # API 서버 주소(기본 이 PC에서만. 화면 서버가 /api를 넘겨준다)
    port: int            # API 서버 포트(DUBBER_API_PORT, 기본 8766)
    library: str         # 프로젝트 목록에 보여 줄 드라이브 폴더(DUBBER_LIBRARY, 기본 JP)
    gdrive: str          # rclone 리모트 이름(DUBBER_GDRIVE)
    yt_playlist: str     # 유튜브 재생목록(DUBBER_YT_PLAYLIST)
    yt_client_id: str    # 유튜브 OAuth(DUBBER_YT_CLIENT_ID/SECRET, 없으면 rclone 설정의 것)
    yt_client_secret: str
    voice_workers: int   # 음성 줄 수(DUBBER_VOICE_WORKERS)
    tts_threads: int     # 음성 하나가 쓰는 CPU 스레드 수(DUBBER_TTS_THREADS)
    shorts_font: str     # 쇼츠 자막 글꼴(DUBBER_SHORTS_FONT)
    shorts_credit: str   # 쇼츠 아래쪽 문구(DUBBER_SHORTS_CREDIT)
    sleep_font: str      # 음성 영상 제목 글꼴(DUBBER_SLEEP_FONT)
    sleep_sub: str       # 음성 영상 부제(DUBBER_SLEEP_SUB)


def load(argv=None):
    ap = argparse.ArgumentParser(description="설교 영상 한국어 더빙 API 서버")
    ap.add_argument("--port", type=int, default=int(os.environ.get("DUBBER_API_PORT", "8766")))
    ap.add_argument("--lan", action="store_true", help="같은 네트워크의 다른 PC에서도 API에 접속을 받는다")
    args = ap.parse_args(argv)
    env = os.environ.get
    return Config(
        projects=env("DUBBER_PROJECTS") or os.path.join(REPO, "projects"),
        host=env("DUBBER_API_HOST") or ("0.0.0.0" if args.lan else "127.0.0.1"),
        port=args.port,
        library=env("DUBBER_LIBRARY", "JP").strip("/"),
        gdrive=env("DUBBER_GDRIVE", "gdrive"),
        yt_playlist=env("DUBBER_YT_PLAYLIST", "조셉 프린스 더빙"),
        yt_client_id=env("DUBBER_YT_CLIENT_ID"),
        yt_client_secret=env("DUBBER_YT_CLIENT_SECRET"),
        voice_workers=int(env("DUBBER_VOICE_WORKERS", "4")),
        tts_threads=int(env("DUBBER_TTS_THREADS", "4")),
        shorts_font=env("DUBBER_SHORTS_FONT"),
        shorts_credit=env("DUBBER_SHORTS_CREDIT", "조셉 프린스 설교 · {제목}"),
        sleep_font=env("DUBBER_SLEEP_FONT"),
        sleep_sub=env("DUBBER_SLEEP_SUB", "조셉 프린스 설교 · 한국어 더빙"),
    )
