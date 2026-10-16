"""AI 도구(Claude, Codex, Antigravity) 규칙: 모델마다 쓸 수 있는지와 걸린 한도."""
import re

from .schedule import FALLBACK_WINDOW

TOOL_NAMES = {"claude": "Claude", "codex": "Codex", "agy": "Antigravity"}
CLAUDE_MODELS = [("", "기본 (Claude Code 설정)"), ("opus", "Opus"), ("sonnet", "Sonnet"), ("haiku", "Haiku"),
                 ("fable", "Fable")]


def span(m):
    return "" if not m else f"{round(m / 1440)}일" if m >= 1440 else f"{round(m / 60)}시간" if m >= 60 else f"{m}분"


def agy_limits(model, label, rows):
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


def verdict(logged_in, limits):
    """로그인이 안 됐거나 한도 하나라도 다 썼으면 쓸 수 없다. 로그인 확인 전이면 모른다(None)."""
    if logged_in is False:
        return False, "로그인 안 됨"
    full = [u for u in limits if u.get("used") is not None and u["used"] >= 1]
    if full:
        return False, f"{full[0]['label']} 한도를 다 씀"
    return (None, "로그인 확인 전") if logged_in is None else (True, "")


def model_info(t, x, windows, codex_limits, agy_rows, codex_new=None):
    """모델마다 {"ok": True/False/None, "why": 쓸 수 없는 까닭, "note": 덧붙임, "limits": [{label, used 0~1, resets}]}
    windows: Claude 사용량 창(unifiedWindows), codex_limits: Codex 한도, agy_rows: Antigravity /usage 표."""
    li, info = x.get("logged_in"), {}
    if t == "claude":
        win = windows or {}
        lim = lambda k, lab: ({"label": lab, "used": win[k].get("utilization"), "resets": win[k].get("resetsAt")}  # noqa
                              if win.get(k) else None)
        base = [u for u in (lim("five_hour", "5시간"), lim("seven_day", "주간")) if u]
        extra = lim(FALLBACK_WINDOW, "Fable 추가 몫")
        for v, _ in x["models"]:
            ok, why = verdict(li, base)
            note = ""
            if v == "fable" and extra:
                if ok is False and li is not False:  # 기본 한도를 다 써도 Fable 추가 몫이 남았으면 쓴다
                    ok, why = verdict(li, [extra])
                    note = "" if ok is False else "기본 한도를 다 써서 Fable 추가 몫으로 씀"
                info[v] = {"ok": ok, "why": why, "note": note, "limits": base + [extra]}
            else:
                info[v] = {"ok": ok, "why": why, "note": note, "limits": base}
    elif t == "codex":
        cl = codex_limits or {}
        limits = [{"label": f"{lab} ({span(w.get('window_minutes'))})", "used": (w.get("used_percent") or 0) / 100,
                   "resets": w.get("resets_at")} for key, lab in (("primary", "한도"), ("secondary", "두 번째 한도"))
                  if (w := cl.get(key))]
        for v, _ in x["models"]:
            ok, why = verdict(li, limits)
            up = (codex_new or {}).get(v)
            info[v] = {"ok": ok, "why": why, "note": f"이전 모델 · 새 모델 {up}" if up else "", "limits": limits}
    else:
        rows = agy_rows or []
        for v, label in x["models"]:
            limits = agy_limits(v, label, rows) if v else []
            ok, why = verdict(li, limits)
            info[v] = {"ok": ok, "why": why, "note": "", "limits": limits}
    return info


def sort_models(models, info):
    """쓸 수 있는 모델을 먼저, 쓸 수 없는 모델을 나중에 둔다(기본은 맨 앞)."""
    rank = {True: 1, None: 2, False: 3}
    return sorted(models, key=lambda m: 0 if not m[0] else rank[info[m[0]]["ok"]])
