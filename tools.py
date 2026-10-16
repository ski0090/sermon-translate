"""AI 도구(Claude, Codex, Antigravity) 설정과 상태.
- 도구마다 사용 여부와 모델을 정한다(projects/_tools.json -> ai.CONFIG).
- 설치·버전·로그인·플랜·고를 수 있는 모델·지금 쓰는 모델을 알아낸다(느린 명령은 몇 분 동안 기억해 둔다).
- 화면에서 Codex 로그인(기기 코드)과 로그아웃, 도구마다 연결 시험을 한다.
- 사용량 화면에 쓸 정보(Claude 5시간·주간·Fable 추가 몫, Codex 한도, Antigravity /usage, 날짜별 호출 수)를 모은다."""
import base64
import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

import ai

STATE = os.path.join(ai._PROJECTS, "_tools.json")
CLAUDE_MODELS = [("", "기본 (Claude Code 설정)"), ("opus", "Opus"), ("sonnet", "Sonnet"), ("haiku", "Haiku"),
                 ("fable", "Fable")]
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
TTL = 300
_cache = {}
_login = {}   # 도구 -> {"running", "lines", "url", "code", "ok", "error", "t"}
_tested = {}  # 도구 -> {"ok", "msg", "t", "model"}
_agy_usage = {}
_agy_busy = {"on": False}  # /usage를 뒤에서 읽는 중(한 번에 30~40초 걸린다)
_procs = {}   # 도구 -> 로그인 중인 프로세스
CODEX_AUTH = os.path.expanduser("~/.codex/auth.json")
_lock = threading.Lock()


# ---------- 설정 ----------
def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}
    for t in ai.TOOL_NAMES:
        ai.CONFIG[t].update({k: v for k, v in (saved.get(t) or {}).items() if k in ("enabled", "model")})


def set_config(tool, enabled=None, model=None):
    if tool not in ai.TOOL_NAMES:
        raise ValueError(f"모르는 AI 도구입니다: {tool}")
    if enabled is not None:
        ai.CONFIG[tool]["enabled"] = bool(enabled)
    if model is not None:
        ai.CONFIG[tool]["model"] = str(model).strip()
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ai.CONFIG, f, ensure_ascii=False)
    os.replace(tmp, STATE)


def enabled_tools():
    return [t for t in ai.TOOL_NAMES if ai.CONFIG[t].get("enabled", True)]


# ---------- 상태 ----------
def _path(tool):
    try:
        return ai._bin(tool)
    except ai.ToolError:
        return None


def _cmd(args, timeout=20):
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def _cached(key, fn, fresh=False):
    hit = _cache.get(key)
    if hit and not fresh and time.time() - hit[0] < TTL:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val


def _jwt_claims(tok):
    try:
        body = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (IndexError, ValueError):
        return {}


def _claude(path):
    code, out = _cmd([path, "auth", "status"])
    try:
        j = json.loads(out[out.index("{"):])
    except ValueError:
        return {"logged_in": None, "note": out.strip()[-200:]}
    return {"logged_in": bool(j.get("loggedIn")), "plan": j.get("subscriptionType"), "account": j.get("orgName"),
            "auth": j.get("authMethod")}


def _codex(path):
    code, out = _cmd([path, "login", "status"])
    st = {"logged_in": "Logged in" in out and "Not logged in" not in out, "note": out.strip().splitlines()[-1:] or ""}
    st["note"] = st["note"][0] if st["note"] else ""
    try:
        with open(os.path.expanduser("~/.codex/auth.json"), encoding="utf-8") as f:
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


def _agy(path):
    t = _tested.get("agy")
    return {"logged_in": t["ok"] if t else None,
            "note": "" if t else "로그인 여부는 \"연결 시험\"으로 확인합니다", "plan": _agy_usage.get("plan")}


# ---------- 모델별 사용 가능 여부와 사용량 ----------
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


