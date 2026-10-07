"""AI 명령줄 도구(claude, codex)로 자막 그림을 읽고 문장을 정리한다.
자막 그림을 20~30장씩 세로로 이어 붙인 한 장을 보내 번호별로 보이는 글자만 적게 한다."""
import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageDraw, ImageFont

import sentences

PER_STRIP = 25
GUTTER = 72
DIVIDER = 4
FONT = "C:/Windows/Fonts/arial.ttf"
TIMEOUT = 300

READ_PROMPT = (
    "{path} 파일을 Read 도구로 열어 보세요. 한국어 자막 {n}장을 세로로 이어 붙인 그림이고, "
    "왼쪽 흰 상자에 1부터 {n}까지 번호가 있으며 빨간 선이 자막 사이의 경계입니다.\n"
    "각 번호마다 그 칸에 보이는 자막 글자를 보이는 그대로 적으세요. 맞춤법이나 띄어쓰기를 고치지 말고, "
    "줄바꿈은 공백 하나로 바꾸세요. 칸 위쪽에 잘려 보이는 작은 글씨(성경 구절 상자)는 무시하세요. "
    "글자가 없으면 빈 문자열로 두세요.\n"
    "다른 말 없이 JSON 배열만 출력하세요. 형식: [{{\"n\":1,\"text\":\"...\"}}, ...] 항목은 정확히 {n}개여야 합니다."
)

TIDY_PROMPT = (
    "아래는 설교 영상의 한국어 자막을 그림에서 읽은 목록입니다. 항목 하나가 화면에 한 번 보인 자막이고 c는 자막 번호입니다.\n"
    "1. 이어지는 자막을 묶어 문장으로 만드세요. 한 문장은 자막 1~{units}개입니다. 모든 번호를 순서대로 한 번씩만 쓰세요.\n"
    "2. text: 묶은 자막을 공백으로 이은 글에서 그림을 읽다 생긴 오류만 고치세요. 허용: 잘못 읽힌 글자, 빠지거나 겹친 글자, "
    "띄어쓰기, 문장 부호. 금지: 말을 바꾸거나 다듬기, 단어 더하기나 빼기, 어미 바꾸기. 확신이 없으면 그대로 두세요.\n"
    "3. reading: 숫자, 영어, 성경 장절이 있는 문장만 음성으로 읽을 글을 적으세요. 숫자는 문맥에 맞는 한국어로(3명은 세 명), "
    "영어는 한국어 발음으로, 요 3:16은 요한복음 3장 16절로 적습니다. 해당 없으면 빼세요.{keep}\n"
    "4. check: 잘못 읽힌 것 같은데 고칠 수 없는 곳, 앞뒤 문맥으로 뜻이 통하지 않는 곳, 찬양 가사처럼 설교자가 한 말이 "
    "아닌 글이 있으면 이유를 짧게 적으세요. 설교자가 성경을 읽거나 인용하는 것은 설교자가 한 말이니 표시하지 마세요. "
    "없으면 빼세요.\n"
    "다른 말 없이 JSON 배열만 출력하세요. 형식: [{{\"c\":[1,2],\"text\":\"...\"}}, "
    "{{\"c\":[3],\"text\":\"...\",\"reading\":\"...\",\"check\":\"...\"}}]\n\n"
)
TIDY_CHUNK = 60
TIDY_TIMEOUT = 600


def _font(size=30):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def file_hash(paths):
    h = hashlib.sha1()
    for p in paths:
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:16]


