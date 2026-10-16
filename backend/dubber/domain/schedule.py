"""스케줄 규칙: 날마다 자동 작업이 쓸 수 있는 Claude 사용량(%)과 AI 도구, 자동 작업이 쉬어야 하는지.
자동 작업은 Claude 사용량이 그날의 한도(스케줄 달력, 기본 5시간 50%·주간 50%)를 넘으면 쉬어서, 사람이 Claude를
직접 쓸 몫을 남긴다."""
import re
import time

SCHEDULE_DEFAULT = {"five_hour": 50, "seven_day": 50}  # 자동 작업이 쓸 수 있는 Claude 사용량(%)
USAGE_NAMES = {"five_hour": "5시간", "seven_day": "주간"}
TOOLS = ("claude", "codex", "agy")
# 기본 사용량을 다 쓴 뒤에 쓰는 Fable의 별도 주간 몫(seven_day_overage_included)
FALLBACK_WINDOW = "seven_day_overage_included"
KEEP_DAYS = 90  # 이만큼 지난 날의 값은 지운다


def empty():
    return {"default": dict(SCHEDULE_DEFAULT), "days": {},  # days: {"2026-10-10": {"five_hour": 90, "seven_day": 90}}
            "fable": {"on": True, "limit": 100},  # 기본 사용량을 다 쓰면 Fable의 별도 몫을 limit%까지 쓴다
            "tool": "claude"}  # 날을 따로 정하지 않았을 때 자동 작업이 쓰는 AI 도구(날마다 days[...]["tool"])


def day(t=None):
    return time.strftime("%Y-%m-%d", time.localtime(t))


def next_midnight(t):
    lt = time.localtime(t)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + 1, 0, 0, 0, 0, 0, -1))


def usage_limits(sched, d=None):
    """그날 자동 작업이 쓸 수 있는 Claude 사용량(%). 달력에서 정한 날은 그 값, 아니면 기본값."""
    x = sched["days"].get(d or day()) or {}
    return {k: int(x.get(k, sched["default"].get(k, v))) for k, v in SCHEDULE_DEFAULT.items()}


def day_tool(sched, enabled, d=None):
    """그날 자동 작업이 쓰는 AI 도구(claude, codex, agy). 그 도구를 꺼 두었으면 켜진 도구로 대신하고, 켜진 도구가
    없으면 None."""
    want = (sched["days"].get(d or day()) or {}).get("tool") or sched.get("tool") or "claude"
    for t in [want, sched.get("tool") or "claude"] + list(TOOLS):
        if t in enabled:
            return t
    return None


def apply(sched, body, enabled, now=None):
    """기본값({"default": {...}})이나 날짜별 값({"days": {"2026-10-10": {...} 또는 None(기본값으로)}})을 바꾼다.
    Fable을 켜고 끈 값이 바뀌었으면 True."""
    def pct(v):
        return min(100, max(0, int(round(float(v)))))
    fable_changed = False
    if body.get("fable"):
        f = body["fable"]
        sched["fable"] = {"on": bool(f.get("on", sched["fable"]["on"])),
                          "limit": pct(f.get("limit", sched["fable"]["limit"]))}
        fable_changed = True
    if body.get("tool") in TOOLS:
        sched["tool"] = body["tool"]
    if body.get("default"):
        sched["default"] = {k: pct(body["default"].get(k, sched["default"].get(k, v)))
                            for k, v in SCHEDULE_DEFAULT.items()}
    for d, v in (body.get("days") or {}).items():
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            raise ValueError(f"날짜 형식이 틀렸습니다: {d}")
        if v is None:
            sched["days"].pop(d, None)
        else:
            sched["days"][d] = {k: pct(v.get(k, usage_limits(sched, d)[k])) for k in SCHEDULE_DEFAULT}
            tool = v.get("tool") if v.get("tool") in TOOLS else (day_tool(sched, enabled, d) or "claude")
            if tool != (sched.get("tool") or "claude"):
                sched["days"][d]["tool"] = tool
    old = day((now or time.time()) - KEEP_DAYS * 86400)  # 석 달 지난 날은 지운다
    sched["days"] = {d: v for d, v in sorted(sched["days"].items()) if d >= old}
    return fable_changed


def usage_pause(sched, enabled, usage_info, now=None):
    """자동 작업이 Claude를 쉬어야 하면 (다시 해 볼 시각, 이유). 사용량은 마지막 Claude 호출 때의 값이다.
    그날의 한도는 스케줄 달력에서 정하고, 한도가 더 높은 날이 사용량 초기화보다 먼저 오면 그날 0시에 다시 한다."""
    now = now or time.time()
    lim = usage_limits(sched)
    if min(lim.values()) <= 0:
        m = next_midnight(now)
        for _ in range(60):
            if min(usage_limits(sched, day(m)).values()) > 0:
                break
            m = next_midnight(m + 1)
        return m + 5, "스케줄에서 오늘은 자동 작업을 쉬도록 정해"
    tool = day_tool(sched, enabled)
    if tool is None:
        return now + 600, "켜진 AI 도구가 없어(설정 > AI 도구)"
    if tool != "claude":
        return None  # Codex·Antigravity로 하는 날은 Claude 사용량을 보지 않는다(그 도구 한도에 걸리면 그때 기다린다)
    wins = (usage_info or {}).get("unifiedWindows") or {}
    fw = wins.get(FALLBACK_WINDOW) or {}
    fable = sched["fable"]
    fable_left = (fw.get("utilization") or 0) < fable["limit"] / 100 or (fw.get("resetsAt") or 0) <= now
    for k in SCHEDULE_DEFAULT:
        w = wins.get(k) or {}
        used, reset = w.get("utilization", 0) or 0, w.get("resetsAt", 0) or 0
        if used >= lim[k] / 100 and reset > now and lim[k] >= 100 and fable["on"] and fable_left:
            continue  # 그날 다 써도 되는 날: 기본 사용량을 다 썼으면 Fable로 이어 간다
        if used >= lim[k] / 100 and reset > now:
            if lim[k] >= 100 and fable["on"]:
                fr = (fw.get("resetsAt") or 0) + 120
                return min(reset + 120, fr) if fr > now else reset + 120, \
                    f"Claude {USAGE_NAMES[k]} 사용량과 Fable 추가 몫({fable['limit']}%)을 다 써"
            until = reset + 120
            m = next_midnight(now)
            while m < until:
                if used < usage_limits(sched, day(m))[k] / 100:
                    until = m + 5
                    break
                m = next_midnight(m + 1)
            return until, f"Claude {USAGE_NAMES[k]} 사용량이 {used:.0%}라 오늘 한도 {lim[k]}%를 넘어"
    return None
