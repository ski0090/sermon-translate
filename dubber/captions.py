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
MIN_BAND_SHARE = 0.2    # 자막 띠로 볼 최소 글자량(감지 구간 전체 글자량 대비)


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
    near_dark = dark.copy()
    for dy in (-2, -1, 1, 2):
        near_dark |= np.roll(dark, dy, axis=0)
    for dx in (-2, -1, 1, 2):
        near_dark |= np.roll(dark, dx, axis=1)
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


def detect_band(video, info, start=120.0, dur=300.0):
    """첫 몇 분에서 글자가 가장 많이 나타나는 가로 띠를 찾아 자막 영역으로 삼는다."""
    H, W = info["height"], info["width"]
    total = float(info.get("duration") or 0)
    if total and start + dur > total:
        # 짧은 영상이면 가운데 구간을 쓴다
        dur = min(dur, total)
        start = max(0.0, (total - dur) / 2)
    y0 = int(H * 0.55)
    roi = {"x": 0, "y": y0, "w": W, "h": H - y0}
    rows = np.zeros(H - y0)
    n = 0
    for _, f in _frames(video, roi, 1, start, dur):
        m = text_mask(f)
        if m.sum() >= MIN_TEXT_PX:
            rows += m.sum(axis=1)
            n += 1
    if n == 0:
        return {"x": 0, "y": int(H * 0.7), "w": W, "h": H - int(H * 0.7)}
    thresh = rows.max() * 0.15
    ys = np.where(rows > thresh)[0]
    # 가장 아래쪽 연속 구간(설교 자막)을 고른다. 위쪽의 성경 구절 상자는 떨어져 있다.
    # 화면 맨 아래의 가는 선(진행 막대, 테두리)처럼 글자가 거의 없는 구간은 건너뛴다.
    groups = np.split(ys, np.where(np.diff(ys) > 12)[0] + 1)
    total = rows.sum()
    big = [g for g in groups if rows[g].sum() >= total * MIN_BAND_SHARE]
    band = (big or groups)[-1]
    top = max(0, int(band[0]) - 9)
    bot = min(H - y0, int(band[-1]) + 12)
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
