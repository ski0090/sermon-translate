"""AI 명령줄 도구 부르기(ports.AiRunner): claude, codex, agy(Antigravity)를 헤드리스로 한 번 부르고 답 글을 돌려준다.
호출마다 플랜 사용량(_usage.json)과 날짜별·도구별 호출 기록(_ai_log.json)을 남긴다."""
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time

from ...domain.ai_tools import TOOL_NAMES
from ...domain.errors import ToolError, UsageLimit

TIMEOUT = 300
USAGE = "_usage.json"
AI_LOG = "_ai_log.json"
AGY_ARG_MAX = 100_000  # 명령줄 인자 하나의 한도(128KB)보다 작게. 넘으면 프롬프트를 파일로 넘긴다
_LIMIT_TEXT = re.compile(r"usage limit|limit reached|rate limit|hit your limit|quota|RESOURCE_EXHAUSTED", re.I)
_AUTH_TEXT = re.compile(r"authentication required|not logged in|log ?in required|unauthenticated|please (log|sign) ?in", re.I)


def _run(cmd, prompt, cwd, env, timeout):
    """시간이 지나면 자식 프로세스 트리까지 끝낸다(shell을 거치면 손자 프로세스가 남아 기다리게 된다)."""
    # Linux는 새 세션(프로세스 그룹)으로 띄워 그룹째 끝낸다
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env,
                         start_new_session=os.name != "nt")
    try:
        out, err = p.communicate(prompt.encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        else:
            os.killpg(p.pid, signal.SIGKILL)
            p.communicate()
        raise RuntimeError(f"{cmd[0]} 응답 시간 초과({timeout}초)")
    return p.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def find_bin(name):
    """도구 실행 파일. 서비스로 띄운 서버는 PATH에 ~/.local/bin이 없을 수 있어서 거기도 찾는다. 없으면 None."""
    return shutil.which(name) or shutil.which(name, path=os.path.expanduser("~/.local/bin"))


def _bin(name):
    found = find_bin(name)
    if not found:
        raise ToolError(f"{name} 명령을 찾지 못했습니다(설치와 PATH를 확인하세요)")
    return found


def codex_info():
    """Codex 실행 기록(~/.codex/sessions)에서 마지막으로 쓴 모델과 사용량 한도. 없으면 빈 dict."""
    files = sorted(glob.glob(os.path.expanduser("~/.codex/sessions/*/*/*/*.jsonl")), key=os.path.getmtime)[-20:]
    out = {}
    for path in reversed(files):
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            try:
                j = json.loads(line)
            except ValueError:
                continue
            p = j.get("payload") or {}
            if "model" not in out and j.get("type") == "turn_context" and p.get("model"):
                out["model"] = p["model"]
            if "limits" not in out and isinstance(p, dict) and p.get("type") == "token_count" and p.get("rate_limits"):
                out["limits"], out["limits_t"] = p["rate_limits"], os.path.getmtime(path)
        if "model" in out and "limits" in out:
            break
    return out


class CliAiRunner:
    def __init__(self, store):
        self.store = store  # ports.StateStore: 사용량과 호출 기록을 남긴다
        # 도구마다 사용 여부와 모델(빈칸이면 도구의 기본 모델). 설정 화면(AI 도구) 값으로 정한다
        self.config = {t: {"enabled": True, "model": ""} for t in TOOL_NAMES}
        # 기본 모델이 사용량 한도에 걸리면 이어 쓸 모델(스케줄 설정으로 정한다. None이면 쓰지 않음).
        # Fable은 5시간·주간 사용량을 기본 모델과 함께 쓰지만, 그것을 다 쓴 뒤에 쓸 수 있는 별도 주간 몫이 있다.
        self.fallback_model = None
        self._main_out = 0.0  # 기본 모델이 한도에 걸려 풀리는 시각. 그때까지는 바로 fallback_model로 부른다
        self._log_lock = threading.Lock()

    def fallback_active(self):
        return time.time() < self._main_out

    # ---------- 사용량과 호출 기록 ----------
    def usage(self):
        return self.store.read(USAGE) or {"info": None, "t": None}

    def _save_usage(self, info):
        """마지막 사용량 정보를 저장한다. 이번 호출에 없는 창(기본 모델로 부르면 Fable 몫이 없다)은 전에 받은 값을 둔다."""
        old = (self.usage().get("info") or {}).get("unifiedWindows") or {}
        info = dict(info, unifiedWindows=dict(old, **(info.get("unifiedWindows") or {})))
        self.store.write(USAGE, {"info": info, "t": time.time()})

    def call_log(self):
        return self.store.read(AI_LOG) or {}

    def codex_info(self):
        return codex_info()

    def _record(self, tool, meta, ok=True):
        """날짜별·도구별 호출 수(실패 수)와 토큰, 도구가 마지막으로 쓴 모델을 남긴다."""
        with self._log_lock:
            d = self.call_log()
            day = time.strftime("%Y-%m-%d")
            x = d.setdefault("days", {}).setdefault(day, {}).setdefault(tool, {"calls": 0, "fails": 0, "in": 0, "out": 0})
            x["calls"] += 1
            x["fails"] += 0 if ok else 1
            x["in"] += int(meta.get("in") or 0)
            x["out"] += int(meta.get("out") or 0)
            if meta.get("model"):
                d.setdefault("models", {})[tool] = {"model": meta["model"], "t": time.time()}
            old = time.strftime("%Y-%m-%d", time.localtime(time.time() - 60 * 86400))
            d["days"] = {k: v for k, v in d["days"].items() if k >= old}
            try:
                self.store.write(AI_LOG, d)
            except OSError:
                pass

    # ---------- 부르기 ----------
    def run(self, prompt, tool="claude", image=None, cwd=None, timeout=TIMEOUT):
        """AI 도구를 한 번 호출해 출력 문자열을 돌려준다. 꺼 둔 도구는 ToolError. 호출마다 사용 기록을 남긴다."""
        if tool not in TOOL_NAMES:
            raise ToolError(f"모르는 AI 도구입니다: {tool}")
        if not self.config[tool].get("enabled", True):
            raise ToolError(f"{TOOL_NAMES[tool]} 사용이 꺼져 있습니다(설정 > AI 도구에서 켜세요)")
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE")}
        meta = {}
        try:
            out = {"claude": self._run_claude, "codex": self._run_codex,
                   "agy": self._run_agy}[tool](prompt, image, cwd, env, timeout, meta)
        except Exception:
            self._record(tool, meta, ok=False)
            raise
        self._record(tool, meta)
        return out

    def _claude_result(self, raw, meta=None):
        """stream-json 출력에서 답 글을 꺼내고, 사용량 정보가 있으면 저장한다. 한도에 걸렸으면 UsageLimit.
        meta에는 쓴 모델과 토큰 수를 남긴다."""
        text, info, is_error = "", None, False
        meta = {} if meta is None else meta
        for line in raw.splitlines():
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if j.get("type") == "rate_limit_event":
                info = j.get("rate_limit_info")
            elif j.get("type") == "system" and j.get("subtype") == "init":
                meta["model"] = j.get("model")
            elif j.get("type") == "result":
                text, is_error = j.get("result") or "", bool(j.get("is_error"))
                u = j.get("usage") or {}
                meta["in"] = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens",
                                                              "cache_creation_input_tokens"))
                meta["out"] = int(u.get("output_tokens") or 0)
        if info:
            self._save_usage(info)
        # 상태가 rejected여도 답이 왔으면 쓴다(추가 몫으로 처리된 호출)
        rejected = info and info.get("status") == "rejected" and (is_error or not text.strip())
        if rejected or (is_error and _LIMIT_TEXT.search(text)):
            raise UsageLimit((info or {}).get("resetsAt"))
        return text

    def _run_claude(self, prompt, image, cwd, env, timeout, meta):
        base = self.config["claude"].get("model") or None
        fb = self.fallback_model
        model = fb if fb and self.fallback_active() else base
        try:
            return self._claude(prompt, image, cwd, env, timeout, model, meta)
        except UsageLimit as e:
            if not fb or model == fb:
                raise
            # 기본 사용량을 다 썼다: 풀릴 때까지 Fable로 부른다
            self._main_out = max(e.resets_at or 0, time.time() + 1800)
            return self._claude(prompt, image, cwd, env, timeout, fb, meta)

    def _claude(self, prompt, image, cwd, env, timeout, model=None, meta=None):
        cmd = [_bin("claude"), "-p", "--output-format", "stream-json", "--verbose", "--max-turns", "4",
               "--allowedTools", "Read" if image else ""]
        if model:
            cmd += ["--model", model]
        code, raw, err = _run(cmd, prompt, cwd, env, timeout)
        out = self._claude_result(raw, meta)
        if code != 0 and not out.strip():
            raise ToolError(f"claude 실패: {err.strip()[:300]}")
        return out

    def _run_codex(self, prompt, image, cwd, env, timeout, meta):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            last = f.name
        cmd = [_bin("codex"), "exec", "--skip-git-repo-check", "--json", "-o", last]
        if self.config["codex"].get("model"):
            cmd += ["-m", self.config["codex"]["model"]]
        if image:
            cmd += ["-i", image]
        cmd += ["-"]
        code, raw, err = _run(cmd, prompt, cwd, env, timeout)
        with open(last, encoding="utf-8", errors="replace") as f:
            out = f.read()
        os.unlink(last)
        for line in raw.splitlines():
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if j.get("type") == "turn.completed":
                u = j.get("usage") or {}
                meta["in"], meta["out"] = int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
        meta["model"] = self.config["codex"].get("model") or codex_info().get("model")
        if code != 0 and not out.strip():
            if _LIMIT_TEXT.search(raw + err):
                raise UsageLimit()  # 풀리는 시각을 모르면 자동 진행이 30분 뒤에 다시 해 본다
            raise ToolError(f"codex 실패: {(err or raw).strip()[-300:]}")
        return out

    def _run_agy(self, prompt, image, cwd, env, timeout, meta):
        """Antigravity CLI(agy) 헤드리스 호출. 그림은 프롬프트에 적힌 경로를 agy가 직접 읽는다."""
        cmd = [_bin("agy"), "--output-format", "json"]
        if self.config["agy"].get("model"):
            cmd += ["--model", self.config["agy"]["model"]]
        tmp = None
        if len(prompt.encode("utf-8")) > AGY_ARG_MAX:
            fd, tmp = tempfile.mkstemp(dir=cwd or None, prefix="agy_prompt_", suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)
            prompt = f"{os.path.abspath(tmp)} 파일을 읽고, 그 안의 지시를 그대로 따라 답만 출력하세요."
        try:
            code, raw, err = _run(cmd + ["-p", prompt], "", cwd, env, timeout)
        finally:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        j = {}
        for line in reversed(raw.strip().splitlines()):
            try:
                j = json.loads(line)
                break
            except ValueError:
                continue
        if not j:
            try:
                j = json.loads(raw)
            except ValueError:
                j = {}
        u = j.get("usage") or {}
        meta["in"] = int(u.get("input_tokens") or u.get("inputTokens") or u.get("prompt_tokens") or 0)
        meta["out"] = int(u.get("output_tokens") or u.get("outputTokens") or u.get("completion_tokens") or 0)
        meta["model"] = j.get("model") or self.config["agy"].get("model") or None
        text = j.get("response") or (raw if not j else "")
        if code != 0 or (j and j.get("status") not in (None, "SUCCESS")) or not str(text).strip():
            why = (err + " " + str(j.get("error") or "")).strip() or raw.strip()
            if _AUTH_TEXT.search(why):
                raise ToolError("Antigravity 로그인이 필요합니다(서버 PC 터미널에서 agy를 한 번 실행해 로그인)")
            if _LIMIT_TEXT.search(why):
                raise UsageLimit()
            raise ToolError(f"agy 실패: {why[-300:]}")
        return str(text)
