"""영상·소리 포트: 영상 정보와 자막 찾기, 더빙 결과·쇼츠·음성 영상 만들기."""
from typing import Protocol


class VideoAnalyzer(Protocol):
    def probe(self, video) -> dict:
        """{"duration", "width", "height", "fps", "has_audio"}. 영상이 아니면 오류."""

    def detect_band(self, video, info) -> dict:
        """자막 영역(가로 띠) {x, y, w, h}."""

    def scan(self, video, roi, out_dir, progress=None, cancel=None) -> list:
        """자막이 바뀌는 순간을 찾아 자막 한 장마다 그림을 out_dir에 남긴다. [{start, end, crop, yellow}]
        progress(지금 시각 초)."""

    def frame(self, video, t, roi=None) -> bytes:
        """t초 장면(JPEG). roi를 주면 빨간 상자로 표시한다."""


class DubRenderer(Protocol):
    def export(self, project, ws, placements, want, orig_audio, progress=None, cancel=None) -> list:
        """want({"video","audio","srt","txt","sleep"})의 결과 파일을 만들고 경로 목록을 돌려준다.
        progress(단계 이름, 0~1)."""

    def natural_track(self, project, ws) -> tuple:
        """싱크 없이 문장을 원래 속도로 이은 음성 (wav 경로, 길이 초)."""


class SleepRenderer(Protocol):
    def render(self, wav, out, title, progress=None, cancel=None) -> bool:
        """어두운 배경 + 제목 + 이퀄라이저 영상. 중단하면 False."""


class ShortsRenderer(Protocol):
    def content_box(self, video, info) -> dict:
        """원본에서 검은 테두리를 뺀 영역 {x, y, w, h}."""

    def render(self, project, ws, item, box, out, progress=None, cancel=None) -> bool:
        """쇼츠 영상 하나를 만들어 out에 둔다. 중단하면 False."""

    def preview(self, project, ws, item, box, t=None) -> bytes:
        """지금 설정으로 한 장면(JPEG)."""
