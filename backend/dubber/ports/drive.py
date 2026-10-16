"""구글 드라이브 포트."""
from typing import Protocol


class CloudDrive(Protocol):
    def available(self) -> bool:
        """연결되어 있는지."""

    def list_dir(self, path="", shared=False) -> list:
        """폴더와 영상 파일 [{"name", "dir", "size"}], 폴더가 먼저."""

    def list_library(self, root) -> list:
        """목록 폴더의 영상과 진행 흔적(결과 폴더, 이전 작업) [{"path", "size"}]."""

    def download(self, path, dest_dir, size, shared=False, progress=None, cancel=None):
        """파일 하나를 받아 로컬 경로를 돌려준다(이미 받았으면 바로). 중단하면 None.
        progress(받은 바이트, 전체 바이트, 초당 바이트)."""

    def upload(self, files, folder, shared=False, progress=None, cancel=None) -> bool:
        """로컬 파일들을 폴더에 올린다(같은 이름은 덮어씀). 중단하면 False. 쓸 권한이 없으면 RuntimeError.
        progress(올린 바이트, 전체 바이트, 초당 바이트, 파일 번호, 파일 수)."""
