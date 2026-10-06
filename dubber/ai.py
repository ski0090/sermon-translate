"""AI 명령줄 도구(claude, codex)로 자막 그림을 읽고 글을 교정한다.
자막 그림을 20~30장씩 세로로 이어 붙인 한 장을 보내 번호별로 보이는 글자만 적게 한다."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageDraw, ImageFont

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

CORRECT_PROMPT = (
    "아래는 설교 영상의 한국어 자막을 그림에서 읽어 문장 단위로 합친 목록입니다. 그림을 읽는 과정에서 생긴 "
    "글자 오류만 고치세요. 허용되는 수정: 잘못 읽힌 글자, 빠지거나 겹친 글자, 띄어쓰기, 문장 부호 보완. "
    "금지: 말을 바꾸거나 다듬기, 단어 추가나 삭제, 문장 합치기나 나누기, 어미 바꾸기. "
    "확신이 없으면 그대로 두세요.\n"
    "입력과 같은 개수, 같은 순서로 JSON 배열만 출력하세요. 형식: [{\"i\":0,\"text\":\"...\"}, ...]\n\n"
)


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


def _correct_group(texts, g, tool):
    payload = json.dumps([{"i": j, "text": texts[i]} for j, i in enumerate(g)], ensure_ascii=False)
    fixed = {}
    try:
        res = _parse_json_array(run_tool(CORRECT_PROMPT + payload, tool))
        if len(res) == len(g):
            for a in res:
                j = int(a.get("i", -1))
                if 0 <= j < len(g) and isinstance(a.get("text"), str) and a["text"].strip():
                    fixed[g[j]] = a["text"].strip()
    except Exception:
        pass
    return fixed


def correct_texts(texts, tool="claude", chunk=60, workers=4, progress=None, cancel=None):
    """문장 목록을 1:1로 교정한다. 묶음을 동시에 보내고, 실패한 묶음은 원문을 그대로 돌려준다."""
    out = list(texts)
    groups = [list(range(i, min(i + chunk, len(texts)))) for i in range(0, len(texts), chunk)]
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_correct_group, texts, g, tool) for g in groups]
        for fut in as_completed(futs):
            for i, t in fut.result().items():
                out[i] = t
            done += 1
            if progress:
                progress(done, len(groups))
            if cancel and cancel():
                for f in futs:
                    f.cancel()
                break
    return out


def diff_marks(a, b):
    """두 문장의 다른 부분을 <b>..</b>로 표시한 b를 돌려준다(검수 화면 표시용)."""
    import difflib
    sm = difflib.SequenceMatcher(None, a, b)
    parts = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        seg = b[j1:j2]
        parts.append(seg if op == "equal" else f"<mark>{seg or '␣'}</mark>")
    return "".join(parts)


if __name__ == "__main__":
    import sys
    crops = sys.argv[2:]
    print(read_strip(crops, sys.argv[1]))
