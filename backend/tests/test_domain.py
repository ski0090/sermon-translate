"""도메인 규칙 시험(바깥 없이 돈다): python -m unittest discover -s backend/tests -t backend"""
import unittest

from dubber.domain import placement, schedule, sentences
from dubber.domain import shorts as sh
from dubber.domain.project import Project


class SentencesTest(unittest.TestCase):
    def test_merge_and_reading(self):
        caps = [
            {"id": 0, "start": 0, "end": 2, "text": "제가 기도하고 있을 때"},
            {"id": 1, "start": 2, "end": 4, "text": "하나님은"},
            {"id": 2, "start": 4, "end": 6, "text": "\"목사님 그게 큰 문제인가요?\""},
            {"id": 3, "start": 6, "end": 8, "text": "생각해 보세요 고린도후서 3장을 봅시다"},
            {"id": 4, "start": 8, "end": 10, "text": "'나라들은 네 빛으로 나아오리라' (박수)"},
            {"id": 5, "start": 10, "end": 12, "text": "요 3:16과 사 60:1-3을 보면"},
            {"id": 6, "start": 12, "end": 14, "text": "이사야 60:5 말씀입니다"},
        ]
        s = sentences.merge(caps)
        self.assertEqual([x["caps"] for x in s], [[0, 1, 2], [3], [4], [5, 6]])
        self.assertEqual((s[0]["start"], s[0]["end"]), (0, 6))
        self.assertEqual(sentences.reading(caps[5]["text"]), "요한복음 3장 16절과 이사야 60장 1절에서 3절을 보면")
        self.assertEqual(sentences.reading(caps[6]["text"]), "이사야 60장 5절 말씀입니다")
        self.assertEqual(sentences.reading(caps[4]["text"]), "나라들은 네 빛으로 나아오리라")

    def test_duplicates_and_dictionary(self):
        dup = sentences.merge([{"id": 0, "start": 0, "end": 1, "text": "율법을 알아야"},
                               {"id": 1, "start": 1, "end": 2, "text": "율법을 알아야"},
                               {"id": 2, "start": 2, "end": 3, "text": ""},
                               {"id": 3, "start": 3, "end": 4, "text": "거룩함을 압니다"}])
        self.assertEqual(dup, [{"caps": [0, 1, 3], "raw": "율법을 알아야 거룩함을 압니다", "start": 0, "end": 4}])
        self.assertEqual(sentences.reading("할렐루야", {"할렐루야": "할렐루우야"}), "할렐루우야")
        self.assertEqual(sentences.reading("[즉 남편을 주목하고, 높이 평가하라]'"), "즉 남편을 주목하고, 높이 평가하라")
        self.assertEqual(sentences.reading("아멘 [웃음] 그렇죠 (청중 박수)"), "아멘 그렇죠")
        self.assertTrue(sentences.is_end("복종했다고 합니다") and sentences.is_end("어렵죠"))
        self.assertFalse(sentences.is_end("특히 배우자에게는"))


def fake_project(sents, cuts=(), duration=100.0):
    return Project("p", {"name": "p", "info": {"duration": duration}, "cuts": list(cuts), "sentences": sents,
                         "captions": []})


class PlacementTest(unittest.TestCase):
    def test_plan(self):
        """밀림과 초기화: 5초를 2초 창에 넣으면 1.2배로 줄여도 넘치고, 잘라내기 뒤 새 구간에서 밀림이 사라진다."""
        p = fake_project([
            {"id": 1, "start": 0.0, "end": 2.0, "tts": "a", "tts_dur": 5.0, "pause": 0},
            {"id": 2, "start": 2.0, "end": 4.0, "tts": "b", "tts_dur": 1.0, "pause": 0},
            {"id": 3, "start": 48.0, "end": 50.0, "tts": "c", "tts_dur": 1.0, "pause": 0},
            {"id": 4, "start": 60.0, "end": 62.0, "tts": "d", "tts_dur": 1.0, "pause": 0},
        ], cuts=[{"start": 50.0, "end": 60.0}])
        pl = placement.plan(p)
        self.assertTrue(pl[0]["tempo"] == 1.2 and pl[0]["overflow"])
        self.assertAlmostEqual(pl[1]["start"], 5.0 / 1.2, places=2)
        self.assertTrue(pl[2]["start"] == 48.0 and not pl[2]["overflow"])
        self.assertTrue(pl[3]["start"] == 50.0 and pl[3]["tempo"] == 1.0)
        self.assertEqual(placement.fmt_srt(3661.5), "01:01:01,500")

    def test_subtitles_and_natural(self):
        p = fake_project([{"id": 1, "start": 0.0, "end": 2.0, "tts": "a", "tts_dur": 1.0, "text": "하나"},
                          {"id": 2, "start": 10.0, "end": 12.0, "tts": "b", "tts_dur": 1.0, "text": "둘", "pause": 0.2}])
        srt, txt = placement.subtitles(p, placement.plan(p))
        self.assertTrue(srt.startswith("1\n00:00:00,000 --> 00:00:01,000\n하나\n\n2\n"))
        self.assertEqual(txt, "하나\n둘\n")
        self.assertEqual([round(g, 2) for _, g in placement.natural_sequence(p)], [0.0, 1.7])


