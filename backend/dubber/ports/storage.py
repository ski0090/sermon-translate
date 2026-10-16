"""저장소 포트: 프로젝트(project.json과 작업 파일 자리)와 작은 상태 파일(JSON)."""
from typing import Protocol

from ..domain.project import Project


class Workspace(Protocol):
    """프로젝트 한 편의 작업 파일 자리(자막 그림, 음성, 결과 파일). 경로는 유스케이스가 어댑터에 넘기기만 한다."""
    root: str

    def path(self, *parts) -> str:
        """그 자리의 경로(만들지 않는다)."""

    def ensure(self, *parts) -> str:
        """폴더를 만들고 그 경로."""


class ProjectRepository(Protocol):
    root: str  # 모든 프로젝트가 있는 곳(알림 글에만 쓴다)

    def summaries(self) -> list:
        """프로젝트 목록(domain.project.summary), 최근에 고친 것부터."""

    def exists(self, pid) -> bool: ...

    def load(self, pid) -> Project:
        """없으면 domain.errors.NotFound."""

    def is_stale(self, project) -> bool:
        """다른 프로세스(명령줄 실행)가 파일을 바꿨는지."""

    def save(self, project) -> None: ...

    def create(self, folder, data) -> Project:
        """새 프로젝트. 같은 이름의 폴더가 있으면 _2, _3을 붙인다."""

    def workspace(self, pid) -> Workspace: ...

    def area(self, name) -> str:
        """프로젝트 밖의 공용 폴더(받은 영상 _drive, 목소리 예시 _samples 등). 만들고 경로를 돌려준다."""


class StateStore(Protocol):
    """작은 상태 파일. key는 프로젝트들이 있는 곳 기준의 상대 경로("_batch.json", "<프로젝트>/shorts.json")."""

    def read(self, key, default=None): ...

    def write(self, key, obj, indent=None) -> None:
        """다 쓴 뒤 바꿔 넣는다(쓰다가 꺼져도 파일이 깨지지 않게)."""

    def exists(self, key) -> bool: ...

    def remove(self, key) -> None: ...
