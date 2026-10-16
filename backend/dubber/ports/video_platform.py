"""유튜브 포트. 할당량을 다 쓰면 domain.errors.QuotaExceeded."""
from typing import Protocol


class VideoPlatform(Protocol):
    def status(self) -> dict:
        """{"connected", "channel", "login": {"busy", "error"}}."""

    def start_login(self) -> str:
        """로그인 주소. 로그인이 끝나 돌아올 곳을 잠시 연다."""

    def channel_uploads(self) -> list:
        """내 채널의 영상 [{"id", "title", "privacy"}]."""

    def upload_video(self, path, title, description="", privacy="private", progress=None, cancel=None, tags=None):
        """영상 id. 중단하면 None. progress(올린 바이트, 전체 바이트)."""

    def playlist_id(self, title) -> str:
        """제목이 같은 재생목록(없으면 비공개로 만든다)."""

    def in_playlist(self, playlist, video) -> bool: ...

    def add_to_playlist(self, playlist, video) -> None: ...

    def has_captions(self, video, language="ko") -> bool: ...

    def upload_captions(self, video, srt_path, language="ko", name="한국어") -> None: ...
