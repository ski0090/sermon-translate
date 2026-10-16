"""AI 도구 유스케이스(Claude, Codex, Antigravity):
- 도구마다 사용 여부와 모델을 정한다(_tools.json -> AiRunner.config).
- 설치·버전·로그인·플랜·고를 수 있는 모델·지금 쓰는 모델을 알아낸다(느린 명령은 몇 분 동안 기억해 둔다).
- 화면에서 Codex 로그인(기기 코드)과 로그아웃, 도구마다 연결 시험을 한다.
- 사용량 화면에 쓸 정보(Claude 5시간·주간·Fable 추가 몫, Codex 한도, Antigravity /usage, 날짜별 호출 수)를 모은다."""
import tempfile
import threading
import time

from ..domain import ai_tools as rules
from ..domain.ai_tools import TOOL_NAMES

STATE = "_tools.json"
TTL = 300
INSTALL = {
    "claude": "curl -fsSL https://claude.ai/install.sh | bash",
    "codex": "npm i -g @openai/codex   (또는 GitHub 릴리스의 codex 실행 파일을 ~/.local/bin에)",
    "agy": "curl -fsSL https://antigravity.google/cli/install.sh | bash",
}
LOGIN_HELP = {
    "claude": "서버 PC 터미널에서 claude를 실행하고 /login으로 로그인합니다.",
    "codex": "아래 \"로그인\"을 누르면 나오는 주소와 코드로 아무 기기의 브라우저에서 로그인합니다.",
    "agy": "서버 PC 터미널에서 agy를 실행하고 \"1. Google OAuth\"를 골라 로그인합니다.",
}
CHECK_PROMPT = "다른 말 없이 \"확인\"이라고만 답하세요."


