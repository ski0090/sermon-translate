"""자막 읽기와 문장 정리 유스케이스: AI 도구로 자막 그림 묶음을 읽고, 자막을 문장으로 정리한다.
자막 그림을 20~30장씩 세로로 이어 붙인 한 장을 보내 번호별로 보이는 글자만 적게 한다. 읽은 묶음은 캐시해서
중단하거나 한도에 걸린 뒤 이어서 읽는다."""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..domain import sentences, tidy
from ..domain.errors import ToolError, UsageLimit

PER_STRIP = 25
TIDY_TIMEOUT = 600

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


class CaptionReader:
    def __init__(self, ai, strips, store):
        self.ai = ai          # ports.AiRunner
        self.strips = strips  # ports.StripImages
        self.store = store    # ports.StateStore: 읽은 묶음 캐시(<프로젝트>/strips/<해시>.json)

    def read_strip(self, pid, ws, crop_paths, tool="claude"):
        """자막 그림 묶음 하나를 읽어 글자 목록을 돌려준다. 개수가 맞지 않으면 반으로 나눠 다시 읽는다."""
        key = self.strips.fingerprint(crop_paths)
        cache = f"{pid}/strips/{key}.json"
        hit = self.store.read(cache)
        if hit is not None:
            return hit
        strips_dir = ws.ensure("strips")
        strip = self.strips.build(crop_paths, os.path.join(strips_dir, key + ".jpg"))
        n = len(crop_paths)
        texts = None
        for attempt in range(2):
            try:
                out = self.ai.run(READ_PROMPT.format(path=os.path.abspath(strip).replace("\\", "/"), n=n), tool,
                                  image=os.path.abspath(strip), cwd=strips_dir)
                texts = tidy.strip_texts(tidy.parse_json_array(out), n)
                if texts is not None:
                    break
            except (UsageLimit, ToolError):
                raise  # 빈칸으로 캐시하지 않는다
            except Exception:  # noqa
                if attempt == 1 and n <= 3:
                    texts = [""] * n
        if texts is None:
            if n <= 3:
                texts = [""] * n
            else:
                half = n // 2
                texts = self.read_strip(pid, ws, crop_paths[:half], tool) + \
                    self.read_strip(pid, ws, crop_paths[half:], tool)
        self.store.write(cache, texts)
        return texts

    def read_all(self, pid, ws, crop_paths, tool="claude", workers=4, per_strip=PER_STRIP, progress=None,
                 cancel=None):
        """모든 자막 그림을 읽는다. 결과는 crop_paths와 같은 길이의 글자 목록."""
        ws.ensure("strips")
        groups = [list(range(i, min(i + per_strip, len(crop_paths)))) for i in range(0, len(crop_paths), per_strip)]
        texts = [None] * len(crop_paths)
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {}
            for g in groups:
                if cancel and cancel():
                    break
                futs[ex.submit(self.read_strip, pid, ws, [crop_paths[i] for i in g], tool)] = g
            for fut in as_completed(futs):
                g = futs[fut]
                try:
                    res = fut.result()
                except (UsageLimit, ToolError):
                    for f in futs:
                        f.cancel()
                    raise  # 읽은 묶음은 캐시에 남아 있으니 한도가 풀리거나 도구를 고친 뒤 이어서 읽는다
                except Exception:  # noqa
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

    def _tidy_chunk(self, runs, tool, keep):
        """자막 묶음 하나를 AI로 정리한다. 번호는 묶음 안에서 1부터 새로 매긴다(자막 번호의 빈틈을 AI가 빠진 자막으로
        오해하지 않게). 번호가 빠지거나 순서가 틀리면 None."""
        keep = f"\n   다음 단어는 reading에서도 그대로 두세요(프로그램이 따로 바꿉니다): {', '.join(keep)}" if keep else ""
        prompt = TIDY_PROMPT.format(units=sentences.MAX_UNITS, keep=keep) + json.dumps(
            [{"c": k, "t": r["text"]} for k, r in enumerate(runs, 1)], ensure_ascii=False)
        for _ in range(2):
            try:
                arr = tidy.parse_json_array(self.ai.run(prompt, tool, timeout=TIDY_TIMEOUT))
                groups = tidy.groups_of(arr, len(runs))
            except (UsageLimit, ToolError):
                raise  # 규칙으로 합치지 않고 멈춘다
            except Exception:  # noqa
                continue
            if groups:
                return groups, arr
        return None

    def tidy_all(self, captions, tool="claude", workers=4, keep=(), progress=None, cancel=None):
        """자막(dict: id, text)을 AI로 문장 단위로 묶고 글자를 고치고 읽는 글과 확인 필요를 붙인다.
        AI 결과의 형식이 틀린 묶음은 규칙으로 합치고 확인 필요로 표시한다. 시간은 자막 번호로만 정해지므로 AI가 틀려도
        싱크는 깨지지 않는다. 반환: [{"caps", "raw", "text", "ai", "reading_ai", "check", "note"}], 중단하면 None"""
        chunks = tidy.chunks(sentences.collapse(captions))
        results = [None] * len(chunks)
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(self._tidy_chunk, ch, tool, list(keep)): k for k, ch in enumerate(chunks)}
            for fut in as_completed(futs):
                try:
                    results[futs[fut]] = fut.result()
                except UsageLimit:
                    for f in futs:
                        f.cancel()
                    raise
                done += 1
                if progress:
                    progress(done, len(chunks))
                if cancel and cancel():
                    for f in futs:
                        f.cancel()
                    return None
        out = []
        for ch, res in zip(chunks, results):
            out += tidy.tidy_groups(ch, *res) if res else tidy.failed_chunk(ch)
        return out
