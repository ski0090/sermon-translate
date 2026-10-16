"""더빙 결과 만들기(ports.DubRenderer): 배치된 문장 음성으로 더빙 트랙을 만들고, 잘라내기 구간을 뺀 영상에 입힌다."""
import os
import subprocess

import numpy as np

from ...domain import outputs, placement
from . import wav


def _tempo_clip(path, tempo, tmp):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-filter:a", f"atempo={tempo:.4f}", "-ac", "1",
                    "-ar", str(wav.SR), tmp], check=True)
    return wav.read(tmp)[0]


def build_track(project, ws, placements, progress=None):
    """출력 시간 기준 더빙 트랙(wav)을 만든다."""
    total = project.out_time(project.data["info"]["duration"])
    buf = np.zeros(int(total * wav.SR) + wav.SR, dtype=np.float32)
    by_id = {s["id"]: s for s in project.data["sentences"]}
    tmp = os.path.join(ws.ensure("work"), "_tempo.wav")
    for k, p in enumerate(placements):
        s = by_id[p["sid"]]
        path = ws.path("tts", s["tts"])
        if p["tempo"] > 1.001:
            x = _tempo_clip(path, p["tempo"], tmp)
        else:
            x, _ = wav.read(path)
        a = int(p["start"] * wav.SR)
        b = min(a + len(x), len(buf))
        if a < len(buf):
            buf[a:b] += x[:b - a]
        if progress and k % 20 == 0:
            progress(k / max(len(placements), 1))
    if os.path.exists(tmp):
        os.remove(tmp)
    peak = float(np.abs(buf).max()) or 1.0
    if peak > 0.95:
        buf *= 0.95 / peak
    out = os.path.join(ws.ensure("work"), "dub.wav")
    wav.write(out, buf[:int(total * wav.SR)])
    return out, total


def build_natural(project, ws):
    """싱크 없는 오디오용 트랙: 문장을 원래 속도로 차례대로 잇는다(쉼은 domain.placement.natural_sequence)."""
    parts = []
    for s, gap in placement.natural_sequence(project):
        if gap:
            parts.append(np.zeros(int(gap * wav.SR), dtype=np.float32))
        parts.append(wav.read(ws.path("tts", s["tts"]))[0])
    buf = np.concatenate(parts) if parts else np.zeros(wav.SR, dtype=np.float32)
    out = os.path.join(ws.ensure("work"), "natural.wav")
    wav.write(out, buf)
    return out, len(buf) / wav.SR


def _select_expr(cuts, var="t"):
    if not cuts:
        return None
    inside = "+".join(f"between({var},{c['start']:.3f},{c['end']:.3f})" for c in cuts)
    return f"not({inside})"


def write_subtitles(project, placements, out_dir):
    srt_text, txt_text = placement.subtitles(project, placements)
    srt = os.path.join(out_dir, project.name + ".srt")
    txt = os.path.join(out_dir, project.name + ".txt")
    with open(srt, "w", encoding="utf-8") as f:
        f.write(srt_text)
    with open(txt, "w", encoding="utf-8") as g:
        g.write(txt_text)
    return srt, txt


class FfmpegDubRenderer:
    def __init__(self, sleep_renderer):
        self.sleep = sleep_renderer

    def natural_track(self, project, ws):
        return build_natural(project, ws)

    def export(self, project, ws, placements, want, orig_audio="remove", progress=None, cancel=None):
        """want: {"video","audio","srt","txt","sleep"} 중 포함할 것. 결과 파일 경로 목록을 돌려준다.
        sleep은 자면서 듣는 설교 영상(이퀄라이저 화면 + 싱크 없이 이은 음성)."""
        out_dir_ = ws.ensure(outputs.out_name(project.name))
        files = []
        if "srt" in want or "txt" in want:
            srt, txt = write_subtitles(project, placements, out_dir_)
            files += [p for p, k in ((srt, "srt"), (txt, "txt")) if k in want]
        if not ({"video", "audio", "sleep"} & set(want)):
            return files
        # 원음을 깔면 영상과 맞아야 하므로 오디오도 영상 타이밍을 따른다. 아니면 오디오는 싱크 없이 자연스럽게 잇는다.
        natural = not (orig_audio == "duck" and project.data["info"].get("has_audio"))
        if "video" in want or not natural:
            if progress:
                progress("track", 0.0)
            dub, total = build_track(project, ws, placements, progress=lambda r: progress and progress("track", r))
            if cancel and cancel():
                return files
        video = project.data["video"]
        cuts = project.data["cuts"]
        sel = _select_expr(cuts)
        name = project.name
        for kind in ("video", "audio"):
            if kind not in want:
                continue
            if cancel and cancel():
                break
            if kind == "audio" and natural:
                src, length = build_natural(project, ws)
                out = os.path.join(out_dir_, outputs.audio(name))
                cmd = ["ffmpeg", "-v", "error", "-y", "-nostdin", "-progress", "pipe:1", "-i", src,
                       "-c:a", "libmp3lame", "-b:a", "160k", out]
            else:
                length = total
                fc = []
                if kind == "video":
                    fc.append(f"[0:v]select='{sel}',setpts=N/FRAME_RATE/TB[v]" if sel else "[0:v]copy[v]")
                fc.append(f"[0:a]aselect='{sel}',asetpts=N/SR/TB[oa]" if sel else "[0:a]acopy[oa]")
                if orig_audio == "duck" and project.data["info"].get("has_audio"):
                    fc.append(f"[oa]volume={placement.DUCK_VOLUME}[od]")
                    fc.append("[od][1:a]amix=inputs=2:duration=first:normalize=0[a]")
                else:
                    fc.pop()  # 원음은 쓰지 않는다
                    fc.append("[1:a]acopy[a]")
                cmd = ["ffmpeg", "-v", "error", "-y", "-nostdin", "-progress", "pipe:1", "-i", video, "-i", dub,
                       "-filter_complex", ";".join(fc)]
                if kind == "video":
                    out = os.path.join(out_dir_, outputs.dubbed(name))
                    cmd += ["-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{total:.3f}", out]
                else:
                    out = os.path.join(out_dir_, outputs.audio(name))
                    cmd += ["-map", "[a]", "-vn", "-c:a", "libmp3lame", "-b:a", "160k", "-t", f"{total:.3f}", out]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                 errors="replace")
            for line in p.stdout:
                if line.startswith("out_time_ms="):
                    try:
                        done = int(line.split("=")[1]) / 1e6 / max(length, 0.001)
                        if progress:
                            progress(kind, min(done, 1.0))
                    except ValueError:
                        pass
                if cancel and cancel():
                    p.kill()
                    break
            p.wait()
            err = p.stderr.read()
            if p.returncode != 0 and not (cancel and cancel()):
                raise RuntimeError("ffmpeg 실패: " + err[-500:])
            files.append(out)
        if "sleep" in want and not (cancel and cancel()):
            src, _ = build_natural(project, ws)
            out = os.path.join(out_dir_, outputs.sleep(name))
            if self.sleep.render(src, out, name, progress=lambda r: progress and progress("sleep", r), cancel=cancel):
                files.append(out)
        return files
