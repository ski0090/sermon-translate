"""쇼츠 영상 만들기(ports.ShortsRenderer): 세로 영상(1080x1920)을 ffmpeg로 만든다.
원본 영상의 자막 띠 위쪽만 잘라 가운데 두고, 소리는 원본 음성을 쓰고, 자막(ASS, domain.shorts.build_ass)을 박는다.
강조 구절은 노란색으로 조금 크게 쓰고, 그 말을 하는 순간 테두리가 번쩍인다."""
import os
import shutil
import subprocess
import threading

import numpy as np

from ...domain import shorts as rules

CREDIT = "조셉 프린스 설교 · {제목}"


def _fonts(env=None):
    """(굵은 글꼴, 보통 글꼴, Bold 표시). 리눅스는 Noto Sans CJK KR, 윈도우는 맑은 고딕."""
    if env:
        return env, env, 1
    try:
        fams = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, encoding="utf-8",
                              errors="replace").stdout
    except OSError:
        fams = ""
    if "Noto Sans CJK KR Black" in fams:
        return "Noto Sans CJK KR Black", "Noto Sans CJK KR Medium", 0
    if "Noto Sans CJK KR" in fams:
        return "Noto Sans CJK KR", "Noto Sans CJK KR", 1
    return "Malgun Gothic", "Malgun Gothic", 1


def _longest_run(mask):
    idx = np.where(mask)[0]
    if not len(idx):
        return None
    runs = np.split(idx, np.where(np.diff(idx) > 1)[0] + 1)
    r = max(runs, key=len)
    return int(r[0]), int(r[-1]) + 1


