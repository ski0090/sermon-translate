"""결과 파일 이름. 프로젝트 폴더와 구글 드라이브에 같은 이름으로 만든다."""

OUT_SUFFIX = " 한국어 더빙"
DUBBED = " (한국어 더빙).mp4"
AUDIO = " (한국어 음성).mp3"
SLEEP = " (자면서 듣는 설교).mp4"


def out_name(name):
    """결과 폴더 이름: "<영상 이름> 한국어 더빙"."""
    return name + OUT_SUFFIX


def dubbed(name):
    return name + DUBBED


def audio(name):
    return name + AUDIO


def sleep(name):
    return name + SLEEP


def short(name, sid):
    """쇼츠 파일 이름(제목을 고쳐도 이름은 그대로). 결과 폴더 아래 "쇼츠" 폴더에 둔다."""
    return f"{name} 쇼츠 {sid}.mp4"