def build_strip(crop_paths, out_path):
    ims = [Image.open(p).convert("RGB") for p in crop_paths]
    w = max(i.width for i in ims) + GUTTER
    h = sum(i.height for i in ims) + DIVIDER * (len(ims) + 1)
    strip = Image.new("RGB", (w, h), (255, 0, 0))
    draw = ImageDraw.Draw(strip)
    font = _font()
    y = DIVIDER
    for k, im in enumerate(ims, 1):
        draw.rectangle([0, y, GUTTER - 1, y + im.height - 1], fill=(255, 255, 255))
        draw.text((8, y + im.height // 2 - 17), str(k), fill=(0, 0, 0), font=font)
        strip.paste(im, (GUTTER, y))
        y += im.height + DIVIDER
    strip.save(out_path, quality=92)
    return out_path


def _parse_json_array(text):
    s, e = text.find("["), text.rfind("]")
    if s < 0 or e < 0:
        raise ValueError("JSON 배열이 없습니다: " + text[:200])
    return json.loads(text[s:e + 1])


def _run(cmd, prompt, cwd, env, timeout):
    """시간이 지나면 자식 프로세스 트리까지 끝낸다(shell을 거치면 손자 프로세스가 남아 기다리게 된다)."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env)
    try:
        out, err = p.communicate(prompt.encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        raise RuntimeError(f"{cmd[0]} 응답 시간 초과({timeout}초)")
    return p.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def run_tool(prompt, tool="claude", image=None, cwd=None, timeout=TIMEOUT):
    """AI 도구를 한 번 호출해 출력 문자열을 돌려준다. 프롬프트는 stdin으로 넘긴다(명령줄 길이 제한 회피)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE")}
    if tool == "codex":
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            last = f.name
        cmd = ["codex", "exec", "--skip-git-repo-check", "-o", last]
        if image:
            cmd += ["-i", image]
        cmd += ["-"]
        _run(cmd, prompt, cwd, env, timeout)
        with open(last, encoding="utf-8", errors="replace") as f:
            out = f.read()
        os.unlink(last)
        return out
    cmd = ["claude", "-p", "--output-format", "text", "--max-turns", "4", "--allowedTools", "Read" if image else ""]
    code, out, err = _run(cmd, prompt, cwd, env, timeout)
    if code != 0 and not out.strip():
        raise RuntimeError(f"{tool} 실패: {err.strip()[:300]}")
    return out


def read_strip(crop_paths, strips_dir, tool="claude"):
    """자막 그림 묶음 하나를 읽어 글자 목록을 돌려준다. 개수가 맞지 않으면 반으로 나눠 다시 읽는다."""
    key = file_hash(crop_paths)
    cache = os.path.join(strips_dir, key + ".json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    strip = build_strip(crop_paths, os.path.join(strips_dir, key + ".jpg"))
    n = len(crop_paths)
    texts = None
    for attempt in range(2):
        try:
            out = run_tool(READ_PROMPT.format(path=os.path.abspath(strip).replace("\\", "/"), n=n), tool,
                           image=os.path.abspath(strip), cwd=strips_dir)
            arr = _parse_json_array(out)
            if len(arr) == n:
                texts = [str(a.get("text", "")).strip() for a in sorted(arr, key=lambda a: int(a.get("n", 0)))]
                break
        except Exception:
            if attempt == 1 and n <= 3:
                texts = [""] * n
    if texts is None:
        if n <= 3:
            texts = [""] * n
        else:
            half = n // 2
            texts = read_strip(crop_paths[:half], strips_dir, tool) + read_strip(crop_paths[half:], strips_dir, tool)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(texts, f, ensure_ascii=False)
    return texts


def read_all(crop_paths, strips_dir, tool="claude", workers=4, per_strip=PER_STRIP, progress=None, cancel=None):
    """모든 자막 그림을 읽는다. 결과는 crop_paths와 같은 길이의 글자 목록."""
    os.makedirs(strips_dir, exist_ok=True)
    groups = [list(range(i, min(i + per_strip, len(crop_paths)))) for i in range(0, len(crop_paths), per_strip)]
    texts = [None] * len(crop_paths)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {}
        for g in groups:
            if cancel and cancel():
                break
            futs[ex.submit(read_strip, [crop_paths[i] for i in g], strips_dir, tool)] = g
        for fut in as_completed(futs):
            g = futs[fut]
            try:
                res = fut.result()
            except Exception:
                res = [""] * len(g)
            for i, t in zip(g, res):
                texts[i] = t
            done += 1
            if progress:
                progress(done, len(groups))
            if cancel and cancel():
                for f in futs:
                    f.cancel()
                break
    return [t if t is not None else "" for t in texts]


def _chunks(runs, size=TIDY_CHUNK):
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


def _tidy_chunk(runs, tool, keep):
    """자막 묶음 하나를 AI로 정리한다. 번호는 묶음 안에서 1부터 새로 매긴다(자막 번호의 빈틈을 AI가 빠진 자막으로
    오해하지 않게). 번호가 빠지거나 순서가 틀리면 None."""
    keep = f"\n   다음 단어는 reading에서도 그대로 두세요(프로그램이 따로 바꿉니다): {', '.join(keep)}" if keep else ""
    prompt = TIDY_PROMPT.format(units=sentences.MAX_UNITS, keep=keep) + json.dumps(
        [{"c": k, "t": r["text"]} for k, r in enumerate(runs, 1)], ensure_ascii=False)
    for _ in range(2):
        try:
            arr = _parse_json_array(run_tool(prompt, tool, timeout=TIDY_TIMEOUT))
            groups = [[int(c) for c in a["c"]] for a in arr]
        except Exception:
            continue
        if all(groups) and [c for g in groups for c in g] == list(range(1, len(runs) + 1)):
            return groups, arr
    return None


def _by_rule(runs):
    return [{"caps": m["caps"], "raw": m["raw"]} for m in sentences.merge(
        [{"id": i, "start": 0, "end": 0, "text": r["text"]} for r in runs for i in r["ids"]])]


def _tidy_groups(runs, groups, arr):
    """AI 결과를 문장으로 바꾼다. 자막 수가 넘치거나 원문과 너무 다른 문장은 원문을 쓰고 확인 필요로 표시한다."""
    out = []
    for g, a in zip(groups, arr):
        rs = [runs[c - 1] for c in g]
        if len(rs) > sentences.MAX_UNITS:
            out += _by_rule(rs)
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


def tidy_all(captions, tool="claude", workers=4, keep=(), progress=None, cancel=None):
    """자막(dict: id, text)을 AI로 문장 단위로 묶고 글자를 고치고 읽는 글과 확인 필요를 붙인다.
    AI 결과의 형식이 틀린 묶음은 규칙으로 합치고 확인 필요로 표시한다. 시간은 자막 번호로만 정해지므로 AI가 틀려도
    싱크는 깨지지 않는다. 반환: [{"caps", "raw", "text", "ai", "reading_ai", "check", "note"}], 중단하면 None"""
    chunks = _chunks(sentences.collapse(captions))
    results = [None] * len(chunks)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_tidy_chunk, ch, tool, list(keep)): k for k, ch in enumerate(chunks)}
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()
            done += 1
            if progress:
                progress(done, len(chunks))
            if cancel and cancel():
                for f in futs:
                    f.cancel()
                return None
    out = []
    for ch, res in zip(chunks, results):
        out += _tidy_groups(ch, *res) if res else [
            dict(m, check=True, note="AI 정리에 실패해 규칙으로 합침") for m in _by_rule(ch)]
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(read_strip(sys.argv[2:], sys.argv[1]))
        sys.exit()
    # AI 없이 정리 결과 검증과 대체 처리를 확인한다.
    caps = [{"id": i, "text": t} for i, t in enumerate(["은혜가 크고", "율법을 알지", "율법을 알지", "거룩합니다",
                                                         "12명이", "모였습니다"])]
    replies = iter([json.dumps([{"c": [1, 2], "text": "은혜가 크고 율법을 알지."},
                                {"c": [3], "text": "전혀 다른 말로 바꿨습니다"},
                                {"c": [4, 5], "text": "12명이 모였습니다.", "reading": "열두 명이 모였습니다.",
                                 "check": "뜻이 이상함"}], ensure_ascii=False)])
    run_tool = lambda *a, **k: next(replies)  # noqa
    out = tidy_all(caps, workers=1)
    assert [s["caps"] for s in out] == [[0, 1, 2], [3], [4, 5]], out
    assert out[0]["text"] == "은혜가 크고 율법을 알지." and out[0]["raw"] == "은혜가 크고 율법을 알지" and not out[0]["check"]
    assert out[1]["text"] == "거룩합니다" and out[1]["check"], out[1]
    assert out[2]["reading_ai"] == "열두 명이 모였습니다." and out[2]["note"] == "뜻이 이상함"
    replies = iter(['[{"c":[1],"text":"x"}]'] * 2)
    out = tidy_all(caps, workers=1)
    assert [s["caps"] for s in out] == [[0, 1, 2, 3], [4, 5]] and all(s["check"] for s in out), out
    print("ok")
