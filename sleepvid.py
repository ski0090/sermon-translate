"""자면서 듣는 설교 영상: 어두운 배경에 설교 제목과 소리에 맞춰 움직이는 이퀄라이저 막대만 그린다.
소리는 영상 싱크 없이 문장을 자연스럽게 이은 음성(export.build_natural)을 쓴다."""
import os
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import tts

W, H, FPS = 1280, 720, 15
NB = 16  # 주파수 칸 수. 막대는 좌우 대칭으로 NB*2개(가운데가 낮은 음)
BAR_W, BAR_GAP, CY, MAX_H = 18, 12, 500, 120
FONTS = [os.environ.get("DUBBER_SLEEP_FONT", ""), "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
         "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", "C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf"]
SUBTITLE = os.environ.get("DUBBER_SLEEP_SUB", "조셉 프린스 설교 · 한국어 더빙")


def _font(size):
    for f in FONTS:
        if f and os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def background(title, sub=SUBTITLE):
    img = Image.new("RGB", (W, H), (11, 16, 32))
    d = ImageDraw.Draw(img)
    for txt, y, size, color in ((title, 200, 48, (205, 210, 225)), (sub, 275, 26, (138, 147, 168))):
        f = _font(size)
        d.text(((W - d.textlength(txt, font=f)) / 2, y), txt, font=f, fill=color)
    return np.asarray(img).copy()


def render(wav, out, title, progress=None, cancel=None):
    """wav로 이퀄라이저 영상을 만들어 out에 둔다. 중단하면 False."""
    x, sr = tts.read_wav(wav)
    bg = background(re.sub(r"^\d+\s*", "", title))
    hop, win = sr // FPS, 4096
    edges = np.geomspace(90, 7000, NB + 1)
    freqs = np.fft.rfftfreq(win, 1 / sr)
    bands = [(freqs >= a) & (freqs < b) for a, b in zip(edges, edges[1:])]
    tilt = np.arange(NB) * 1.2  # 높은 음은 약하니 조금 올린다
    hann = np.hanning(win)
    x0 = (W - (2 * NB * BAR_W + (2 * NB - 1) * BAR_GAP)) // 2
    color = np.linspace([96, 128, 200], [120, 96, 170], NB).astype(np.uint8)  # 가운데 파랑 -> 바깥 보라
    order = [int(abs(j - NB + 0.5) - 0.5) for j in range(2 * NB)]
    n = len(x) // hop
    tmp = out[:-4] + f".{os.getpid()}.part.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-nostdin", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a", "-shortest",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p", "-threads", "4",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    level = np.zeros(NB)
    try:
        for i in range(n):
            if cancel and cancel():
                p.kill()
                return False
            seg = x[i * hop: i * hop + win]
            if len(seg) < win:
                seg = np.pad(seg, (0, win - len(seg)))
            mag = np.abs(np.fft.rfft(seg * hann))
            db = np.array([20 * np.log10(mag[m].mean() + 1e-6) for m in bands])
            v = np.clip((db + 12 + tilt) / 48, 0, 1)
            level = np.where(v > level, v, level * 0.82 + v * 0.18)  # 빨리 오르고 천천히 내려온다
            f = bg.copy()
            for j, k in enumerate(order):
                h = int(3 + level[k] * MAX_H)
                xs = x0 + j * (BAR_W + BAR_GAP)
                f[CY - h: CY + h, xs: xs + BAR_W] = color[k]
            p.stdin.write(f.tobytes())
            if progress and i % 150 == 0:
                progress(i / n)
        p.stdin.close()
        p.wait()
    finally:
        if p.poll() is None:
            p.kill()
        if p.returncode not in (0, None) and os.path.exists(tmp):
            os.remove(tmp)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg 실패: " + p.stderr.read().decode("utf-8", "replace")[-300:])
    os.replace(tmp, out)
    return True