def _agy_refresh(path):
    """/usage를 뒤에서 읽는다. 화면은 기다리지 않고, 다 읽으면 다음 상태 요청에 들어간다."""
    with _lock:
        if _agy_busy["on"]:
            return
        _agy_busy["on"] = True

    def run():
        try:
            _agy_fetch_usage(path)
        finally:
            _agy_busy["on"] = False
    threading.Thread(target=run, daemon=True).start()


def _agy_fetch_usage(path, timeout=120):
    code, out = _cmd([path, "-p", "/usage"], timeout=timeout)
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out).strip()
    _agy_usage.update(text=text[-3000:], ok=code == 0, t=time.time(), rows=_agy_rows(text) if code == 0 else [])
    m = re.search(r"(?i)(plan|tier|요금제)\s*[:：]\s*([^\n]+)", out)
    if m:
        _agy_usage["plan"] = m.group(2).strip()[:40]
    return dict(_agy_usage)


def _span(m):
    return "" if not m else f"{round(m / 1440)}일" if m >= 1440 else f"{round(m / 60)}시간" if m >= 60 else f"{m}분"


def _agy_limits(model, label, rows):
    """Antigravity 모델 하나에 걸리는 한도: 모델 묶음 공용(Gemini, Claude·GPT)과 그 모델 전용."""
    base = re.sub(r"\s*\([^)]*\)\s*$", "", label).lower()
    out = []
    for r in rows:
        g = r["group"].lower()
        shared = g.endswith("models") and (("gemini" in g and model.startswith("gemini"))
                                           or (("claude" in g or "gpt" in g) and model.startswith(("claude", "gpt"))))
        if not shared and not (base and base.startswith(g)):
            continue
        n = r["name"].lower()
        kind = "주간" if "weekly" in n else "5시간" if "five hour" in n else r["name"]
        who = ("Gemini 공용" if "gemini" in g else "Claude·GPT 공용") if shared else "이 모델"
        out.append({"label": f"{kind} ({who})", "used": max(0.0, 1 - r["left"] / 100), "resets": r["resets"]})
    return out


def _verdict(logged_in, limits):
    """로그인이 안 됐거나 한도 하나라도 다 썼으면 쓸 수 없다. 로그인 확인 전이면 모른다(None)."""
    if logged_in is False:
        return False, "로그인 안 됨"
    full = [u for u in limits if u.get("used") is not None and u["used"] >= 1]
    if full:
        return False, f"{full[0]['label']} 한도를 다 씀"
    return (None, "로그인 확인 전") if logged_in is None else (True, "")


def _model_info(t, x, codex_new=None):
    """모델마다 {"ok": True/False/None, "why": 쓸 수 없는 까닭, "note": 덧붙임, "limits": [{label, used 0~1, resets}]}"""
    li, info = x.get("logged_in"), {}
    if t == "claude":
        win = (ai.load_usage().get("info") or {}).get("unifiedWindows") or {}
        lim = lambda k, lab: ({"label": lab, "used": win[k].get("utilization"), "resets": win[k].get("resetsAt")}
                              if win.get(k) else None)
        base = [u for u in (lim("five_hour", "5시간"), lim("seven_day", "주간")) if u]
        extra = lim(ai.FALLBACK_WINDOW, "Fable 추가 몫")
        for v, _ in x["models"]:
            ok, why = _verdict(li, base)
            note = ""
            if v == "fable" and extra:
                if ok is False and li is not False:  # 기본 한도를 다 써도 Fable 추가 몫이 남았으면 쓴다
                    ok, why = _verdict(li, [extra])
                    note = "" if ok is False else "기본 한도를 다 써서 Fable 추가 몫으로 씀"
                info[v] = {"ok": ok, "why": why, "note": note, "limits": base + [extra]}
            else:
                info[v] = {"ok": ok, "why": why, "note": note, "limits": base}
    elif t == "codex":
        cl = ai.codex_info().get("limits") or {}
        limits = [{"label": f"{lab} ({_span(w.get('window_minutes'))})", "used": (w.get("used_percent") or 0) / 100,
                   "resets": w.get("resets_at")} for key, lab in (("primary", "한도"), ("secondary", "두 번째 한도"))
                  if (w := cl.get(key))]
        for v, _ in x["models"]:
            ok, why = _verdict(li, limits)
            up = (codex_new or {}).get(v)
            info[v] = {"ok": ok, "why": why, "note": f"이전 모델 · 새 모델 {up}" if up else "", "limits": limits}
    else:
        rows = _agy_usage.get("rows") or []
        for v, label in x["models"]:
            limits = _agy_limits(v, label, rows) if v else []
            ok, why = _verdict(li, limits)
            info[v] = {"ok": ok, "why": why, "note": "", "limits": limits}
    return info