class ProjectTest(unittest.TestCase):
    def test_cuts_and_edits(self):
        caps = [{"id": i, "start": i * 2.0, "end": i * 2.0 + 2, "text": t, "yellow": 0.0}
                for i, t in enumerate(["첫째 문장입니다.", "둘째", "문장입니다.", "셋째 문장입니다."])]
        p = Project("p", {"name": "p", "info": {"duration": 8.0}, "cuts": [], "captions": caps, "sentences": [],
                         "next_id": 1})
        self.assertEqual(p.build_sentences(), 3)
        new = p.split_sentence(p.data["sentences"][1]["id"], 2)
        self.assertEqual(new["caps"], [2])
        p.merge_next(p.data["sentences"][1]["id"])
        self.assertEqual(p.data["sentences"][1]["caps"], [1, 2])
        p.set_cuts([{"start": 6.0, "end": 8.0}])
        self.assertEqual([s["caps"] for s in p.data["sentences"]], [[0], [1, 2]])
        self.assertEqual(p.out_time(8.0), 6.0)
        p.update_sentence(p.data["sentences"][0]["id"], text="고친 글", tts="무시")
        self.assertEqual(p.data["sentences"][0]["text"], "고친 글")
        p.apply_settings({"voice": "M1", "unknown": 1})
        self.assertEqual(p.settings["voice"], "M1")
        self.assertNotIn("unknown", p.settings)


class ShortsTest(unittest.TestCase):
    TL = [{"id": 1, "text": "가", "t": 0.0, "d": 10.0}, {"id": 2, "text": "나 다", "t": 10.0, "d": 20.0},
          {"id": 3, "text": "라", "t": 31.0, "d": 5.0}, {"id": 4, "text": "마", "t": 40.0, "d": 25.0},
          {"id": 5, "text": "바 사", "t": 65.2, "d": 30.0}]

    def test_segments(self):
        p = fake_project([], cuts=[{"start": 50.0, "end": 60.0}])
        self.assertEqual([sh.orig_time(p, t) for t in (45, 55, 50)], [45, 65, 60])
        seg, nxt = sh.segment(self.TL, {"start": 1, "end": 2})
        self.assertEqual(([s["id"] for s in seg], nxt["id"]), ([1, 2], 3))
        self.assertEqual(sh.span(seg, nxt), (0.0, 30.6))
        self.assertEqual(sh.span(*sh.segment(self.TL, {"start": 4, "end": 4})), (39.7, 65.15))  # 다음 문장 바로 앞에서

    def test_candidates(self):
        taken = []
        c = sh.candidate(self.TL, {"start": 1, "end": 2, "title": ["하나", "둘"],
                                   "emph": {"2": ["나 다", "없는 말", "다"]}}, taken)
        self.assertEqual((c["emph"], c["title"], taken), ({"2": ["나 다"]}, ["하나", "둘"], [(1, 2)]))
        self.assertIsNone(sh.candidate(self.TL, {"start": 2, "end": 2}, taken))  # 겹침
        self.assertIsNone(sh.candidate(self.TL, {"start": 5, "end": 4}, taken))  # 순서
        self.assertEqual(sh.candidate(self.TL, {"start": 4, "end": 5, "title": "한 줄"}, taken)["title"], ["한 줄", ""])

    def test_caption_chunks(self):
        self.assertEqual(sh.mark("우리 죄는 하나님이 아시는", ["하나님이 아시"]),
                         [("우리", False), ("죄는", False), ("하나님이", True), ("아시는", True)])
        words = sh.mark("먼저 알려드릴 것은, 우리의 죄 사함이 우리가 아는 죄를 기준으로 사하는 게 아니라 하나님이 아시는 죄를 "
                        "기준으로 사함 받습니다.", [])
        g = sh.chunks(words)
        lines = [" ".join(w for w, _ in line) for grp in g for line in grp]
        self.assertEqual(" ".join(lines), " ".join(w for w, _ in words))
        self.assertTrue(all(sh.vw(x) <= sh.CAP_WIDTH for x in lines))
        self.assertTrue(all(len(grp) <= 2 for grp in g) and len(lines) <= 8)

    def test_manual_and_edit(self):
        it = sh.manual_item(self.TL, 12)
        self.assertEqual((it["start"], it["end"]), (2, 4))
        p = fake_project([{"id": s["id"], "text": s["text"], "start": s["t"], "end": s["t"] + s["d"]} for s in self.TL])
        sh.edit_item(p, it, {"end": 3, "title": ["가", "나", "다"], "xpos": 2}, sh.timeline(p))
        self.assertEqual((it["end"], it["title"], it["xpos"]), (3, ["가", "나"], 1.0))
        with self.assertRaises(ValueError):
            sh.edit_item(p, it, {"start": 5}, sh.timeline(p))


class ScheduleTest(unittest.TestCase):
    def test_day_tool_and_apply(self):
        s = schedule.empty()
        today = schedule.day()
        schedule.apply(s, {"days": {today: {"five_hour": 120, "seven_day": 30, "tool": "codex"}}}, ["claude", "codex"])
        self.assertEqual(schedule.usage_limits(s), {"five_hour": 100, "seven_day": 30})
        self.assertEqual(schedule.day_tool(s, ["claude", "codex"]), "codex")
        self.assertEqual(schedule.day_tool(s, ["claude"]), "claude")  # 꺼 둔 도구는 켜진 도구로 대신
        self.assertIsNone(schedule.day_tool(s, []))
        self.assertIsNone(schedule.usage_pause(s, ["claude", "codex"], {}))  # Codex 날은 Claude 한도를 보지 않는다
        with self.assertRaises(ValueError):
            schedule.apply(s, {"days": {"2026/10/10": None}}, ["claude"])

    def test_pause_when_over_limit(self):
        s = schedule.empty()
        now = 1_000_000.0
        info = {"unifiedWindows": {"five_hour": {"utilization": 0.6, "resetsAt": now + 3600}}}
        until, why = schedule.usage_pause(s, ["claude"], info, now)
        self.assertIn("5시간", why)
        self.assertLessEqual(until, now + 3600 + 120)


if __name__ == "__main__":
    unittest.main()
