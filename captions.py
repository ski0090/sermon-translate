"""자막 읽기 1단계: 자막 영역의 그림이 바뀌는 순간을 찾아 자막 한 장마다 그림과 시간을 기록한다.
외부로 아무것도 보내지 않는다. ffmpeg로 자막 영역만 디코딩하고 numpy로 글자 마스크를 비교한다."""
import json
import os
import subprocess
import numpy as np
from PIL import Image

FPS = 4                 # 초당 비교 횟수
BRIGHT, DARK = 175, 70  # 밝은 글자(R,G 모두) / 검은 테두리 밝기 기준
MIN_TEXT_PX = 150       # 이보다 적으면 글자 없음
CHANGE_RATIO = 0.4      # 마스크 차이 비율이 이보다 크면 새 자막
DEBOUNCE = 2            # 바뀐 상태가 이 프레임 수만큼 이어져야 인정
MAX_KEEP = 40           # 대표 그림 선택용으로 보관하는 프레임 수
MIN_BAND_SHARE = 0.2    # 자막 띠로 볼 최소 글자량(강한 띠들 전체 대비)
BAND_TH = 0.3           # 부드럽게 한 줄별 글자량이 최고치의 이만큼을 넘어야 띠 후보
BAND_EDGE = 0.25        # 띠의 위아래 끝: 원래 글자량이 띠 최고치의 이만큼을 넘는 줄까지
STATIC_RATIO = 0.1      # 바뀐 양/글자량이 이보다 작은 줄은 늘 떠 있는 것(플레이어 막대, 테두리)
MIN_LINE = 0.025        # 자막 띠의 실제 글자 높이가 화면 높이의 이만큼은 되어야 한다(가는 선 제외)


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", video],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = v["r_frame_rate"].split("/")
    return {"duration": float(info["format"]["duration"]), "width": int(v["width"]), "height": int(v["height"]),
            "fps": float(num) / float(den), "has_audio": any(s["codec_type"] == "audio" for s in info["streams"])}


def _frames(video, roi, fps, start=0.0, dur=None):
    """ROI를 rgb24 프레임으로 하나씩 낸다. (t, HxWx3 uint8)"""
    w, h = roi["w"], roi["h"]
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", video]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    # format을 crop보다 먼저 둔다. yuv420p 상태에서 홀수 높이로 자르면 ffmpeg가 높이를 줄여 버려 프레임 크기가 어긋난다.
    cmd += ["-vf", f"fps={fps},format=rgb24,crop={w}:{h}:{roi['x']}:{roi['y']}", "-f", "rawvideo", "pipe:1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 7)
    n = w * h * 3
    i = 0
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield start + i / fps, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            i += 1
    finally:
        p.stdout.close()
        p.wait()


def text_mask(rgb):
    """밝은 글자(흰색 또는 노란색) 중 바로 옆에 검은 테두리가 있는 픽셀만 글자로 본다."""
    g = rgb.mean(axis=2)
    bright = (rgb[..., 0] > BRIGHT) & (rgb[..., 1] > BRIGHT)
    dark = g < DARK
    # 위아래·좌우 2픽셀 안에 검은 테두리가 있는지 본다. np.roll은 반대쪽 끝으로 넘어가서(아래쪽 검은 띠가 맨 윗줄의
    # 테두리로 잡히는 등) 가짜 글자가 생기므로 넘어가지 않게 민다.
    near_dark = dark.copy()
    for d in (1, 2):
        near_dark[d:] |= dark[:-d]
        near_dark[:-d] |= dark[d:]
        near_dark[:, d:] |= dark[:, :-d]
        near_dark[:, :-d] |= dark[:, d:]
    return bright & near_dark


def yellow_ratio(rgb, mask=None):
    """글자 픽셀 중 노란색(가사) 비율."""
    if mask is None:
        mask = text_mask(rgb)
    r, b = rgb[..., 0].astype(int), rgb[..., 2].astype(int)
    yellow = mask & (b < 140) & (r - b > 80)
    return float(yellow.sum()) / max(int(mask.sum()), 1)


def _diff(a, b):
    return (a ^ b).sum() / max((a | b).sum(), 1)


def _band_rows(video, info, y0):
    """아래쪽(y0부터)의 줄별 글자량(seen)과 이어진 두 화면 사이에 바뀐 양(change).
    영상 전체의 키프레임만 풀어 빠르게 훑는다. 키프레임이 너무 적으면 다섯 지점을 1초에 한 장씩 본다."""
    H, W = info["height"], info["width"]
    h = H - y0
    seen, change = np.zeros(h), np.zeros(h)

    def add(frames):
        prev, n = None, 0
        for f in frames:
            m = text_mask(f)
            if m.sum() >= MIN_TEXT_PX:
                seen[:] += m.sum(axis=1)
            if prev is not None:
                change[:] += (m ^ prev).sum(axis=1)
            prev, n = m, n + 1
        return n

    def keyframes():
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-skip_frame", "nokey", "-i", video, "-vf",
                              f"format=rgb24,crop={W}:{h}:0:{y0}", "-fps_mode", "passthrough", "-f", "rawvideo", "pipe:1"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 7)
        try:
            while True:
                buf = p.stdout.read(W * h * 3)
                if len(buf) < W * h * 3:
                    break
                yield np.frombuffer(buf, np.uint8).reshape(h, W, 3)
        finally:
            p.stdout.close()
            p.wait()
    if add(keyframes()) < 30:
        seen[:], change[:] = 0, 0
        total = float(info.get("duration") or 0)
        roi = {"x": 0, "y": y0, "w": W, "h": h}
        for frac in (0.15, 0.35, 0.55, 0.75, 0.9):
            add(f for _, f in _frames(video, roi, 1, max(0.0, min(total * frac, total - 60)), 60))
    return seen, change


