"""스케줄 유스케이스: 날마다 자동 작업이 쓸 Claude 사용량과 AI 도구(_schedule.json). 규칙은 domain.schedule."""
import threading

from ..domain import schedule as rules
from ..domain.ai_tools import TOOL_NAMES

STATE = "_schedule.json"


class ScheduleService:
    def __init__(self, store, ai):
        self.store = store  # ports.StateStore
        self.ai = ai        # ports.AiRunner(켜진 도구, Fable로 이어 쓰기, 마지막 사용량)
        self._sched = rules.empty()
        self._lock = threading.Lock()

    def enabled(self):
        return [t for t in TOOL_NAMES if self.ai.config[t].get("enabled", True)]

    def load(self):
        self._sched.update(self.store.read(STATE) or {})
        self._fable_apply()

    def _fable_apply(self):
        self.ai.fallback_model = "fable" if self._sched["fable"].get("on") else None

    def limits(self, day=None):
        return rules.usage_limits(self._sched, day)

    def day_tool(self, day=None):
        return rules.day_tool(self._sched, self.enabled(), day)

    def usage_pause(self):
        return rules.usage_pause(self._sched, self.enabled(), self.ai.usage().get("info") or {})

    def set(self, body):
        with self._lock:
            if rules.apply(self._sched, body, self.enabled()):
                self._fable_apply()
            self.store.write(STATE, self._sched)

    def view(self):
        u = self.ai.usage()
        wins = (u.get("info") or {}).get("unifiedWindows") or {}
        pause = self.usage_pause()
        return {"default": self._sched["default"], "days": self._sched["days"], "today": rules.day(),
                "limits": self.limits(),
                "usage": {k: {"utilization": (wins.get(k) or {}).get("utilization"),
                              "resetsAt": (wins.get(k) or {}).get("resetsAt")}
                          for k in list(rules.SCHEDULE_DEFAULT) + [rules.FALLBACK_WINDOW]},
                "fable": self._sched["fable"], "fable_now": self.ai.fallback_active(),
                "tool": self._sched.get("tool") or "claude", "today_tool": self.day_tool(),
                "usage_t": u.get("t"), "pause": {"until": pause[0], "reason": pause[1]} if pause else None}
