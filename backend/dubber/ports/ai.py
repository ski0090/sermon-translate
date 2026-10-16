"""AI 명령줄 도구 포트: 부르기, 자막 그림 묶음 만들기, 도구 상태 알아보기."""
from typing import Protocol


class AiRunner(Protocol):
    """AI 도구(claude, codex, agy)를 한 번 부른다. 한도에 걸리면 domain.errors.UsageLimit, 도구가 실행되지 않으면
    domain.errors.ToolError."""
    config: dict  # 도구 -> {"enabled", "model"}
    fallback_model: str  # 기본 모델이 한도에 걸리면 이어 쓸 모델(None이면 쓰지 않음)

    def run(self, prompt, tool="claude", image=None, cwd=None, timeout=300) -> str: ...

    def fallback_active(self) -> bool:
        """기본 모델이 한도에 걸려 지금 이어 쓸 모델로 부르는 중인지."""

    def usage(self) -> dict:
        """마지막 Claude 호출 때 받은 플랜 사용량 {"info", "t"}."""

    def call_log(self) -> dict:
        """날짜별·도구별 호출 수와 토큰, 도구가 마지막으로 쓴 모델."""

    def codex_info(self) -> dict:
        """Codex 실행 기록의 마지막 모델과 사용량 한도."""


class StripImages(Protocol):
    def fingerprint(self, paths) -> str:
        """그림 파일들의 내용 해시(같은 묶음이면 읽은 결과를 다시 쓴다)."""

    def build(self, crop_paths, out_path) -> str:
        """자막 그림을 번호와 경계선을 넣어 세로로 이어 붙인다."""


class ToolProbe(Protocol):
    """AI 도구의 설치·버전·로그인·모델·사용량을 알아보고, 로그인·로그아웃한다."""

    def path(self, tool): ...

    def version(self, path) -> str: ...

    def auth(self, tool, path) -> dict:
        """{"logged_in", "plan", ...}. 명령으로 알 수 없으면 빈 dict."""

    def models(self, tool, path) -> list:
        """codex는 (slug, 이름, 새 모델 또는 None), agy는 (id, 이름)."""

    def agy_usage(self, path) -> dict:
        """Antigravity /usage 표 {"text", "ok", "t", "rows", "plan"}."""

    def login(self, tool, path, st, on_end=None) -> None:
        """기기 코드 로그인을 뒤에서 하며 st를 고친다({"running", "lines", "url", "code", "ok", "error"}).
        끝나면 on_end()를 부른다."""

    def cancel_login(self, tool) -> None: ...

    def logout(self, tool, path) -> tuple:
        """(종료 코드, 출력)."""
