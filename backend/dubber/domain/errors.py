"""도메인과 유스케이스가 내는 오류. 바깥(HTTP 등)은 이 종류를 보고 응답을 정한다."""
import time


class NotFound(LookupError):
    """찾는 것(프로젝트, 쇼츠, 파일)이 없다."""


class Conflict(RuntimeError):
    """지금 상태에서는 할 수 없다(이미 진행 중인 작업이 있음 등)."""


class UsageLimit(RuntimeError):
    """AI 도구의 사용량 한도에 걸렸다. 빈칸으로 저장하지 않고 멈춰야 한도가 풀린 뒤 다시 읽을 수 있다."""
    PREFIX = "Claude 사용량 한도에 걸렸습니다"

    def __init__(self, resets_at=None):
        self.resets_at = resets_at
        when = f" ({time.strftime('%m월 %d일 %H:%M', time.localtime(resets_at))}에 풀림)" if resets_at else ""
        super().__init__(self.PREFIX + when)


class ToolError(RuntimeError):
    """AI 도구가 아예 실행되지 않았다(도구를 못 찾음, 로그인 안 됨 등). 빈칸으로 저장하지 않고 멈춰야 고친 뒤 다시 읽는다."""


class QuotaExceeded(RuntimeError):
    """유튜브 하루 할당량을 다 썼다."""
