"""쇼츠 규칙: 구간 계산, AI가 고른 후보 검사, 직접 추가와 고치기, 세로 화면 배치, 자막(ASS) 만들기.
영상을 실제로 만드는 일은 렌더러(ports.ShortsRenderer)가 한다. 상태는 프로젝트 폴더의 shorts.json에 둔다
(project.json과 따로 저장해서 음성 작업과 서로 덮어쓰지 않게)."""
import hashlib
import json
import re
import time

W, H = 1080, 1920
FG_Y = 470                  # 가운데 영상의 위쪽 끝
FG_ASPECT = 1.8             # 가운데 영상의 가로:세로. 원본에서 이 비율로 잘라 확대한다
MIN_LEN, MAX_LEN = 25, 75   # Claude에게 고르게 하는 길이(초)
LIMIT_LEN = 180             # 유튜브 쇼츠 최대 길이(초)
CAP_SIZE, CAP_WIDTH = 90, 9.0  # 자막 글자 크기와 한 줄 폭(한글 글자 수). 오른쪽 유튜브 버튼에 가리지 않을 만큼
TITLE_SIZE = 84
YELLOW, WHITE, FLASH = "&H4DD8FF&", "&HFFFFFF&", "&H0050FF&"
STYLE_VERSION = 3           # 화면 모양을 바꾸면 올린다(이미 만든 쇼츠가 '고친 내용 반영 안 됨'으로 보인다)
STATE = "shorts.json"


# ---------- 상태 ----------
def empty_state():
    return {"items": [], "next_id": 1, "suggest": {"status": "idle"}}


def find(st, sid):
    return next((x for x in st["items"] if x["id"] == sid), None)


# ---------- 문장과 구간 ----------
def timeline(p):
    """문장을 시간 순으로: [{"id", "text", "t", "d"}]. 쇼츠는 원본 음성을 쓰므로 t, d는 원본 영상에서 그 문장
    자막이 보이는 시작과 길이다(더빙 음성과 상관없다)."""
    return [{"id": s["id"], "text": s["text"], "t": s["start"], "d": max(0.3, s["end"] - s["start"])}
            for s in sorted(p.data["sentences"], key=lambda s: s["start"])]


def segment(tl, item):
    """구간의 문장들과 그 다음 문장. 문장이 없어졌으면 ValueError."""
    ids = [s["id"] for s in tl]
    if item["start"] not in ids or item["end"] not in ids:
        raise ValueError("구간의 문장을 찾지 못했습니다(문장을 합치거나 지웠을 수 있습니다)")
    a, b = ids.index(item["start"]), ids.index(item["end"])
    if a > b:
        raise ValueError("시작 문장이 끝 문장보다 뒤에 있습니다")
    seg = tl[a:b + 1]
    return seg, (tl[b + 1] if b + 1 < len(tl) else None)


def span(seg, nxt):
    """구간의 시작과 끝(원본 영상 시간). 앞은 조금 띄우고, 뒤는 다음 문장이 시작하기 전까지 여운을 둔다."""
    t0 = max(0.0, seg[0]["t"] - 0.3)
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
    """만든 영상과 지금 설정이 같은지 비교하는 값. 구간, 제목, 강조, 위치, 문장 글과 시간이 들어간다."""
    try:
        seg, _ = segment(tl or timeline(p), item)
    except ValueError:
        return None
    emph = item.get("emph") or {}
    key = [STYLE_VERSION, item["start"], item["end"], item.get("title"), item.get("xpos", 0.5),
           [(s["text"], round(s["t"], 2), round(s["d"], 2), emph.get(str(s["id"]))) for s in seg]]
    return hashlib.md5(json.dumps(key, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def orig_time(p, t):
    """결과 영상 시간 -> 원본 영상 시간(잘라내기 구간을 다시 넣는다). Project.out_time의 반대."""
    for c in p.data["cuts"]:  # 시작 순으로 정렬되고 겹치지 않는다(set_cuts)
        if c["start"] <= t:
            t += c["end"] - c["start"]
        else:
            break
    return t


# ---------- 후보, 직접 추가, 고치기 ----------
def candidate(tl, a, taken):
    """AI가 고른 구간 하나를 검사해 항목으로 만든다. 틀리면 None. 고른 구간은 taken에 더한다."""
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


def manual_item(tl, at):
    """직접 추가: 원본 영상의 at초에서 시작하는 문장부터 40초쯤(만들기 전 상태). id는 상태에 넣을 때 붙인다."""
    k = next((k for k, s in enumerate(tl) if s["t"] is not None and s["t"] + s["d"] > at), None)
    if k is None:
        raise ValueError("그 시각 뒤에 음성이 있는 문장이 없습니다")
    e = k
    while e + 1 < len(tl) and tl[e + 1]["t"] is not None and tl[e]["t"] + tl[e]["d"] - tl[k]["t"] < 40:
        e += 1
    return {"start": tl[k]["id"], "end": tl[e]["id"], "title": ["", ""], "emph": {}, "reason": "직접 추가",
            "xpos": 0.5, "status": "draft", "created": time.time()}


def edit_item(p, it, body, tl):
    """구간, 제목, 강조, 가로 위치를 고친다. 영상은 '다시 만들기'를 눌러야 바뀐다."""
    new = dict(it)
    for k in ("start", "end"):
        if k in body:
            new[k] = int(body[k])
    if "title" in body:
        new["title"] = ([str(x).strip()[:30] for x in body["title"] or []] + ["", ""])[:2]
    if "emph" in body:
        new["emph"] = {str(k): [str(v).strip() for v in vs if str(v).strip()]
                       for k, vs in (body["emph"] or {}).items() if vs}
    if "xpos" in body:
        new["xpos"] = min(1.0, max(0.0, float(body["xpos"])))
    inf = info(p, new, tl)
    if "invalid" in inf:
        raise ValueError(inf["invalid"])
    if inf["len"] > LIMIT_LEN:
        raise ValueError("쇼츠는 3분을 넘을 수 없습니다")
    it.update(new)  # 구간 밖 문장의 강조는 남겨 둔다(구간을 다시 넓히면 되살아난다)


# ---------- 세로 화면 ----------
def layout(roi, box, xpos=0.5):
    """가운데 영상: 원본에서 잘라낼 곳(원본 좌표)과 화면에서의 높이. 원본 자막 띠 위쪽만 쓴다."""
    top, bot = box["y"], box["y"] + box["h"]
    if roi and roi["y"] - 2 > top + box["h"] * 0.4:
        bot = min(bot, roi["y"] - 2)
    fh = (bot - top) // 2 * 2
    cw = min(box["w"], int(fh * FG_ASPECT)) // 2 * 2
    cx = box["x"] + int((box["w"] - cw) * min(max(xpos, 0.0), 1.0)) // 2 * 2
    return {"x": cx, "y": top, "w": cw, "h": fh, "out_h": int(round(W * fh / cw / 2)) * 2}


def cap_pos(fg):
    """자막 덩어리의 가운데 높이: 가운데 영상 아래."""
    return min(FG_Y + fg["out_h"] + 230, 1480)


# ---------- 자막(ASS) ----------
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


def build_ass(name, item, seg, t0, dur, cap_y, fonts, credit):
    """쇼츠 자막(ASS). fonts는 (굵은 글꼴, 보통 글꼴, Bold 표시), credit은 아래쪽 문구({제목}, {이름})."""
    heavy, light, bold = fonts
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
    short_name = re.sub(r"^\d+\s*", "", name)
    credit = _ass_text(credit.replace("{제목}", short_name).replace("{이름}", name))
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
