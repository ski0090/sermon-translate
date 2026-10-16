"""문장 정리 규칙: 자막 한 장(화면 표시 단위)을 문장으로 합치고, 음성으로 읽을 글(읽는 글)을 만든다."""
import difflib
import re

MAX_UNITS = 3        # 한 문장에 합치는 자막 최대 장수
MAX_CHARS = 60       # 한 문장 최대 글자 수(넘으면 더 합치지 않음)

_BRACKETS = re.compile(r"\([^)]*\)|\[[^\]]*\]|（[^）]*）|【[^】]*】")
_END_PUNCT = re.compile(r"""[.?!…]+["'”’』」)]*$""")
_END_FORM = re.compile(
    r"(습니다|입니다|니다|습니까|입니까|니까|십시오|시오|세요|셔요|죠|지요|네요|군요|구나|거든요|잖아요|"
    r"어요|아요|여요|에요|예요|해요|나요|가요|래요|데요|까요|라|다|냐|니|자|요)"
    r"""["'”’』」]*$""")

BOOKS = {
    "창": "창세기", "출": "출애굽기", "레": "레위기", "민": "민수기", "신": "신명기", "수": "여호수아", "삿": "사사기",
    "룻": "룻기", "삼상": "사무엘상", "삼하": "사무엘하", "왕상": "열왕기상", "왕하": "열왕기하", "대상": "역대상",
    "대하": "역대하", "스": "에스라", "느": "느헤미야", "에": "에스더", "욥": "욥기", "시": "시편", "잠": "잠언",
    "전": "전도서", "아": "아가", "사": "이사야", "렘": "예레미야", "애": "예레미야애가", "겔": "에스겔", "단": "다니엘",
    "호": "호세아", "욜": "요엘", "암": "아모스", "옵": "오바댜", "욘": "요나", "미": "미가", "나": "나훔", "합": "하박국",
    "습": "스바냐", "학": "학개", "슥": "스가랴", "말": "말라기",
    "마": "마태복음", "막": "마가복음", "눅": "누가복음", "요": "요한복음", "행": "사도행전", "롬": "로마서",
    "고전": "고린도전서", "고후": "고린도후서", "갈": "갈라디아서", "엡": "에베소서", "빌": "빌립보서", "골": "골로새서",
    "살전": "데살로니가전서", "살후": "데살로니가후서", "딤전": "디모데전서", "딤후": "디모데후서", "딛": "디도서",
    "몬": "빌레몬서", "히": "히브리서", "약": "야고보서", "벧전": "베드로전서", "벧후": "베드로후서", "요일": "요한일서",
    "요이": "요한이서", "요삼": "요한삼서", "유": "유다서", "계": "요한계시록",
}
_FULL = sorted(set(BOOKS.values()), key=len, reverse=True)
_ABBR = sorted(BOOKS.keys(), key=len, reverse=True)
_VERSE = re.compile(
    r"(?<![가-힣])(" + "|".join(_FULL + _ABBR) + r")\s*(\d+)\s*[:：]\s*(\d+)(?:\s*[-~–]\s*(\d+))?(?:\s*절)?")
_CHAPTER_VERSE = re.compile(r"(\d+)\s*[:：]\s*(\d+)(?:\s*[-~–]\s*(\d+))?")


def clean(text):
    """괄호 표기 제거, 공백 정리. (박수) [웃음] 같은 짧은 표기는 지우고, 괄호 안이 긴 글(성경 인용 등)은
    괄호만 빼고 남긴다(통째로 지우면 그 문장의 음성이 비어 더빙에서 빠진다)."""
    def repl(m):
        inner = m.group(0)[1:-1]
        return f" {inner} " if len(re.sub(r"\s", "", inner)) > 8 else " "
    t = _BRACKETS.sub(repl, text or "")
    return re.sub(r"\s+", " ", t).strip()


def is_end(text):
    t = text.rstrip()
    return bool(_END_PUNCT.search(t) or _END_FORM.search(t))


SAME_RATIO = 0.9     # 이어 붙은 두 자막의 글이 이만큼 같으면 같은 자막이 나뉘어 조금 다르게 읽힌 것으로 본다
TOUCH = 0.3          # 앞 자막 끝과 다음 자막 시작이 이 시간(초) 안이면 이어 붙은 것
_NOISE = re.compile(r"[\s.,?!…\"'“”‘’–\-]")


def _same(a, b):
    """띄어쓰기·문장 부호만 다르거나("아래있으면"/"아래 있으면") 글자가 거의 같으면("친구나"/"친규나") 같은 글."""
    a, b = _NOISE.sub("", a), _NOISE.sub("", b)
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= SAME_RATIO


