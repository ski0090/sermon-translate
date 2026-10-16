"""유튜브에 올릴 영상의 제목·설명·태그 규칙과, 채널에 이미 있는 영상을 이름으로 찾는 규칙."""
import re

PRIVACY = "private"
SHORT_KEY = "short:"  # 유튜브 대기열에서 쇼츠를 가리키는 이름: "short:<프로젝트>:<번호>"
SLEEP_KEY = "sleep:"  # 음성 영상: "sleep:<프로젝트>"
# 영상 설명과 해시태그 기본값. 시작 화면의 "설명·해시태그"에서 바꾼다. {이름}은 영상 이름으로 바뀐다
DEFAULTS = {"description": "조셉 프린스 목사님 설교 \"{이름}\"의 한국어 더빙입니다.",
            "hashtags": "#조셉프린스 #JosephPrince #한국어더빙 #설교 #은혜",
            # 쇼츠: {제목}은 쇼츠 제목 두 줄, {링크}는 유튜브에 올린 전체 영상(없으면 그 줄을 뺀다)
            "shorts_title": "{제목} | 조셉 프린스 설교 (한국어 더빙)",
            "shorts_description": "조셉 프린스 목사님 설교 \"{이름}\" 중에서 (한국어 더빙)\n전체 영상: {링크}",
            # 음성 영상(자면서 듣는 설교)
            "sleep_title": "{이름} (자면서 듣는 설교)",
            "sleep_description": "조셉 프린스 목사님 설교 \"{이름}\"을 한국어 음성으로 편하게 들을 수 있게 만들었습니다. 잠들기 전이나 쉬면서 들어 보세요.\n화면과 함께 보기: {링크}"}
PREVIEW_NAME = "218 선생이 아닌 구세주 예수"  # 설정 화면의 미리 보기에 쓰는 영상 이름


def short_key(pid, sid):
    return f"{SHORT_KEY}{pid}:{sid}"


def settings(saved):
    return {k: saved.get(k, v) for k, v in DEFAULTS.items()}


def video_url(vid):
    return f"https://www.youtube.com/watch?v={vid}"


def short_url(vid):
    return f"https://www.youtube.com/shorts/{vid}"


def meta(s, stem, desc=None, extra_tags=()):
    """올릴 영상의 설명과 태그. 해시태그는 설명 끝에 붙이고(앞의 3개가 제목 위에 보인다) 태그로도 넣는다."""
    tags = list(extra_tags) + [t.lstrip("#") for t in re.split(r"[\s,]+", s["hashtags"]) if t.strip("#")]
    desc = (s["description"] if desc is None else desc).replace("{이름}", stem).strip()
    if tags:
        desc += "\n\n" + " ".join("#" + t for t in tags)
    # 유튜브 제한: 설명 5,000바이트, 꺾쇠 괄호 금지, 태그 합계 500자
    desc = desc.replace("<", "(").replace(">", ")").encode("utf-8")[:5000].decode("utf-8", "ignore")
    out, n = [], 0
    for t in tags:
        n += len(t) + 1
        if n > 500:
            break
        out.append(t)
    return desc, out


def _with_link(template, full):
    """{링크} 줄은 링크가 있을 때만 남긴다."""
    return "\n".join(ln.replace("{링크}", full or "") for ln in template.split("\n") if full or "{링크}" not in ln)


def short_meta(s, stem, item, full):
    """쇼츠의 유튜브 제목, 설명, 태그. full은 전체 영상 주소(없으면 None)."""
    head = " ".join(x for x in item.get("title") or [] if x).strip() or stem
    title = s["shorts_title"].replace("{제목}", head).replace("{이름}", stem)
    title = title.replace("<", "(").replace(">", ")").strip()[:100]
    desc, tags = meta(s, stem, _with_link(s["shorts_description"], full), extra_tags=["Shorts"])
    return title, desc, tags


def sleep_meta(s, stem, full):
    """음성 영상의 유튜브 제목, 설명, 태그."""
    title = s["sleep_title"].replace("{이름}", stem).replace("<", "(").replace(">", ")").strip()[:100]
    desc, tags = meta(s, stem, _with_link(s["sleep_description"], full), extra_tags=["자면서듣는설교", "수면설교"])
    return title, desc, tags


def norm_title(title):
    """제목 비교용: "한국어 더빙", 괄호, 띄어쓰기, 문장 부호를 뺀다."""
    t = re.sub(r"한국어\s*더빙", "", title)
    return re.sub(r"[\s()\[\]{}<>.,_\-–:;'\"“”‘’!?]", "", t)


def existing(stem, videos):
    """채널에 이미 있는 같은 이름의 영상(직접 올린 것 포함)."""
    key = norm_title(stem)
    v = next((v for v in videos if norm_title(v["title"]) == key), None)
    return v and dict(v, url=video_url(v["id"]))
