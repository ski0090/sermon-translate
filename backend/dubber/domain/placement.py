"""음성 배치 규칙: 문장 음성을 출력 시간에 놓고(1.2배속 한도, 밀림, 고정 지점) 자막 파일 내용을 만든다."""

MAX_TEMPO = 1.2
DUCK_VOLUME = 0.12
GAP_MIN, GAP_MAX = 0.4, 1.5  # 싱크 없는 오디오에서 문장 사이 쉼(원본 간격을 이 범위로 맞춘다)


def voiced(project):
    """음성이 있는 문장을 시간 순으로."""
    return sorted([s for s in project.data["sentences"] if s.get("tts") and s.get("tts_dur")], key=lambda s: s["start"])


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
    sents = voiced(project)
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


def natural_sequence(project):
    """싱크 없는 오디오용 순서: [(문장, 앞 쉼 초)]. 문장을 원래 속도로 차례대로 잇고, 쉼은 원본 간격을 줄인 값 +
    문장의 앞 쉼."""
    sents = voiced(project)
    out = []
    for i, s in enumerate(sents):
        gap = 0.0
        if i:
            gap = min(max(s["start"] - sents[i - 1]["end"], GAP_MIN), GAP_MAX) + float(s.get("pause") or 0.0)
        out.append((s, gap))
    return out


def fmt_srt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def subtitles(project, placements):
    """자막 파일 내용 (srt, txt)."""
    by_id = {s["id"]: s for s in project.data["sentences"]}
    srt, txt = [], []
    for n, p in enumerate(placements, 1):
        s = by_id[p["sid"]]
        end = p["start"] + p["dur"]
        if n < len(placements):
            end = min(end, placements[n]["start"] - 0.05)
        srt.append(f"{n}\n{fmt_srt(p['start'])} --> {fmt_srt(max(end, p['start'] + 0.3))}\n{s['text']}\n\n")
        txt.append(s["text"] + "\n")
    return "".join(srt), "".join(txt)
