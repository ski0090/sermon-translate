"""쇼츠: 더빙한 설교에서 짧은 구간을 골라(Claude) 세로 영상(1080x1920)을 만든다.
원본 영상의 자막 띠 위쪽만 잘라 가운데 두고, 더빙 음성으로 소리를 다시 만들고, 음성에 맞춰 큰 자막을 새로 박는다.
강조 구절은 노란색으로 조금 크게 쓰고, 그 말을 하는 순간 테두리가 번쩍인다.
상태는 프로젝트 폴더의 shorts.json에 둔다(project.json과 따로 저장해서 음성 작업과 서로 덮어쓰지 않게)."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading

import numpy as np

import ai
import export
import tts

W, H = 1080, 1920
FG_Y = 470                  # 가운데 영상의 위쪽 끝
FG_ASPECT = 1.8             # 가운데 영상의 가로:세로. 원본에서 이 비율로 잘라 확대한다
MIN_LEN, MAX_LEN = 25, 75   # Claude에게 고르게 하는 길이(초)
LIMIT_LEN = 180             # 유튜브 쇼츠 최대 길이(초)
CAP_SIZE, CAP_WIDTH = 90, 9.0  # 자막 글자 크기와 한 줄 폭(한글 글자 수). 오른쪽 유튜브 버튼에 가리지 않을 만큼
TITLE_SIZE = 84
YELLOW, WHITE, FLASH = "&H4DD8FF&", "&HFFFFFF&", "&H0050FF&"
CREDIT = os.environ.get("DUBBER_SHORTS_CREDIT", "조셉 프린스 설교 · {제목}")
STYLE_VERSION = 1           # 화면 모양을 바꾸면 올린다(이미 만든 쇼츠가 '고친 내용 반영 안 됨'으로 보인다)
STATE = "shorts.json"

SUGGEST_PROMPT = """다음은 한국어로 더빙한 설교 한 편의 문장 목록입니다. n은 문장 번호, t는 시작 시각(초), d는 길이(초)입니다.
이 설교에서 유튜브 쇼츠로 만들 구간을 {n}개 고르세요.

조건:
- 이어진 문장들로 된 구간이고, 길이(첫 문장의 t부터 마지막 문장의 t+d까지)는 {lo}~{hi}초입니다. 40~60초가 가장 좋습니다.
- 앞뒤 설명 없이 이 구간만 봐도 이해되고, 메시지가 하나로 분명하며, 마지막 문장에서 깔끔하게 끝나야 합니다.
- 첫 문장이 보는 사람의 관심을 바로 끄는 곳이면 더 좋습니다.
- 성경 구절을 읽기만 하는 부분, 인사, 광고, 찬양, "몇 장을 보세요" 같은 안내는 피하세요.
- 구간끼리 겹치지 않게 하세요.{exclude}

구간마다:
- title: 화면 위에 크게 띄울 제목 두 줄. 줄마다 띄어쓰기를 포함해 12자 이내로, 구간의 핵심 메시지를 짧고 강하게.
- emph: 강조할 구절. 문장 번호를 키로, 그 문장에 있는 글자를 띄어쓰기까지 그대로 옮긴 짧은 구절(2~15자) 목록. 구간 전체에서 3~6개.
- reason: 이 구간을 고른 이유 한 줄.

설명 없이 JSON 배열만 출력하세요:
[{{"start": 첫 문장 번호, "end": 마지막 문장 번호, "title": ["첫 줄", "둘째 줄"], "emph": {{"문장 번호": ["구절"]}}, "reason": "..."}}]

