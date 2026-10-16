"""AI 도구 알아보기(ports.ToolProbe): claude, codex, agy 명령으로 설치·버전·로그인·플랜·모델·사용량을 알아내고,
Codex 기기 코드 로그인과 로그아웃을 한다."""
import base64
import datetime
import json
import os
import re
import shutil
import subprocess
import threading
import time

from .ai_cli import find_bin

CODEX_AUTH = os.path.expanduser("~/.codex/auth.json")


def _cmd(args, timeout=20):
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def _jwt_claims(tok):
    try:
        body = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (IndexError, ValueError):
        return {}


def _claude_auth(path):
    code, out = _cmd([path, "auth", "status"])
    try:
        j = json.loads(out[out.index("{"):])
    except ValueError:
        return {"logged_in": None, "note": out.strip()[-200:]}
    return {"logged_in": bool(j.get("loggedIn")), "plan": j.get("subscriptionType"), "account": j.get("orgName"),
            "auth": j.get("authMethod")}


def _codex_auth(path):
    code, out = _cmd([path, "login", "status"])
    st = {"logged_in": "Logged in" in out and "Not logged in" not in out, "note": out.strip().splitlines()[-1:] or ""}
    st["note"] = st["note"][0] if st["note"] else ""
    try:
        with open(CODEX_AUTH, encoding="utf-8") as f:
            auth = json.load(f)
        st["auth"] = auth.get("auth_mode")
        a = _jwt_claims((auth.get("tokens") or {}).get("id_token") or "").get("https://api.openai.com/auth") or {}
        st["plan"] = a.get("chatgpt_plan_type")
        st["plan_until"] = a.get("chatgpt_subscription_active_until")
    except (OSError, ValueError):
        pass
    return st


def _codex_models(path):
    """(slug, 이름, 새 모델 slug 또는 None). 새 모델이 있으면 이전 모델이다."""
    code, out = _cmd([path, "debug", "models"], timeout=30)
    try:
        j = json.loads(out[out.index("{"):])
    except ValueError:
        return []
    return [(m["slug"], m.get("display_name") or m["slug"], (m.get("upgrade") or {}).get("model"))
            for m in j.get("models", []) if m.get("visibility") == "list"]


def _agy_models(path):
    """agy models: 한 줄에 "<모델 id>\t<이름>". 탭이 없는 예전 출력은 이름만 있는 목록으로 읽는다."""
    code, out = _cmd([path, "models"], timeout=30)
    if code != 0:
        return []
    rows = [[p.strip() for p in line.split("\t")] for line in out.splitlines() if "\t" in line]
    if rows:
        return [(r[0], r[1] or r[0]) for r in rows if r[0]]
    names = []
    for line in out.splitlines():
        line = re.sub(r"^[\s*•\-–>]+", "", line).strip()
        if line and len(line) < 80 and not line.endswith((":", "...", "…")):
            names.append(re.sub(r"\s*\((default|current|기본)\)\s*$", "", line, flags=re.I))
    return [(n, n) for n in names]


def _ts(s):
    try:
        return datetime.datetime.fromisoformat(s.strip().replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def _agy_rows(text):
    """agy /usage 표: 한 줄에 "<묶음>\t<한도 이름>\t<남은 %>\t<초기화 시각>"."""
    rows = []
    for line in text.splitlines():
        p = [x.strip() for x in line.split("\t")]
        if len(p) >= 3 and p[2].endswith("%"):
            try:
                left = float(p[2].rstrip("%"))
            except ValueError:
                continue
            rows.append({"group": p[0], "name": p[1], "left": left, "resets": _ts(p[3]) if len(p) > 3 else None})
    return rows


class CliToolProbe:
    def __init__(self):
        self._procs = {}  # 도구 -> 로그인 중인 프로세스

    def path(self, tool):
        return find_bin(tool)

    def version(self, path):
        return (_cmd([path, "--version"])[1].strip().splitlines() or [""])[0]

    def auth(self, tool, path):
        if tool == "claude":
            return _claude_auth(path)
        if tool == "codex":
            return _codex_auth(path)
        return {}  # agy는 명령으로 로그인 여부를 알 수 없다(연결 시험이나 /usage로 안다)

    def models(self, tool, path):
        return _codex_models(path) if tool == "codex" else _agy_models(path) if tool == "agy" else []

    def agy_usage(self, path, timeout=120):
        code, out = _cmd([path, "-p", "/usage"], timeout=timeout)
        text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out).strip()
        got = {"text": text[-3000:], "ok": code == 0, "t": time.time(), "rows": _agy_rows(text) if code == 0 else []}
        m = re.search(r"(?i)(plan|tier|요금제)\s*[:：]\s*([^\n]+)", out)
        if m:
            got["plan"] = m.group(2).strip()[:40]
        return got

    def login(self, tool, path, st, on_end=None):
        """Codex 기기 코드 로그인: 주소와 코드를 st에 남기고, 사용자가 다른 기기에서 끝내면 저절로 끝난다.
        codex login은 시작하자마자 지금 로그인 정보를 지우므로, 먼저 백업해 두고 로그인이 끝나지 않으면(실패, 취소,
        15분 만료) 되살린다."""
        bak = CODEX_AUTH + ".dubber-bak"
        if os.path.exists(CODEX_AUTH):
            shutil.copy2(CODEX_AUTH, bak)

        def run():
            try:
                p = self._procs[tool] = subprocess.Popen([path, "login", "--device-auth"], stdout=subprocess.PIPE,
                                                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
                                                         encoding="utf-8", errors="replace")
                for line in p.stdout:
                    line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).rstrip()
                    if not line:
                        continue
                    st["lines"] = (st["lines"] + [line])[-20:]
                    m = re.search(r"https?://\S+", line)
                    if m and not st["url"]:
                        st["url"] = m.group(0)
                    m = re.search(r"\b[A-Z0-9]{4,5}-[A-Z0-9]{4,5}\b", line)
                    if m and not st["code"]:
                        st["code"] = m.group(0)
                p.wait(timeout=1800)
                st["ok"] = p.returncode == 0
                if not st["ok"] and not st.get("error"):
                    st["error"] = (st["lines"] or ["로그인에 실패했습니다"])[-1]
            except Exception as e:  # noqa
                st.update(ok=False, error=str(e))
            finally:
                st["running"] = False
                self._procs.pop(tool, None)
                if st.get("ok") and os.path.exists(CODEX_AUTH):
                    if os.path.exists(bak):
                        os.remove(bak)
                elif os.path.exists(bak):
                    os.replace(bak, CODEX_AUTH)  # 로그인을 끝내지 않았으면 전의 로그인을 되살린다
                    st["error"] = (st.get("error") or "로그인을 끝내지 않았습니다") + " · 전의 로그인을 되살렸습니다"
                if on_end:
                    on_end()
        threading.Thread(target=run, daemon=True).start()

    def cancel_login(self, tool):
        p = self._procs.get(tool)
        if p and p.poll() is None:
            p.kill()

    def logout(self, tool, path):
        return _cmd([path, "logout"], timeout=30)
