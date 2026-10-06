"""음성 배치와 내보내기: 문장 음성을 시간에 맞춰 놓고, 잘라내기 구간을 뺀 영상에 입힌다."""
import os
import subprocess

import numpy as np

import tts

MAX_TEMPO = 1.2
DUCK_VOLUME = 0.12


def _region_end(project, t):
    """원본 시간 t가 속한 구간의 끝(다음 잘라내기 시작 또는 영상 끝)."""
    end = project.data["info"]["duration"]
    for c in project.data["cuts"]:
        if c["start"] >= t:
            end = min(end, c["start"])
            break
    return end


def plan(project):
    """문장별 배치 계산. 반환: [{sid, start(출력 시간), dur, tempo, overflow, fixed_overflow}]"""
    sents = sorted([s for s in project.data["sentences"] if s.get("tts") and s.get("tts_dur")],
                   key=lambda s: s["start"])
    out = []
    end_prev = -1.0
    prev_start = -1.0
    for i, s in enumerate(sents):
        natural = project.out_time(s["start"]) + float(s.get("pause") or 0.0)
        # 잘라내기 구간을 지나 새 구간에 들어오면 밀림을 초기화한다(고정 지점). 아니면 앞 문장이 끝난 뒤에 시작한다.
        crossed = any(prev_start < c["start"] <= s["start"] for c in project.data["cuts"])
        start = natural if (i == 0 or crossed) else max(natural, end_prev)
        region_end_orig = _region_end(project, s["start"])
        region_end = project.out_time(region_end_orig)
        if i + 1 < len(sents) and sents[i + 1]["start"] < region_end_orig:
            next_natural = project.out_time(sents[i + 1]["start"])
        else:
            next_natural = region_end
        window = max(next_natural - start, 0.3)
        dur = float(s["tts_dur"])
        tempo = min(MAX_TEMPO, dur / window) if dur > window else 1.0
        eff = dur / tempo
        overflow = start + eff > next_natural + 0.05
        fixed_overflow = start + eff > region_end + 0.05
        out.append({"sid": s["id"], "start": round(start, 3), "dur": round(eff, 3), "tempo": round(tempo, 3),
                    "overflow": overflow, "fixed_overflow": fixed_overflow})
        end_prev = start + eff
        prev_start = s["start"]
    return out


def _tempo_clip(path, tempo, tmp):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-filter:a", f"atempo={tempo:.4f}", "-ac", "1",
                    "-ar", str(tts.SR), tmp], check=True)
    return tts.read_wav(tmp)[0]


def build_track(project, placements, progress=None):
    """출력 시간 기준 더빙 트랙(wav)을 만든다."""
    total = project.out_time(project.data["info"]["duration"])
    buf = np.zeros(int(total * tts.SR) + tts.SR, dtype=np.float32)
    by_id = {s["id"]: s for s in project.data["sentences"]}
    tmp = os.path.join(project.sub("out"), "_tempo.wav")
    for k, p in enumerate(placements):
        s = by_id[p["sid"]]
        path = os.path.join(project.dir, "tts", s["tts"])
        if p["tempo"] > 1.001:
            x = _tempo_clip(path, p["tempo"], tmp)
        else:
            x, _ = tts.read_wav(path)
        a = int(p["start"] * tts.SR)
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
    out = os.path.join(project.sub("out"), "dub.wav")
    tts.write_wav(out, buf[:int(total * tts.SR)])
    return out, total


def _select_expr(cuts, var="t"):
    if not cuts:
        return None
    inside = "+".join(f"between({var},{c['start']:.3f},{c['end']:.3f})" for c in cuts)
    return f"not({inside})"


def _fmt_srt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_subtitles(project, placements, out_dir):
    by_id = {s["id"]: s for s in project.data["sentences"]}
    srt = os.path.join(out_dir, project.data["name"] + ".srt")
    txt = os.path.join(out_dir, project.data["name"] + ".txt")
    with open(srt, "w", encoding="utf-8") as f, open(txt, "w", encoding="utf-8") as g:
        for n, p in enumerate(placements, 1):
            s = by_id[p["sid"]]
            end = p["start"] + p["dur"]
            if n < len(placements):
                end = min(end, placements[n]["start"] - 0.05)
            f.write(f"{n}\n{_fmt_srt(p['start'])} --> {_fmt_srt(max(end, p['start'] + 0.3))}\n{s['text']}\n\n")
            g.write(s["text"] + "\n")
    return srt, txt