class AiToolsService:
    def __init__(self, ai, probe, store):
        self.ai = ai        # ports.AiRunner
        self.probe = probe  # ports.ToolProbe
        self.store = store  # ports.StateStore
        self._cache = {}
        self._login = {}   # 도구 -> {"running", "lines", "url", "code", "ok", "error", "t"}
        self._tested = {}  # 도구 -> {"ok", "msg", "t", "model"}
        self._agy_usage = {}
        self._agy_busy = {"on": False}  # /usage를 뒤에서 읽는 중(한 번에 30~40초 걸린다)
        self._lock = threading.Lock()

    # ---------- 설정 ----------
    def load(self):
        saved = self.store.read(STATE) or {}
        for t in TOOL_NAMES:
            self.ai.config[t].update({k: v for k, v in (saved.get(t) or {}).items() if k in ("enabled", "model")})

    def set_config(self, tool, enabled=None, model=None):
        if tool not in TOOL_NAMES:
            raise ValueError(f"모르는 AI 도구입니다: {tool}")
        if enabled is not None:
            self.ai.config[tool]["enabled"] = bool(enabled)
        if model is not None:
            self.ai.config[tool]["model"] = str(model).strip()
        self.store.write(STATE, self.ai.config)

    # ---------- 상태 ----------
    def _cached(self, key, fn, fresh=False):
        hit = self._cache.get(key)
        if hit and not fresh and time.time() - hit[0] < TTL:
            return hit[1]
        val = fn()
        self._cache[key] = (time.time(), val)
        return val

    def _auth(self, t, path):
        if t == "agy":
            tested = self._tested.get("agy")
            return {"logged_in": tested["ok"] if tested else None,
                    "note": "" if tested else "로그인 여부는 \"연결 시험\"으로 확인합니다", "plan": self._agy_usage.get("plan")}
        return self.probe.auth(t, path)

    def _agy_refresh(self, path):
        """/usage를 뒤에서 읽는다. 화면은 기다리지 않고, 다 읽으면 다음 상태 요청에 들어간다."""
        with self._lock:
            if self._agy_busy["on"]:
                return
            self._agy_busy["on"] = True

        def run():
            try:
                self._agy_usage.update(self.probe.agy_usage(path))
            finally:
                self._agy_busy["on"] = False
        threading.Thread(target=run, daemon=True).start()

    def status(self, fresh=False):
        log_models = self.ai.call_log().get("models") or {}
        windows = (self.ai.usage().get("info") or {}).get("unifiedWindows") or {}
        out = []
        for t, name in TOOL_NAMES.items():
            path = self.probe.path(t)
            x = {"tool": t, "name": name, "installed": bool(path), "path": path, "install": INSTALL[t],
                 "login_help": LOGIN_HELP[t], "enabled": self.ai.config[t].get("enabled", True),
                 "model": self.ai.config[t].get("model", ""), "login": self._login.get(t), "tested": self._tested.get(t),
                 "can_login": t == "codex", "can_logout": t in ("codex", "agy")}
            if path:
                x["version"] = self._cached((t, "ver"), lambda: self.probe.version(path), fresh)
                x.update(self._cached((t, "auth"), lambda: self._auth(t, path), fresh))
                codex_new = {}
                if t == "claude":
                    x["models"] = rules.CLAUDE_MODELS
                elif t == "codex":
                    ms = self._cached((t, "models"), lambda: self.probe.models(t, path), fresh)
                    x["models"] = [("", "기본 (Codex 설정)")] + [(m[0], m[1]) for m in ms]
                    codex_new = {m[0]: m[2] for m in ms if len(m) > 2 and m[2]}
                else:
                    x["models"] = [("", "기본 (agy 설정)")] + self._cached((t, "models"),
                                                                       lambda: self.probe.models(t, path), fresh)
                    # 모델별 한도(/usage)는 몇 분마다 뒤에서 새로 묻는다. 표를 읽었으면 로그인된 것이다
                    if x.get("logged_in") is not False:
                        if fresh or time.time() - (self._agy_usage.get("t") or 0) > TTL:
                            self._agy_refresh(path)
                        if self._agy_usage.get("rows") and x.get("logged_in") is None:
                            x.update(logged_in=True, note="")
                    x["usage_busy"] = self._agy_busy["on"]
                cx = self.ai.codex_info().get("limits") if t == "codex" else None
                x["model_info"] = rules.model_info(t, x, windows, cx, self._agy_usage.get("rows"), codex_new)
                x["models"] = rules.sort_models(x["models"], x["model_info"])
            # 지금 쓰는 모델: 정해 둔 모델, 없으면 마지막 호출에서 본 모델
            seen = (log_models.get(t) or {}).get("model")
            if t == "codex" and not seen:
                seen = self.ai.codex_info().get("model")
            x["active_model"] = x["model"] or seen
            x["seen_model"], x["seen_t"] = seen, (log_models.get(t) or {}).get("t")
            if t == "claude":
                x["fallback"] = self.ai.fallback_model
                x["fallback_now"] = self.ai.fallback_active()
            out.append(x)
        return out

    # ---------- 로그인, 로그아웃, 연결 시험 ----------
    def login(self, tool):
        """Codex 기기 코드 로그인: 주소와 코드를 화면에 보여 주고, 사용자가 다른 기기에서 끝내면 저절로 끝난다."""
        if tool != "codex":
            raise ValueError(LOGIN_HELP.get(tool, "화면에서 로그인할 수 없는 도구입니다"))
        path = self.probe.path(tool)
        if not path:
            raise ValueError("Codex가 설치되어 있지 않습니다")
        with self._lock:
            cur = self._login.get(tool)
            if cur and cur.get("running"):
                return cur
            st = self._login[tool] = {"running": True, "lines": [], "url": None, "code": None, "ok": None,
                                      "error": None, "t": time.time()}
        self.probe.login(tool, path, st, on_end=lambda: self._cache.pop((tool, "auth"), None))
        return st

    def cancel(self, tool):
        """진행 중인 로그인을 멈춘다(전의 로그인은 되살린다)."""
        self.probe.cancel_login(tool)
        st = self._login.get(tool) or {}
        st["error"] = "로그인을 취소했습니다"
        return st

    def logout(self, tool):
        path = self.probe.path(tool)
        if tool == "claude":
            raise ValueError("Claude 로그아웃은 이 PC의 Claude Code도 함께 로그아웃되어 화면에서는 하지 않습니다. 사용만 끌 수 있습니다")
        if not path:
            raise ValueError(f"{TOOL_NAMES[tool]}이(가) 설치되어 있지 않습니다")
        code, out = self.probe.logout(tool, path)
        self._cache.pop((tool, "auth"), None)
        self._tested.pop(tool, None)
        if code != 0:
            raise ValueError(f"로그아웃하지 못했습니다: {out.strip()[-200:]}")
        return out.strip()

    def test(self, tool):
        """아주 짧게 한 번 불러 본다(토큰이 조금 든다). 꺼 둔 도구도 시험할 수 있다."""
        was = self.ai.config[tool].get("enabled", True)
        self.ai.config[tool]["enabled"] = True
        try:
            out = self.ai.run(CHECK_PROMPT, tool, cwd=tempfile.gettempdir(), timeout=180)
            self._tested[tool] = {"ok": True, "msg": out.strip()[:100], "t": time.time()}
        except Exception as e:  # noqa
            self._tested[tool] = {"ok": False, "msg": str(e)[:300], "t": time.time()}
        finally:
            self.ai.config[tool]["enabled"] = was
            self._cache.pop((tool, "auth"), None)
        return self._tested[tool]

    # ---------- 사용량 ----------
    def claude_usage(self):
        return self.ai.usage()

    def check_claude(self):
        """사용량만 알아보려고 claude를 아주 짧게 한 번 부른다(토큰이 조금 든다)."""
        self.ai.run(CHECK_PROMPT, "claude", cwd=tempfile.gettempdir(), timeout=120)
        return self.ai.usage()

    def usage(self):
        u = self.ai.usage()
        info = u.get("info") or {}
        cx = self.ai.codex_info()
        log = self.ai.call_log()
        days = sorted((log.get("days") or {}).items(), reverse=True)[:14]
        return {"claude": {"windows": info.get("unifiedWindows") or {}, "status": info.get("status"), "t": u.get("t")},
                "codex": {"limits": cx.get("limits"), "t": cx.get("limits_t"), "model": cx.get("model")},
                "agy": self._agy_usage, "days": days, "names": TOOL_NAMES}

    def check(self, tool):
        """사용량을 새로 읽는다. Claude와 Codex는 아주 짧게 한 번 부르고, Antigravity는 /usage를 묻는다."""
        if tool == "claude":
            self.check_claude()
        elif tool == "codex":
            self.test("codex")
        elif tool == "agy":
            path = self.probe.path("agy")
            if not path:
                raise ValueError("Antigravity가 설치되어 있지 않습니다")
            self._agy_usage.update(self.probe.agy_usage(path))
        else:
            raise ValueError(f"모르는 AI 도구입니다: {tool}")
        return self.usage()