def content_box(video, inf):
    """원본에서 검은 테두리를 뺀 영역 {x, y, w, h}. 여러 장면의 밝은 곳을 모아 찾는다."""
    vw, vh = inf["width"], inf["height"]
    acc = None
    for k in range(1, 7):
        r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{inf['duration'] * k / 7:.2f}", "-i",
                            video, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"],
                           capture_output=True)
        if len(r.stdout) != vw * vh:
            continue
        a = np.frombuffer(r.stdout, np.uint8).reshape(vh, vw).astype(np.float32)
        acc = a if acc is None else np.maximum(acc, a)
    if acc is None:
        return {"x": 0, "y": 0, "w": vw, "h": vh}
    rows, cols = _longest_run(acc.mean(1) > 24), _longest_run(acc.mean(0) > 24)
    if not rows or not cols or rows[1] - rows[0] < vh * 0.5 or cols[1] - cols[0] < vw * 0.5:
        return {"x": 0, "y": 0, "w": vw, "h": vh}
    x0, y0 = cols[0] + cols[0] % 2, rows[0] + rows[0] % 2
    return {"x": x0, "y": y0, "w": (cols[1] - x0) // 2 * 2, "h": (rows[1] - y0) // 2 * 2}


def _graph(box, fg, ass_name, pre="", post=""):
    """흐린 배경 + 가운데 영상 + 자막. pre는 원본에, post는 합친 화면에(자막을 입히기 전) 거는 필터."""
    b = box
    W, H = rules.W, rules.H
    return (f"[0:v]{pre}crop={b['w']}:{b['h']}:{b['x']}:{b['y']},split[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=10:2,scale={W}:{H},"
            f"eq=brightness=-0.22[bg];"
            f"[b]crop={fg['w']}:{fg['h']}:{fg['x'] - b['x']}:{fg['y'] - b['y']},scale={W}:{fg['out_h']}:flags=lanczos[fg];"
            f"[bg][fg]overlay=0:{rules.FG_Y}{post},ass={ass_name}[v]")


class FfmpegShortsRenderer:
    def __init__(self, font=None, credit=CREDIT):
        self.font = font  # DUBBER_SHORTS_FONT
        self.credit = credit  # DUBBER_SHORTS_CREDIT

    def content_box(self, video, info):
        return content_box(video, info)

    def _ass(self, p, item, seg, t0, dur, fg):
        return rules.build_ass(p.name, item, seg, t0, dur, rules.cap_pos(fg), _fonts(self.font), self.credit)

    def render(self, p, ws, item, box, out, progress=None, cancel=None):
        """쇼츠 영상 하나를 만든다. 다 만들면 out에 두고 True, 중단하면 False."""
        tl = rules.timeline(p)
        seg, nxt = rules.segment(tl, item)
        t0, t1 = rules.span(seg, nxt)
        dur = t1 - t0
        if dur > rules.LIMIT_LEN:
            raise ValueError("쇼츠는 3분을 넘을 수 없습니다")
        work = ws.ensure("work")
        tag = f"short_{item['id']}"
        ass = os.path.join(work, tag + ".ass")
        fg = rules.layout(p.data.get("roi"), box, item.get("xpos", 0.5))
        with open(ass, "w", encoding="utf-8") as f:
            f.write(self._ass(p, item, seg, t0, dur, fg))
        # 소리는 원본 음성(설교자 목소리)을 쇼츠 표준 크기(-14 LUFS)로 맞추고 끝을 0.4초 줄여 끝낸다
        fade = f"afade=t=out:st={max(0.0, dur - 0.4):.3f}:d=0.4"
        audio = (f"[0:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,{fade}[a]"
                 if p.data["info"].get("has_audio", True) else f"anullsrc=r=48000:cl=mono,atrim=0:{dur:.3f}[a]")
        fc = _graph(box, fg, os.path.basename(ass), "", ",fps=30") + ";" + audio
        # 임시 파일 이름에 서버 프로세스 번호를 넣는다(꺼진 서버가 남긴 ffmpeg가 같은 파일에 쓰지 않게). 예전 조각은 지운다
        base = os.path.basename(out)[:-4]
        if os.path.isdir(os.path.dirname(out)):
            for f in os.listdir(os.path.dirname(out)):
                if f.startswith(base + ".") and f.endswith(".part.mp4"):
                    os.remove(os.path.join(os.path.dirname(out), f))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tmp = out[:-4] + f".{os.getpid()}.part.mp4"
        cmd = ["ffmpeg", "-v", "error", "-y", "-nostdin", "-progress", "pipe:1",
               "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", p.data["video"],
               "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "4",
               "-c:a", "aac", "-b:a", "160k", "-t", f"{dur:.3f}", "-movflags", "+faststart", tmp]
        if os.name != "nt" and shutil.which("nice"):
            cmd = ["nice", "-n", "5"] + cmd  # 음성 만들기보다 양보한다
        proc = subprocess.Popen(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace")
        for line in proc.stdout:
            if line.startswith("out_time_ms=") and progress:
                try:
                    progress(min(int(line.split("=")[1]) / 1e6 / dur, 1.0))
                except ValueError:
                    pass
            if cancel and cancel():
                proc.kill()
                break
        proc.wait()
        err = proc.stderr.read()
        if os.path.exists(ass):
            os.remove(ass)
        if cancel and cancel():
            if os.path.exists(tmp):
                os.remove(tmp)
            return False
        if proc.returncode != 0:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise RuntimeError("ffmpeg 실패: " + err[-500:])
        os.replace(tmp, out)
        return True

    def preview(self, p, ws, item, box, t=None):
        """지금 설정으로 한 장면만 그려 JPEG로 돌려준다(영상을 다시 만들기 전에 제목, 강조, 가로 위치를 확인).
        t는 쇼츠 안의 시각(초). 없으면 강조가 있는 첫 문장(없으면 첫 문장)의 1초 뒤."""
        tl = rules.timeline(p)
        seg, nxt = rules.segment(tl, item)
        t0, t1 = rules.span(seg, nxt)
        dur = t1 - t0
        if t is None:
            s = next((s for s in seg if (item.get("emph") or {}).get(str(s["id"]))), seg[0])
            t = s["t"] - t0 + min(1.0, s["d"] / 2)
        t = min(max(float(t), 0.0), dur - 0.05)
        fg = rules.layout(p.data.get("roi"), box, item.get("xpos", 0.5))
        work = ws.ensure("work")
        name = f"short_{item['id']}_{threading.get_ident()}_prev.ass"
        with open(os.path.join(work, name), "w", encoding="utf-8") as f:
            f.write(self._ass(p, item, seg, t0, dur, fg))
        try:
            r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t0 + t:.3f}", "-i", p.data["video"],
                                "-filter_complex", _graph(box, fg, name, post=f",setpts=PTS+{t:.3f}/TB"), "-map", "[v]",
                                "-frames:v", "1", "-f", "image2", "-c:v", "mjpeg", "-q:v", "4", "pipe:1"],
                               cwd=work, capture_output=True)
        finally:
            os.remove(os.path.join(work, name))
        if not r.stdout:
            raise RuntimeError("미리 보기를 만들지 못했습니다: " + r.stderr.decode("utf-8", "replace")[-300:])
        return r.stdout