def status(fresh=False):
    log_models = ai.load_log().get("models") or {}
    out = []
    for t, name in ai.TOOL_NAMES.items():
        path = _path(t)
        x = {"tool": t, "name": name, "installed": bool(path), "path": path, "install": INSTALL[t],
             "login_help": LOGIN_HELP[t], "enabled": ai.CONFIG[t].get("enabled", True),
             "model": ai.CONFIG[t].get("model", ""), "login": _login.get(t), "tested": _tested.get(t),
             "can_login": t == "codex", "can_logout": t in ("codex", "agy")}
        if path:
            x["version"] = _cached((t, "ver"), lambda: (_cmd([path, "--version"])[1].strip().splitlines() or [""])[0],
                                   fresh)
            x.update(_cached((t, "auth"), lambda: {"claude": _claude, "codex": _codex, "agy": _agy}[t](path), fresh))
            codex_new = {}
            if t == "claude":
                x["models"] = CLAUDE_MODELS
            elif t == "codex":
                ms = _cached((t, "models"), lambda: _codex_models(path), fresh)
                x["models"] = [("", "기본 (Codex 설정)")] + [(m[0], m[1]) for m in ms]
                codex_new = {m[0]: m[2] for m in ms if len(m) > 2 and m[2]}
            else:
                x["models"] = [("", "기본 (agy 설정)")] + _cached((t, "models"), lambda: _agy_models(path), fresh)
                # 모델별 한도(/usage)는 몇 분마다 뒤에서 새로 묻는다. 표를 읽었으면 로그인된 것이다
                if x.get("logged_in") is not False:
                    if fresh or time.time() - (_agy_usage.get("t") or 0) > TTL:
                        _agy_refresh(path)
                    if _agy_usage.get("rows") and x.get("logged_in") is None:
                        x.update(logged_in=True, note="")
                x["usage_busy"] = _agy_busy["on"]
            x["model_info"] = _model_info(t, x, codex_new)
            # 쓸 수 있는 모델을 먼저, 쓸 수 없는 모델을 나중에 둔다(기본은 맨 앞)
            rank = {True: 1, None: 2, False: 3}
            x["models"] = sorted(x["models"], key=lambda m: 0 if not m[0] else rank[x["model_info"][m[0]]["ok"]])
        # 지금 쓰는 모델: 정해 둔 모델, 없으면 마지막 호출에서 본 모델
        seen = (log_models.get(t) or {}).get("model")
        if t == "codex" and not seen:
            seen = ai.codex_info().get("model")
        x["active_model"] = x["model"] or seen
        x["seen_model"], x["seen_t"] = seen, (log_models.get(t) or {}).get("t")
        if t == "claude":
            x["fallback"] = ai.FALLBACK_MODEL
            x["fallback_now"] = time.time() < ai._main_out["until"]
        out.append(x)
    return out