def collapse(captions):
    """같은 글이 이어진 자막(장면만 바뀌어 여러 장으로 잡힌 것)을 하나로 묶는다. 글이 없는 자막은 뺀다.
    같은 자막이 나뉘어 AI가 조금 다르게 읽은 경우도, 두 자막이 시간상 바로 이어 붙어 있으면 하나로 본다.
    반환: [{"ids": [id..], "text"}]"""
    # ponytail: 설교자가 같은 말을 연달아 두 번 한 자막("아멘" "아멘")도 한 번만 읽힌다. 문제가 되면 사이 간격으로 가른다.
    out = []
    last_end = None
    for c in captions:
        t = clean(c.get("text", ""))
        if not t:
            continue
        touching = last_end is not None and c.get("start") is not None and c["start"] - last_end <= TOUCH
        if out and (out[-1]["text"] == t or (touching and _same(out[-1]["text"], t))):
            out[-1]["ids"].append(c["id"])
        else:
            out.append({"ids": [c["id"]], "text": t})
        last_end = c.get("end")
    return out


def merge(captions):
    """자막 목록(dict: id, start, end, text)을 문장 목록으로 합친다.
    반환: [{"caps": [id..], "start", "end", "raw"}]"""
    by_id = {c["id"]: c for c in captions}
    out = []
    cur = None
    for r in collapse(captions):
        if cur is None:
            cur = {"caps": [], "raw": "", "n": 0}
        cur["caps"] += r["ids"]
        cur["raw"] = (cur["raw"] + " " + r["text"]).strip()
        cur["n"] += 1
        if is_end(r["text"]) or cur["n"] >= MAX_UNITS or len(cur["raw"]) >= MAX_CHARS:
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    for m in out:
        del m["n"]
        m["start"], m["end"] = by_id[m["caps"][0]]["start"], by_id[m["caps"][-1]]["end"]
    return out


def _verse_repl(m):
    book = BOOKS.get(m.group(1), m.group(1))
    s = f"{book} {m.group(2)}장 {m.group(3)}절"
    if m.group(4):
        s += f"에서 {m.group(4)}절"
    return s


def reading(text, dictionary=None):
    """자막에 보이는 글 -> 음성으로 읽는 글."""
    t = clean(text)
    t = _VERSE.sub(_verse_repl, t)
    t = _CHAPTER_VERSE.sub(lambda m: f"{m.group(1)}장 {m.group(2)}절" + (f"에서 {m.group(3)}절" if m.group(3) else ""), t)
    for k, v in sorted((dictionary or {}).items(), key=lambda kv: -len(kv[0])):
        if k:
            t = t.replace(k, v)
    t = re.sub(r"""["'“”‘’『』「」]""", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


if __name__ == "__main__":
    caps = [
        {"id": 0, "start": 0, "end": 2, "text": "제가 기도하고 있을 때"},
        {"id": 1, "start": 2, "end": 4, "text": "하나님은"},
        {"id": 2, "start": 4, "end": 6, "text": "\"목사님 그게 큰 문제인가요?\""},
        {"id": 3, "start": 6, "end": 8, "text": "생각해 보세요 고린도후서 3장을 봅시다"},
        {"id": 4, "start": 8, "end": 10, "text": "'나라들은 네 빛으로 나아오리라' (박수)"},
        {"id": 5, "start": 10, "end": 12, "text": "요 3:16과 사 60:1-3을 보면"},
        {"id": 6, "start": 12, "end": 14, "text": "이사야 60:5 말씀입니다"},
    ]
    s = merge(caps)
    assert [x["caps"] for x in s] == [[0, 1, 2], [3], [4], [5, 6]], [x["caps"] for x in s]
    assert s[0]["start"] == 0 and s[0]["end"] == 6
    assert reading(caps[5]["text"]) == "요한복음 3장 16절과 이사야 60장 1절에서 3절을 보면", reading(caps[5]["text"])
    assert reading(caps[6]["text"]) == "이사야 60장 5절 말씀입니다"
    assert reading(caps[4]["text"]) == "나라들은 네 빛으로 나아오리라"
    dup = merge([{"id": 0, "start": 0, "end": 1, "text": "율법을 알아야"}, {"id": 1, "start": 1, "end": 2, "text": "율법을 알아야"},
                 {"id": 2, "start": 2, "end": 3, "text": ""}, {"id": 3, "start": 3, "end": 4, "text": "거룩함을 압니다"}])
    assert dup == [{"caps": [0, 1, 3], "raw": "율법을 알아야 거룩함을 압니다", "start": 0, "end": 4}], dup
    assert reading("할렐루야", {"할렐루야": "할렐루우야"}) == "할렐루우야"
    assert reading("[즉 남편을 주목하고, 높이 평가하라]'") == "즉 남편을 주목하고, 높이 평가하라"  # 긴 인용은 읽는다
    assert reading("아멘 [웃음] 그렇죠 (청중 박수)") == "아멘 그렇죠"
    assert is_end("복종했다고 합니다") and is_end("어렵죠") and not is_end("특히 배우자에게는")
    print("ok")
