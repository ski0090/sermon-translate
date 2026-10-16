"""AI 답 다루기: JSON 배열 꺼내기, 자막 읽기 답 검사, 문장 정리 묶음 나누기와 결과 검증(틀리면 규칙으로 합침)."""
import difflib
import json

from . import sentences

TIDY_CHUNK = 60


def parse_json_array(text):
    s, e = text.find("["), text.rfind("]")
    if s < 0 or e < 0:
        raise ValueError("JSON 배열이 없습니다: " + text[:200])
    return json.loads(text[s:e + 1])


def strip_texts(arr, n):
    """자막 그림 묶음 읽기 답(번호별 글자)을 번호 순 글자 목록으로. 개수가 틀리면 None."""
    if len(arr) != n:
        return None
    return [str(a.get("text", "")).strip() for a in sorted(arr, key=lambda a: int(a.get("n", 0)))]


def chunks(runs, size=TIDY_CHUNK):
    """size개쯤에서 문장이 끝나는 자리로 자른다(문장 하나가 두 묶음에 걸치지 않게). 끝을 못 찾으면 1.5배에서 자른다."""
    out, cur = [], []
    for r in runs:
        cur.append(r)
        if len(cur) >= size * 1.5 or (len(cur) >= size and sentences.is_end(r["text"])):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def groups_of(arr, n):
    """정리 답의 자막 번호 묶음. 번호가 빠지거나 순서가 틀리면 None."""
    groups = [[int(c) for c in a["c"]] for a in arr]
    if all(groups) and [c for g in groups for c in g] == list(range(1, n + 1)):
        return groups
    return None


def by_rule(runs):
    return [{"caps": m["caps"], "raw": m["raw"]} for m in sentences.merge(
        [{"id": i, "start": 0, "end": 0, "text": r["text"]} for r in runs for i in r["ids"]])]


def tidy_groups(runs, groups, arr):
    """AI 결과를 문장으로 바꾼다. 자막 수가 넘치거나 원문과 너무 다른 문장은 원문을 쓰고 확인 필요로 표시한다."""
    out = []
    for g, a in zip(groups, arr):
        rs = [runs[c - 1] for c in g]
        if len(rs) > sentences.MAX_UNITS:
            out += by_rule(rs)
            continue
        raw = " ".join(r["text"] for r in rs)
        text = sentences.clean(str(a.get("text") or "")) or raw
        reading = sentences.clean(str(a.get("reading") or ""))
        check = str(a.get("check") or "").strip()
        if difflib.SequenceMatcher(None, raw, text).ratio() < 0.8:
            check = f"AI가 많이 고쳐서 적용하지 않음: {text}"
            text, reading = raw, ""
        out.append({"caps": [i for r in rs for i in r["ids"]], "raw": raw, "ai": text, "text": text,
                    "reading_ai": reading if reading and reading != text else None, "check": bool(check),
                    "note": check or None})
    return out


def failed_chunk(runs):
    """AI 정리에 실패한 묶음은 규칙으로 합치고 확인 필요로 표시한다."""
    return [dict(m, check=True, note="AI 정리에 실패해 규칙으로 합침") for m in by_rule(runs)]
