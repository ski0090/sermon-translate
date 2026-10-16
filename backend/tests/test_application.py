"""유스케이스 시험: 포트를 가짜로 끼워 바깥(AI 도구, 파일) 없이 돌린다."""
import json
import unittest

from dubber.application.reading import CaptionReader


class FakeAi:
    def __init__(self, replies):
        self.replies = iter(replies)

    def run(self, prompt, tool="claude", image=None, cwd=None, timeout=300):
        return next(self.replies)


class TidyTest(unittest.TestCase):
    CAPS = [{"id": i, "text": t} for i, t in enumerate(["은혜가 크고", "율법을 알지", "율법을 알지", "거룩합니다",
                                                         "12명이", "모였습니다"])]

    def test_ai_result_is_checked(self):
        """AI가 많이 고친 문장은 원문을 쓰고 확인 필요로, 읽는 글과 확인 이유는 그대로 받는다."""
        reply = json.dumps([{"c": [1, 2], "text": "은혜가 크고 율법을 알지."},
                            {"c": [3], "text": "전혀 다른 말로 바꿨습니다"},
                            {"c": [4, 5], "text": "12명이 모였습니다.", "reading": "열두 명이 모였습니다.",
                             "check": "뜻이 이상함"}], ensure_ascii=False)
        out = CaptionReader(FakeAi([reply]), None, None).tidy_all(self.CAPS, workers=1)
        self.assertEqual([s["caps"] for s in out], [[0, 1, 2], [3], [4, 5]])
        self.assertEqual((out[0]["text"], out[0]["raw"], out[0]["check"]),
                         ("은혜가 크고 율법을 알지.", "은혜가 크고 율법을 알지", False))
        self.assertTrue(out[1]["text"] == "거룩합니다" and out[1]["check"])
        self.assertEqual((out[2]["reading_ai"], out[2]["note"]), ("열두 명이 모였습니다.", "뜻이 이상함"))

    def test_bad_answer_falls_back_to_rule(self):
        """번호가 빠진 답이 두 번 오면 규칙으로 합치고 확인 필요로 표시한다."""
        out = CaptionReader(FakeAi(['[{"c":[1],"text":"x"}]'] * 2), None, None).tidy_all(self.CAPS, workers=1)
        self.assertEqual([s["caps"] for s in out], [[0, 1, 2, 3], [4, 5]])
        self.assertTrue(all(s["check"] for s in out))


if __name__ == "__main__":
    unittest.main()