문장 목록:
"""

_locks = {}
_glock = threading.Lock()


# ---------- 상태 파일 ----------
def lock(d):
    with _glock:
        return _locks.setdefault(os.path.abspath(d), threading.RLock())


def load(d):
    path = os.path.join(d, STATE)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"items": [], "next_id": 1, "suggest": {"status": "idle"}}


def save(d, st):
    path = os.path.join(d, STATE)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def change(d, fn):
    """상태를 읽고 fn(상태)로 고친 뒤 저장한다. fn의 반환값을 돌려준다."""
    with lock(d):
        st = load(d)
        out = fn(st)
        save(d, st)
        return out


def find(st, sid):
    return next((x for x in st["items"] if x["id"] == sid), None)


# ---------- 문장과 구간 ----------
def timeline(p):
    """문장을 시간 순으로: [{"id", "text", "t", "d", "tempo"}]. t는 더빙 결과 영상 기준 시작, d는 음성 길이.
    음성이 없는 문장은 t가 None이다."""
    pl = {x["sid"]: x for x in export.plan(p)}
    out = []
    for s in sorted(p.data["sentences"], key=lambda s: s["start"]):
        x = pl.get(s["id"])
        out.append({"id": s["id"], "text": s["text"], "t": x["start"] if x else None, "d": x["dur"] if x else None,
                    "tempo": x["tempo"] if x else 1.0})
    return out


def segment(tl, item):
    """구간의 문장들과 그 다음 문장. 문장이 없어졌거나 음성이 없는 문장이 끼어 있으면 ValueError."""
    ids = [s["id"] for s in tl]
    if item["start"] not in ids or item["end"] not in ids:
        raise ValueError("구간의 문장을 찾지 못했습니다(문장을 합치거나 지웠을 수 있습니다)")
    a, b = ids.index(item["start"]), ids.index(item["end"])
    if a > b:
        raise ValueError("시작 문장이 끝 문장보다 뒤에 있습니다")
    seg = tl[a:b + 1]
    if any(s["t"] is None for s in seg):
        raise ValueError("음성이 없는 문장이 구간에 있습니다")
    return seg, (tl[b + 1] if b + 1 < len(tl) else None)


def span(seg, nxt):
    """구간의 시작과 끝(결과 영상 시간). 앞은 조금 띄우고, 뒤는 다음 문장 음성이 들리기 전까지 여운을 둔다."""
    t0 = max(0.0, seg[0]["t"] - 0.25)
    end = seg[-1]["t"] + seg[-1]["d"]
    t1 = end + 0.6
    if nxt and nxt["t"] is not None:
        t1 = max(end + 0.1, min(t1, nxt["t"] - 0.05))
    return t0, t1


def info(p, item, tl=None):
    """화면에 보일 구간 정보: {"at", "len"} 또는 {"invalid"}."""
    try:
        seg, nxt = segment(tl or timeline(p), item)
    except ValueError as e:
        return {"invalid": str(e)}
    t0, t1 = span(seg, nxt)
    return {"at": round(t0, 2), "len": round(t1 - t0, 2)}


def signature(p, item, tl=None):
    """만든 영상과 지금 설정이 같은지 비교하는 값. 구간, 제목, 강조, 위치, 문장 글과 음성이 들어간다."""
    try:
        seg, _ = segment(tl or timeline(p), item)
    except ValueError:
        return None
    tts_of = {s["id"]: s.get("tts") for s in p.data["sentences"]}
    emph = item.get("emph") or {}
    key = [STYLE_VERSION, item["start"], item["end"], item.get("title"), item.get("xpos", 0.5),
           [(s["text"], tts_of.get(s["id"]), round(s["t"], 2), emph.get(str(s["id"]))) for s in seg]]
    return hashlib.md5(json.dumps(key, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def orig_time(p, t):
    """결과 영상 시간 -> 원본 영상 시간(잘라내기 구간을 다시 넣는다). project.out_time의 반대."""
    for c in p.data["cuts"]:  # 시작 순으로 정렬되고 겹치지 않는다(set_cuts)
        if c["start"] <= t:
            t += c["end"] - c["start"]
        else:
            break
    return t


# ---------- Claude로 후보 고르기 ----------
def _clean(tl, a, taken):
    """Claude가 고른 구간 하나를 검사해 항목으로 만든다. 틀리면 None."""
    try:
        item = {"start": int(a["start"]), "end": int(a["end"])}
        seg, nxt = segment(tl, item)
    except (KeyError, TypeError, ValueError):
        return None
    t0, t1 = span(seg, nxt)
    if not (MIN_LEN * 0.6 <= t1 - t0 <= LIMIT_LEN):
        return None
    idx = {s["id"]: k for k, s in enumerate(tl)}
    a0, b0 = idx[item["start"]], idx[item["end"]]
    if any(a0 <= idx[e] and idx[s] <= b0 for s, e in taken if s in idx and e in idx):
        return None
    title = [str(x).strip() for x in (a.get("title") or []) if str(x).strip()][:2]
    if isinstance(a.get("title"), str):
        title = [a["title"].strip()]
    title = (title + ["", ""])[:2]
    emph = {}
    raw = a.get("emph") if isinstance(a.get("emph"), dict) else {}
    for s in seg:
        ph = raw.get(str(s["id"])) or raw.get(s["id"]) or []
        ok = [x.strip() for x in ph if isinstance(x, str) and len(x.strip()) >= 2 and x.strip() in s["text"]]
        if ok:
            emph[str(s["id"])] = list(dict.fromkeys(ok))
    taken.append((item["start"], item["end"]))
    return dict(item, title=title, emph=emph, reason=str(a.get("reason") or "").strip(), xpos=0.5)


def suggest(p, n=3, tool="claude", taken=()):
    """Claude에게 쇼츠 구간 n개를 고르게 한다. taken: 이미 있는 구간 [(start, end)]. 반환: 항목 목록."""
    tl = timeline(p)
    rows = [{"n": s["id"], "t": round(s["t"], 1), "d": round(s["d"], 1), "text": s["text"]} for s in tl if s["t"] is not None]
    if not rows:
        raise RuntimeError("음성이 있는 문장이 없습니다")
    taken = list(taken)
    exclude = ("\n- 이미 고른 구간과도 겹치지 않게 하세요: " + ", ".join(f"{s}~{e}번" for s, e in taken)) if taken else ""
    prompt = SUGGEST_PROMPT.format(n=n, lo=MIN_LEN, hi=MAX_LEN, exclude=exclude) + "\n".join(
        json.dumps(r, ensure_ascii=False) for r in rows)
    err = None
    for _ in range(2):
        try:
            arr = ai._parse_json_array(ai.run_tool(prompt, tool, timeout=ai.TIDY_TIMEOUT))
        except ai.UsageLimit:
            raise
        except Exception as e:  # noqa  형식이 틀리면 한 번 더 묻는다
            err = e
            continue
        got = [c for c in (_clean(tl, a, taken) for a in arr if isinstance(a, dict)) if c]
        if got:
            return got[:n]
        err = RuntimeError("AI가 고른 구간이 조건에 맞지 않습니다")
    raise RuntimeError(f"쇼츠 후보를 고르지 못했습니다: {err}")


# ---------- 영상 만들기 ----------
def _fonts():
    """(굵은 글꼴, 보통 글꼴, Bold 표시). 리눅스는 Noto Sans CJK KR, 윈도우는 맑은 고딕."""
    env = os.environ.get("DUBBER_SHORTS_FONT")
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


def content_box(p):
    """원본에서 검은 테두리를 뺀 영역 {x, y, w, h}. 여러 장면의 밝은 곳을 모아 찾는다."""
    inf = p.data["info"]
    vw, vh = inf["width"], inf["height"]
    acc = None
    for k in range(1, 7):
        r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{inf['duration'] * k / 7:.2f}", "-i",
                            p.data["video"], "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"],
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


def layout(p, box, xpos=0.5):
    """가운데 영상: 원본에서 잘라낼 곳(원본 좌표)과 화면에서의 높이. 원본 자막 띠 위쪽만 쓴다."""
    top, bot = box["y"], box["y"] + box["h"]
    roi = p.data.get("roi")
    if roi and roi["y"] - 2 > top + box["h"] * 0.4:
        bot = min(bot, roi["y"] - 2)
    fh = (bot - top) // 2 * 2
    cw = min(box["w"], int(fh * FG_ASPECT)) // 2 * 2
    cx = box["x"] + int((box["w"] - cw) * min(max(xpos, 0.0), 1.0)) // 2 * 2
    return {"x": cx, "y": top, "w": cw, "h": fh, "out_h": int(round(W * fh / cw / 2)) * 2}


def vw(s):
    """화면 폭 어림: 한글 1, 영문·숫자 0.55, 띄어쓰기 0.3."""
    return sum(0.3 if c == " " else 0.55 if ord(c) < 128 else 1.0 for c in s)


def chunks(words, maxw=CAP_WIDTH):
    """단어 [(글, 강조)]를 두 줄 이하 덩어리로 나눈다. 줄 길이를 고르게 하고, 문장 부호 뒤에서 끊는 것을 좋아한다."""
    width = lambda ws: vw(" ".join(x[0] for x in ws))  # noqa
    target = width(words) / max(1, -(-width(words) // maxw))  # 줄 수를 최소로 할 때의 평균 줄 길이
    lines, cur = [], []
    for w in words:
        if cur and width(cur + [w]) > maxw:
            lines.append(cur)
            cur = []
        cur.append(w)
        if width(cur) >= target * 0.98 or (re.search(r"[.?!,]['\"’”]?$", w[0]) and width(cur) >= target * 0.5):
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return [lines[i:i + 2] for i in range(0, len(lines), 2)]


def mark(text, phrases):
    """문장을 단어로 나누고, 강조 구절에 걸친 단어를 표시한다."""
    flags = [False] * len(text)
    for ph in phrases:
        i = text.find(ph)
        if i >= 0:
            flags[i:i + len(ph)] = [True] * len(ph)
    out, i = [], 0
    for w in text.split(" "):
        if w:
            out.append((w, any(flags[i:i + len(w)])))
        i += len(w) + 1
    return out


def _ass_text(s):
    return s.replace("\\", "＼").replace("{", "(").replace("}", ")").replace("\n", " ")


def _ts(t):
    t = max(t, 0.0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _pop(base):
    """덩어리가 나타날 때 살짝 튀어나오는 효과(크기 base%)."""
    return rf"\fscx{base * 0.82:.0f}\fscy{base * 0.82:.0f}\t(0,90,\fscx{base * 1.06:.0f}\fscy{base * 1.06:.0f})" \
           rf"\t(90,170,\fscx{base:.0f}\fscy{base:.0f})"


def build_ass(p, item, seg, t0, dur, cap_y):
    heavy, light, bold = _fonts()
    events = []
    for s in seg:
        groups = chunks(mark(s["text"], (item.get("emph") or {}).get(str(s["id"]), [])))
        total = sum(len(w) for g in groups for line in g for w, _ in line) or 1
        t = s["t"] - t0
        for g in groups:
            n = sum(len(w) for line in g for w, _ in line)
            d = s["d"] * n / total
            done, lines = 0, []
            for line in g:
                parts = []
                for w, e in line:
                    at = int(d * 1000 * done / max(n, 1))  # 이 단어를 말하는 때(글자 비율로 어림)
                    if e:
                        tag = rf"\c{YELLOW}{_pop(112)}\t({at},{at + 90},\3c{FLASH}\bord13\blur3)" \
                              rf"\t({at + 90},{at + 450},\3c&H000000&\bord8\blur0)"
                    else:
                        tag = rf"\c{WHITE}\bord8\blur0{_pop(100)}"
                    parts.append("{" + tag + "}" + _ass_text(w))
                    done += len(w)
                lines.append(" ".join(parts))
            events.append([t, t + d, rf"{{\an5\pos({W // 2},{cap_y})}}" + r"\N".join(lines)])
            t += d
    for a, b in zip(events, events[1:]):  # 문장 사이 짧은 쉼에는 앞 자막을 남겨 깜빡이지 않게
        if 0 < b[0] - a[1] < 0.7:
            a[1] = b[0]
    title = [_ass_text(x) for x in item.get("title") or [] if x.strip()]
    tsize = min(TITLE_SIZE, int(960 / max([vw(x) for x in title] + [1])))
    name = re.sub(r"^\d+\s*", "", p.data["name"])
    credit = _ass_text(CREDIT.replace("{제목}", name).replace("{이름}", p.data["name"]))
    out = [f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{heavy},{CAP_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,{bold},0,0,0,100,100,0,0,1,8,4,5,40,40,0,1
Style: Title,{heavy},{tsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,{bold},0,0,0,100,100,0,0,1,7,3,8,40,40,0,1
Style: Credit,{light},38,&H33FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,2,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""]
    if title:
        lines = [title[0]] + [rf"{{\c{YELLOW}}}" + x for x in title[1:]]
        out.append(rf"Dialogue: 0,{_ts(0)},{_ts(dur)},Title,,0,0,0,,{{\pos({W // 2},180)\fad(250,0)}}" + r"\N".join(lines))
    out.append(rf"Dialogue: 0,{_ts(0)},{_ts(dur)},Credit,,0,0,0,,{{\pos({W // 2},1760)}}{credit}")
    out += [f"Dialogue: 1,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{txt}" for a, b, txt in events]
    return "\n".join(out) + "\n"


def build_audio(p, seg, t0, dur, out):
    """구간의 더빙 음성. 더빙 결과 영상과 같은 자리·같은 빠르기로 놓는다."""
    tts_of = {s["id"]: s.get("tts") for s in p.data["sentences"]}
    buf = np.zeros(int(dur * tts.SR) + 1, dtype=np.float32)
    tmp = out + ".tempo.wav"
    for s in seg:
        path = os.path.join(p.dir, "tts", tts_of[s["id"]])
        x = export._tempo_clip(path, s["tempo"], tmp) if s["tempo"] > 1.001 else tts.read_wav(path)[0]
        a = int((s["t"] - t0) * tts.SR)
        b = min(a + len(x), len(buf))
        if a < len(buf):
            buf[a:b] += x[:b - a]
    if os.path.exists(tmp):
        os.remove(tmp)
    peak = float(np.abs(buf).max()) or 1.0
    if peak > 0.95:
        buf *= 0.95 / peak
    fade = int(0.3 * tts.SR)
    if len(buf) > 2 * fade:
        buf[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    tts.write_wav(out, buf)


def render(p, item, out, box, progress=None, cancel=None):
    """쇼츠 영상 하나를 만든다. 다 만들면 out에 두고 True, 중단하면 False."""
    tl = timeline(p)
    seg, nxt = segment(tl, item)
    t0, t1 = span(seg, nxt)
    dur = t1 - t0
    if dur > LIMIT_LEN:
        raise ValueError("쇼츠는 3분을 넘을 수 없습니다")
    work = p.sub("work")
    tag = f"short_{item['id']}"
    wav, ass = os.path.join(work, tag + ".wav"), os.path.join(work, tag + ".ass")
    build_audio(p, seg, t0, dur, wav)
    fg = layout(p, box, item.get("xpos", 0.5))
    with open(ass, "w", encoding="utf-8") as f:
        f.write(build_ass(p, item, seg, t0, dur, cap_pos(fg)))
    # 원본 시간으로 바꾸고, 구간 안의 잘라내기는 빼고 잇는다
    o0, o1 = orig_time(p, t0), orig_time(p, t1)
    inside = [(max(c["start"], o0) - o0, min(c["end"], o1) - o0) for c in p.data["cuts"] if c["end"] > o0 and c["start"] < o1]
    sel = ("select='not(" + "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in inside) + ")',setpts=N/FRAME_RATE/TB,"
           if inside else "")
    fc = _graph(box, fg, os.path.basename(ass), sel, ",fps=30")
    # 임시 파일 이름에 서버 프로세스 번호를 넣는다(꺼진 서버가 남긴 ffmpeg가 같은 파일에 쓰지 않게). 예전 조각은 지운다
    base = os.path.basename(out)[:-4]
    if os.path.isdir(os.path.dirname(out)):
        for f in os.listdir(os.path.dirname(out)):
            if f.startswith(base + ".") and f.endswith(".part.mp4"):
                os.remove(os.path.join(os.path.dirname(out), f))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out[:-4] + f".{os.getpid()}.part.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-nostdin", "-progress", "pipe:1",
           "-ss", f"{o0:.3f}", "-t", f"{o1 - o0:.3f}", "-i", p.data["video"], "-i", wav,
           "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
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
    for f in (wav, ass):
        if os.path.exists(f):
            os.remove(f)
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


def cap_pos(fg):
    """자막 덩어리의 가운데 높이: 가운데 영상 아래."""
    return min(FG_Y + fg["out_h"] + 230, 1480)


def _graph(box, fg, ass_name, pre="", post=""):
    """흐린 배경 + 가운데 영상 + 자막. pre는 원본에, post는 합친 화면에(자막을 입히기 전) 거는 필터."""
    b = box
    return (f"[0:v]{pre}crop={b['w']}:{b['h']}:{b['x']}:{b['y']},split[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=10:2,scale={W}:{H},"
            f"eq=brightness=-0.22[bg];"
            f"[b]crop={fg['w']}:{fg['h']}:{fg['x'] - b['x']}:{fg['y'] - b['y']},scale={W}:{fg['out_h']}:flags=lanczos[fg];"
            f"[bg][fg]overlay=0:{FG_Y}{post},ass={ass_name}[v]")


def preview(p, item, box, t=None):
    """지금 설정으로 한 장면만 그려 JPEG로 돌려준다(영상을 다시 만들기 전에 제목, 강조, 가로 위치를 확인).
    t는 쇼츠 안의 시각(초). 없으면 강조가 있는 첫 문장(없으면 첫 문장)의 1초 뒤."""
    tl = timeline(p)
    seg, nxt = segment(tl, item)
    t0, t1 = span(seg, nxt)
    dur = t1 - t0
    if t is None:
        s = next((s for s in seg if (item.get("emph") or {}).get(str(s["id"]))), seg[0])
        t = s["t"] - t0 + min(1.0, s["d"] / 2)
    t = min(max(float(t), 0.0), dur - 0.05)
    fg = layout(p, box, item.get("xpos", 0.5))
    work = p.sub("work")
    name = f"short_{item['id']}_{threading.get_ident()}_prev.ass"
    with open(os.path.join(work, name), "w", encoding="utf-8") as f:
        f.write(build_ass(p, item, seg, t0, dur, cap_pos(fg)))
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{orig_time(p, t0 + t):.3f}", "-i", p.data["video"],
                            "-filter_complex", _graph(box, fg, name, post=f",setpts=PTS+{t:.3f}/TB"), "-map", "[v]",
                            "-frames:v", "1", "-f", "image2", "-c:v", "mjpeg", "-q:v", "4", "pipe:1"],
                           cwd=work, capture_output=True)
    finally:
        os.remove(os.path.join(work, name))
    if not r.stdout:
        raise RuntimeError("미리 보기를 만들지 못했습니다: " + r.stderr.decode("utf-8", "replace")[-300:])
    return r.stdout


def out_path(p, item):
    """결과: "<영상 이름> 한국어 더빙/쇼츠/<영상 이름> 쇼츠 <번호>.mp4" (제목을 고쳐도 이름은 그대로)."""
    return os.path.join(p.sub(export.out_name(p), "쇼츠"), f"{p.data['name']} 쇼츠 {item['id']}.mp4")


if __name__ == "__main__":
    # AI와 영상 없이 구간 계산과 자막 나누기를 확인한다
    class P:
        def __init__(self):
            self.data = {"cuts": [{"start": 50.0, "end": 60.0}], "sentences": []}
    pp = P()
    assert orig_time(pp, 45) == 45 and orig_time(pp, 55) == 65 and orig_time(pp, 50) == 60
    tl = [{"id": 1, "text": "가", "t": 0.0, "d": 10.0, "tempo": 1}, {"id": 2, "text": "나 다", "t": 10.0, "d": 20.0, "tempo": 1},
          {"id": 3, "text": "라", "t": None, "d": None, "tempo": 1}, {"id": 4, "text": "마", "t": 40.0, "d": 25.0, "tempo": 1},
          {"id": 5, "text": "바 사", "t": 65.2, "d": 30.0, "tempo": 1}]
    seg, nxt = segment(tl, {"start": 1, "end": 2})
    assert [s["id"] for s in seg] == [1, 2] and nxt["id"] == 3
    assert span(seg, nxt) == (0.0, 30.6)
    try:
        segment(tl, {"start": 2, "end": 4})
        raise AssertionError("음성 없는 문장")
    except ValueError:
        pass
    assert span(*segment(tl, {"start": 4, "end": 4})) == (39.75, 65.15)  # 다음 문장 바로 앞에서 끊는다
    taken = []
    c = _clean(tl, {"start": 1, "end": 2, "title": ["하나", "둘"], "emph": {"2": ["나 다", "없는 말", "다"]}}, taken)
    assert c["emph"] == {"2": ["나 다"]} and c["title"] == ["하나", "둘"] and taken == [(1, 2)], c
    assert _clean(tl, {"start": 2, "end": 2}, taken) is None             # 겹침
    assert _clean(tl, {"start": 5, "end": 4}, taken) is None             # 순서
    assert _clean(tl, {"start": 4, "end": 5, "title": "한 줄"}, taken)["title"] == ["한 줄", ""]
    assert mark("우리 죄는 하나님이 아시는", ["하나님이 아시"]) == [("우리", False), ("죄는", False), ("하나님이", True), ("아시는", True)]
    words = mark("먼저 알려드릴 것은, 우리의 죄 사함이 우리가 아는 죄를 기준으로 사하는 게 아니라 하나님이 아시는 죄를 기준으로 사함 받습니다.", [])
    g = chunks(words)
    lines = [" ".join(w for w, _ in line) for grp in g for line in grp]
    assert " ".join(lines) == " ".join(w for w, _ in words) and all(vw(x) <= CAP_WIDTH for x in lines), lines
    assert all(len(grp) <= 2 for grp in g) and len(lines) <= 8, lines
    print("ok", lines)
