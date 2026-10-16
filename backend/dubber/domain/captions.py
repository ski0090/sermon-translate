"""자막 구간 규칙: 자막 영역 좌표 맞추기, 자막 없음 구간, 찬양(노란 가사) 후보 구간."""


def even_roi(roi, W, H):
    """좌표와 크기를 짝수로 맞추고 화면 안에 들어가게 한다."""
    x = max(0, min(int(roi["x"]) // 2 * 2, W - 2))
    y = max(0, min(int(roi["y"]) // 2 * 2, H - 2))
    w = max(2, min(int(roi["w"]) // 2 * 2, W - x))
    h = max(2, min(int(roi["h"]) // 2 * 2, H - y))
    return {"x": x, "y": y, "w": w, "h": h}


def gaps(segs, duration, min_gap, start=0.0):
    """자막이 min_gap초 이상 없는 구간."""
    out = []
    prev = start
    for s in segs:
        if s["start"] - prev >= min_gap:
            out.append({"start": round(prev, 3), "end": round(s["start"], 3)})
        prev = s["end"]
    if duration - prev >= min_gap:
        out.append({"start": round(prev, 3), "end": round(duration, 3)})
    return out


def lyric_ranges(segs, min_yellow=0.3, min_count=3):
    """노란 가사 자막이 연속되는 구간(찬양 후보)."""
    out = []
    run = []
    for s in segs + [None]:
        if s is not None and s["yellow"] >= min_yellow:
            run.append(s)
            continue
        if len(run) >= min_count:
            out.append({"start": run[0]["start"], "end": run[-1]["end"]})
        run = []
    return out