# ---------- 로그인, 로그아웃, 연결 시험 ----------
def login(tool):
    """Codex 기기 코드 로그인: 주소와 코드를 화면에 보여 주고, 사용자가 다른 기기에서 끝내면 저절로 끝난다.
    codex login은 시작하자마자 지금 로그인 정보를 지우므로, 먼저 백업해 두고 로그인이 끝나지 않으면(실패, 취소,
    15분 만료) 되살린다."""
    if tool != "codex":
        raise ValueError(LOGIN_HELP.get(tool, "화면에서 로그인할 수 없는 도구입니다"))
    path = _path(tool)
    if not path:
        raise ValueError("Codex가 설치되어 있지 않습니다")
    with _lock:
        cur = _login.get(tool)
        if cur and cur.get("running"):
            return cur
        st = _login[tool] = {"running": True, "lines": [], "url": None, "code": None, "ok": None, "error": None,
                             "t": time.time()}

    bak = CODEX_AUTH + ".dubber-bak"
    if os.path.exists(CODEX_AUTH):
        shutil.copy2(CODEX_AUTH, bak)

    def run():
        try:
            p = _procs[tool] = subprocess.Popen([path, "login", "--device-auth"], stdout=subprocess.PIPE,
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
            _procs.pop(tool, None)
            if st.get("ok") and os.path.exists(CODEX_AUTH):
                if os.path.exists(bak):
                    os.remove(bak)
            elif os.path.exists(bak):
                os.replace(bak, CODEX_AUTH)  # 로그인을 끝내지 않았으면 전의 로그인을 되살린다
                st["error"] = (st.get("error") or "로그인을 끝내지 않았습니다") + " · 전의 로그인을 되살렸습니다"
            _cache.pop((tool, "auth"), None)
    threading.Thread(target=run, daemon=True).start()
    return st


def cancel(tool):
    """진행 중인 로그인을 멈춘다(전의 로그인은 되살린다)."""
    p = _procs.get(tool)
    if p and p.poll() is None:
        p.kill()
    st = _login.get(tool) or {}
    st["error"] = "로그인을 취소했습니다"
    return st


def logout(tool):
    path = _path(tool)
    if tool == "claude":
        raise ValueError("Claude 로그아웃은 이 PC의 Claude Code도 함께 로그아웃되어 화면에서는 하지 않습니다. 사용만 끌 수 있습니다")
    if not path:
        raise ValueError(f"{ai.TOOL_NAMES[tool]}이(가) 설치되어 있지 않습니다")
    code, out = _cmd([path, "logout"], timeout=30)
    _cache.pop((tool, "auth"), None)
    _tested.pop(tool, None)
    if code != 0:
        raise ValueError(f"로그아웃하지 못했습니다: {out.strip()[-200:]}")
    return out.strip()


def test(tool):
    """아주 짧게 한 번 불러 본다(토큰이 조금 든다). 꺼 둔 도구도 시험할 수 있다."""
    was = ai.CONFIG[tool].get("enabled", True)
    ai.CONFIG[tool]["enabled"] = True
    try:
        out = ai.run_tool("다른 말 없이 \"확인\"이라고만 답하세요.", tool, cwd=tempfile.gettempdir(), timeout=180)
        _tested[tool] = {"ok": True, "msg": out.strip()[:100], "t": time.time()}
    except Exception as e:  # noqa
        _tested[tool] = {"ok": False, "msg": str(e)[:300], "t": time.time()}
    finally:
        ai.CONFIG[tool]["enabled"] = was
        _cache.pop((tool, "auth"), None)
    return _tested[tool]


# ---------- 사용량 ----------
def usage():
    u = ai.load_usage()
    info = u.get("info") or {}
    cx = ai.codex_info()
    log = ai.load_log()
    days = sorted((log.get("days") or {}).items(), reverse=True)[:14]
    return {"claude": {"windows": info.get("unifiedWindows") or {}, "status": info.get("status"), "t": u.get("t")},
            "codex": {"limits": cx.get("limits"), "t": cx.get("limits_t"), "model": cx.get("model")},
            "agy": _agy_usage, "days": days, "names": ai.TOOL_NAMES}


def check(tool):
    """사용량을 새로 읽는다. Claude와 Codex는 아주 짧게 한 번 부르고, Antigravity는 /usage를 묻는다."""
    if tool == "claude":
        ai.check_usage()
    elif tool == "codex":
        test("codex")
    elif tool == "agy":
        path = _path("agy")
        if not path:
            raise ValueError("Antigravity가 설치되어 있지 않습니다")
        _agy_fetch_usage(path)
    else:
        raise ValueError(f"모르는 AI 도구입니다: {tool}")
    return usage()