def out_dir(project):
    """결과 파일 폴더. 설정에 저장 폴더가 있으면 그곳, 없으면 프로젝트의 out 폴더."""
    d = project.data["settings"].get("out_dir")
    if d and os.path.isdir(d):
        return d
    return project.sub("out")


def run(project, want, orig_audio="remove", progress=None, cancel=None):
    """want: {"video","audio","srt","txt"} 중 포함할 것. 결과 파일 경로 목록을 돌려준다."""
    out_dir_ = out_dir(project)
    placements = plan(project)
    files = []
    if "srt" in want or "txt" in want:
        srt, txt = write_subtitles(project, placements, out_dir_)
        files += [p for p, k in ((srt, "srt"), (txt, "txt")) if k in want]
    if not ({"video", "audio"} & set(want)):
        return files, placements
    if progress:
        progress("track", 0.0)
    dub, total = build_track(project, placements, progress=lambda r: progress and progress("track", r))
    if cancel and cancel():
        return files, placements
    video = project.data["video"]
    cuts = project.data["cuts"]
    sel = _select_expr(cuts)
    name = project.data["name"]
    for kind in ("video", "audio"):
        if kind not in want:
            continue
        if cancel and cancel():
            break
        fc = []
        if kind == "video":
            fc.append(f"[0:v]select='{sel}',setpts=N/FRAME_RATE/TB[v]" if sel else "[0:v]copy[v]")
        fc.append(f"[0:a]aselect='{sel}',asetpts=N/SR/TB[oa]" if sel else "[0:a]acopy[oa]")
        if orig_audio == "duck" and project.data["info"].get("has_audio"):
            fc.append(f"[oa]volume={DUCK_VOLUME}[od]")
            fc.append("[od][1:a]amix=inputs=2:duration=first:normalize=0[a]")
        else:
            fc.pop()  # 원음은 쓰지 않는다
            fc.append("[1:a]acopy[a]")
        cmd = ["ffmpeg", "-v", "error", "-y", "-nostdin", "-progress", "pipe:1", "-i", video, "-i", dub,
               "-filter_complex", ";".join(fc)]
        if kind == "video":
            out = os.path.join(out_dir_, name + " (한국어 더빙).mp4")
            cmd += ["-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{total:.3f}", out]
        else:
            out = os.path.join(out_dir_, name + " (한국어 음성).mp3")
            cmd += ["-map", "[a]", "-vn", "-c:a", "libmp3lame", "-b:a", "160k", "-t", f"{total:.3f}", out]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                             errors="replace")
        for line in p.stdout:
            if line.startswith("out_time_ms="):
                try:
                    done = int(line.split("=")[1]) / 1e6 / max(total, 0.001)
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
    return files, placements


if __name__ == "__main__":
    # 배치 규칙 자가 점검: 가짜 프로젝트로 밀림과 초기화를 확인한다
    class P:
        def __init__(self):
            self.data = {"info": {"duration": 100.0}, "cuts": [{"start": 50.0, "end": 60.0}],
                         "sentences": [
                             {"id": 1, "start": 0.0, "end": 2.0, "tts": "a", "tts_dur": 5.0, "pause": 0},
                             {"id": 2, "start": 2.0, "end": 4.0, "tts": "b", "tts_dur": 1.0, "pause": 0},
                             {"id": 3, "start": 48.0, "end": 50.0, "tts": "c", "tts_dur": 1.0, "pause": 0},
                             {"id": 4, "start": 60.0, "end": 62.0, "tts": "d", "tts_dur": 1.0, "pause": 0},
                         ]}

        def out_time(self, t):
            removed = 0.0
            for c in self.data["cuts"]:
                if c["end"] <= t:
                    removed += c["end"] - c["start"]
                elif c["start"] < t:
                    removed += t - c["start"]
            return t - removed

    pl = plan(P())
    assert pl[0]["tempo"] == 1.2 and pl[0]["overflow"], pl[0]          # 5초를 2초 창에: 1.2배로 줄여도 넘침
    assert abs(pl[1]["start"] - 5.0 / 1.2) < 0.01, pl[1]                # 다음 문장은 앞 문장이 끝난 뒤 시작(밀림)
    assert pl[2]["start"] == 48.0 and not pl[2]["overflow"], pl[2]      # 여유가 있으면 밀림이 이어지지 않는다
    assert pl[3]["start"] == 50.0 and pl[3]["tempo"] == 1.0, pl[3]     # 잘라내기 뒤 새 구간: 밀림 초기화, 출력 시간 50초
    assert _fmt_srt(3661.5) == "01:01:01,500"
    print("ok", pl)