def detect_band(video, info):
    """자막 영역(가로 띠)을 찾는다.
    - 영상 전체를 훑어 줄마다 글자량을 모은다(앞부분에 자막이 없거나 다른 영상도 있다).
    - 늘 떠 있어 바뀌지 않는 줄(웹 플레이어 막대, 테두리)은 뺀다.
    - 글자 한 줄 높이로 부드럽게 한 뒤 강한 띠 가운데 가장 아래쪽을 고른다. 가끔 뜨는 성경 구절 상자는 자막보다
      약해서 빠지고, 밝지만 가는 선(진행 막대)은 실제 글자 높이가 모자라 빠진다.
    - 고른 띠 안에서 원래 글자량으로 위아래 끝을 정하고 여백을 둔다."""
    H, W = info["height"], info["width"]
    y0 = int(H * 0.55)
    seen, change = _band_rows(video, info, y0)
    rows = seen.copy()
    rows[change / np.maximum(seen, 1) < STATIC_RATIO] = 0
    if rows.sum() == 0:
        rows = seen
    if rows.sum() == 0:
        return {"x": 0, "y": int(H * 0.7), "w": W, "h": H - int(H * 0.7)}
    w = max(5, int(H * 0.04))  # 글자 한 줄쯤의 높이
    sm = np.convolve(rows, np.ones(w) / w, mode="same")
    ys = np.where(sm > sm.max() * BAND_TH)[0]
    groups = np.split(ys, np.where(np.diff(ys) > 12)[0] + 1)

    def core(g):  # 띠 안에서 원래 글자량이 띠 최고치의 BAND_EDGE배를 넘는 줄들
        a, b = max(0, int(g[0]) - w // 2), min(len(rows), int(g[-1]) + w // 2 + 1)
        part = rows[a:b]
        return a + np.where(part > part.max() * BAND_EDGE)[0]
    big = [g for g in groups if sm[g].sum() >= sm[ys].sum() * MIN_BAND_SHARE and np.ptp(core(g)) + 1 >= H * MIN_LINE]
    c = core((big or groups)[-1])
    top = max(0, int(c[0]) - 9)
    bot = min(H - y0, int(c[-1]) + 12)
    return even_roi({"x": 0, "y": y0 + top, "w": W, "h": bot - top}, W, H)


def even_roi(roi, W, H):
    """좌표와 크기를 짝수로 맞추고 화면 안에 들어가게 한다."""
    x = max(0, min(int(roi["x"]) // 2 * 2, W - 2))
    y = max(0, min(int(roi["y"]) // 2 * 2, H - 2))
    w = max(2, min(int(roi["w"]) // 2 * 2, W - x))
    h = max(2, min(int(roi["h"]) // 2 * 2, H - y))
    return {"x": x, "y": y, "w": w, "h": h}


def scan(video, roi, out_dir, start=0.0, dur=None, progress=None, cancel=None):
    """자막 구간 목록을 돌려준다. 각 항목: start, end, crop(파일 이름), yellow."""
    os.makedirs(out_dir, exist_ok=True)
    segs = []
    cur = None          # 진행 중인 자막: ref 마스크, start, frames, last
    pending = None      # 바뀐 상태 후보: mask, t, count, rgb, has

    def close(end_t):
        nonlocal cur
        if cur is None:
            return
        frames = cur["frames"]
        _, rgb = frames[len(frames) // 2]
        idx = len(segs)
        name = f"c{idx:05d}.jpg"
        Image.fromarray(rgb).save(os.path.join(out_dir, name), quality=90)
        segs.append({"start": round(cur["start"], 3), "end": round(end_t, 3), "crop": name,
                     "yellow": round(yellow_ratio(rgb), 3)})
        cur = None

    def open_seg(p, t):
        return {"ref": p["mask"], "start": p["t"], "frames": [(p["t"], p["rgb"])], "last": t}

    for i, (t, rgb) in enumerate(_frames(video, roi, FPS, start, dur)):
        if cancel and cancel():
            break
        if progress and i % (FPS * 15) == 0:
            progress(t)
        m = text_mask(rgb)
        has = bool(m.sum() >= MIN_TEXT_PX)
        if cur is None:
            if not has:
                pending = None
                continue
            if pending and pending["has"] and _diff(pending["mask"], m) < CHANGE_RATIO:
                pending["count"] += 1
            else:
                pending = {"mask": m, "t": t, "count": 1, "rgb": rgb, "has": True}
            if pending["count"] >= DEBOUNCE:
                cur = open_seg(pending, t)
                pending = None
            continue
        if has and _diff(cur["ref"], m) < CHANGE_RATIO:
            cur["last"] = t
            if len(cur["frames"]) < MAX_KEEP:
                cur["frames"].append((t, rgb))
            pending = None
            continue
        # 진행 중인 자막과 다르다: 후보를 세운다
        if pending is None or pending["has"] != has or (has and _diff(pending["mask"], m) >= CHANGE_RATIO):
            pending = {"mask": m, "t": t, "count": 1, "rgb": rgb, "has": has}
        else:
            pending["count"] += 1
        if pending["count"] >= DEBOUNCE:
            close(pending["t"])
            if has:
                cur = open_seg(pending, t)
            pending = None
    if cur is not None:
        close(cur["last"] + 1.0 / FPS)
    return segs


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


if __name__ == "__main__":
    import random
    import sys
    import time
    video = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "crops_test"
    t_start = float(sys.argv[3]) if len(sys.argv) > 3 else 300
    t_dur = float(sys.argv[4]) if len(sys.argv) > 4 else 600
    info = probe(video)
    t0 = time.time()
    roi = detect_band(video, info)
    print("band", roi, "sec", round(time.time() - t0, 1))
    t0 = time.time()
    segs = scan(video, roi, out, start=t_start, dur=t_dur, progress=lambda t: print("..", int(t), flush=True))
    print(len(segs), "segments in", round(time.time() - t0, 1), "sec")
    for s in segs[:8]:
        print(s)
    print("gaps", gaps(segs, t_start + t_dur, 20, start=t_start))
    print("lyric", lyric_ranges(segs))
    sample = sorted(random.sample(segs, min(30, len(segs))), key=lambda s: s["start"])
    ims = [Image.open(os.path.join(out, s["crop"])) for s in sample]
    sheet = Image.new("RGB", (ims[0].width, sum(i.height + 2 for i in ims)), "red")
    y = 0
    for im in ims:
        sheet.paste(im, (0, y))
        y += im.height + 2
    sheet.save(os.path.join(out, "sheet.jpg"), quality=85)
    print("sheet saved")
