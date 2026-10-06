"""프로젝트(영상 한 편) 저장소와 단계별 처리. 서버와 명령줄 둘 다 이 모듈을 쓴다."""
import json
import os
import re
import tempfile
import time

import ai
import captions
import sentences

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects")
STEPS = ["load", "scan", "review", "tts", "export"]
DEFAULT_SETTINGS = {"voice": "F1", "speed": 1.05, "min_gap": 20, "tool": "claude", "orig_audio": "remove",
                    "per_strip": 25, "workers": 4, "dictionary": {}, "ai_correct": False, "tts_steps": 8,
                    "out_dir": None}


def _slug(name):
    s = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return s[:60] or "project"


def list_projects():
    out = []
    if not os.path.isdir(ROOT):
        return out
    for d in os.listdir(ROOT):
        p = os.path.join(ROOT, d, "project.json")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    j = json.load(f)
                caps = j.get("captions", [])
                sents = j.get("sentences", [])
                out.append({"dir": d, "name": j.get("name", d), "video": j.get("video"), "step": j.get("step"),
                            "updated": os.path.getmtime(p), "duration": j.get("info", {}).get("duration"),
                            "captions": len(caps), "read": sum(1 for c in caps if c.get("text")),
                            "sentences": len(sents), "tts": sum(1 for s in sents if s.get("tts")),
                            "cuts": len(j.get("cuts", [])), "exported": bool(j.get("last_export"))})
            except Exception:
                pass
    out.sort(key=lambda x: -x["updated"])
    return out


class Project:
    def __init__(self, dir_):
        self.dir = dir_
        self.path = os.path.join(dir_, "project.json")
        with open(self.path, encoding="utf-8") as f:
            self.data = json.load(f)
        self.mtime = os.path.getmtime(self.path)
        self.data.setdefault("settings", {})
        for k, v in DEFAULT_SETTINGS.items():
            self.data["settings"].setdefault(k, v)

    @staticmethod
    def create(video):
        name = os.path.splitext(os.path.basename(video))[0]
        d = os.path.join(ROOT, _slug(name))
        n = 2
        while os.path.exists(d):
            d = os.path.join(ROOT, f"{_slug(name)}_{n}")
            n += 1
        os.makedirs(d)
        info = captions.probe(video)
        data = {"name": name, "video": video, "info": info, "roi": None, "step": "load", "captions": [],
                "sentences": [], "cuts": [], "ranges": {"gaps": [], "lyrics": []}, "settings": dict(DEFAULT_SETTINGS),
                "next_id": 1, "created": time.time()}
        with open(os.path.join(d, "project.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return Project(d)

    def sub(self, *parts):
        p = os.path.join(self.dir, *parts)
        os.makedirs(p, exist_ok=True)
        return p

    def save(self):
        fd, tmp = tempfile.mkstemp(dir=self.dir, suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        self.mtime = os.path.getmtime(self.path)

    def set_step(self, step):
        if STEPS.index(step) > STEPS.index(self.data.get("step", "load")):
            self.data["step"] = step

    # ---------- 자막 읽기 ----------
    def detect_roi(self):
        self.data["roi"] = captions.detect_band(self.data["video"], self.data["info"])
        self.save()
        return self.data["roi"]

    def scan(self, progress=None, cancel=None):
        """자막이 바뀌는 순간을 찾아 그림과 시간을 기록한다(외부 전송 없음)."""
        if not self.data.get("roi"):
            self.detect_roi()
        crops = self.sub("crops")
        for f in os.listdir(crops):
            os.remove(os.path.join(crops, f))
        dur = self.data["info"]["duration"]
        segs = captions.scan(self.data["video"], self.data["roi"], crops,
                             progress=lambda t: progress and progress(t / dur), cancel=cancel)
        self.data["captions"] = [dict(id=i, text="", check=False, **s) for i, s in enumerate(segs)]
        self.update_ranges()
        self.data["sentences"] = []
        self.set_step("scan")
        self.save()
        return len(segs)

    def update_ranges(self):
        d = self.data
        d["ranges"] = {"gaps": captions.gaps(d["captions"], d["info"]["duration"], d["settings"]["min_gap"]),
                       "lyrics": captions.lyric_ranges(d["captions"])}

    def read(self, progress=None, cancel=None):
        """자막 그림을 AI에 읽힌다. 결과는 캐시되어 중단 후 이어서 할 수 있다."""
        caps = self.data["captions"]
        paths = [os.path.join(self.dir, "crops", c["crop"]) for c in caps]
        s = self.data["settings"]
        texts = ai.read_all(paths, self.sub("strips"), tool=s["tool"], workers=s["workers"],
                            per_strip=s["per_strip"], progress=progress, cancel=cancel)
        for c, t in zip(caps, texts):
            c["text"] = t
            c["check"] = (t == "")
        self.save()

    # ---------- 문장 정리 ----------
    def build_sentences(self):
        caps = [c for c in self.data["captions"] if not self._in_cut(c["start"], c["end"])]
        merged = sentences.merge(caps)
        out = []
        for m in merged:
            sid = self.data["next_id"]
            self.data["next_id"] += 1
            out.append({"id": sid, "caps": m["caps"], "start": m["start"], "end": m["end"], "raw": m["raw"],
                        "ai": None, "text": m["raw"], "reading": None, "speed": None, "pause": 0.0,
                        "tts": None, "tts_dur": None, "check": any(self.cap(i)["check"] for i in m["caps"])})
        self.data["sentences"] = out
        self.set_step("review")
        self.save()
        return len(out)

    def correct(self, progress=None, cancel=None):
        sents = [s for s in self.data["sentences"] if s["ai"] is None]
        texts = [s["text"] for s in sents]
        fixed = ai.correct_texts(texts, tool=self.data["settings"]["tool"], workers=self.data["settings"]["workers"],
                                 progress=progress, cancel=cancel)
        for s, t in zip(sents, fixed):
            s["ai"] = t
            if t != s["text"]:
                s["text"] = t
                s["tts"], s["tts_dur"] = None, None
        self.save()

    def cap(self, cid):
        return self.data["captions"][cid]

    def _in_cut(self, start, end):
        mid = (start + end) / 2
        return any(c["start"] <= mid <= c["end"] for c in self.data["cuts"])

    def reading_of(self, s):
        if s.get("reading"):
            return s["reading"]
        return sentences.reading(s["text"], self.data["settings"].get("dictionary"))

    # ---------- 문장 편집 ----------
    def find(self, sid):
        for i, s in enumerate(self.data["sentences"]):
            if s["id"] == sid:
                return i, s
        raise KeyError(sid)

    def _recalc(self, s):
        caps = [self.cap(i) for i in s["caps"]]
        s["start"], s["end"] = caps[0]["start"], caps[-1]["end"]
        s["tts"] = None
        s["tts_dur"] = None

    def update_sentence(self, sid, **fields):
        _, s = self.find(sid)
        for k, v in fields.items():
            if k in ("text", "reading", "speed", "pause", "check"):
                if k in ("text", "reading", "speed") and s.get(k) != v:
                    s["tts"] = None
                    s["tts_dur"] = None
                s[k] = v
        self.save()
        return s

    def split_sentence(self, sid, at_cap):
        """at_cap(자막 id)부터 뒤를 새 문장으로 나눈다. 자막이 하나뿐이면 글만 둘로 나눌 수 없으므로 그대로 둔다."""
        i, s = self.find(sid)
        if at_cap not in s["caps"] or at_cap == s["caps"][0]:
            return None
        k = s["caps"].index(at_cap)
        caps_a, caps_b = s["caps"][:k], s["caps"][k:]
        text_a = " ".join(sentences.clean(self.cap(c)["text"]) for c in caps_a)
        text_b = " ".join(sentences.clean(self.cap(c)["text"]) for c in caps_b)
        s["caps"], s["raw"], s["text"], s["ai"], s["reading"] = caps_a, text_a, text_a, None, None
        self._recalc(s)
        new = {"id": self.data["next_id"], "caps": caps_b, "raw": text_b, "ai": None, "text": text_b, "reading": None,
               "speed": None, "pause": 0.0, "tts": None, "tts_dur": None, "check": False}
        self.data["next_id"] += 1
        self._recalc(new)
        self.data["sentences"].insert(i + 1, new)
        self.save()
        return new

    def merge_next(self, sid):
        i, s = self.find(sid)
        if i + 1 >= len(self.data["sentences"]):
            return None
        n = self.data["sentences"].pop(i + 1)
        s["caps"] += n["caps"]
        s["raw"] = (s["raw"] + " " + n["raw"]).strip()
        s["text"] = (s["text"] + " " + n["text"]).strip()
        s["ai"], s["reading"] = None, None
        s["check"] = s["check"] or n["check"]
        self._recalc(s)
        self.save()
        return s

    def delete_sentence(self, sid):
        i, s = self.find(sid)
        for c in s["caps"]:
            self.cap(c)["deleted"] = True
        self.data["sentences"].pop(i)
        self.save()

    # ---------- 잘라내기 구간 ----------
    def set_cuts(self, cuts):
        cuts = sorted([{"start": float(c["start"]), "end": float(c["end"]), "label": c.get("label", "잘라내기")}
                       for c in cuts if float(c["end"]) > float(c["start"])], key=lambda c: c["start"])
        merged = []
        for c in cuts:
            if merged and c["start"] <= merged[-1]["end"]:
                merged[-1]["end"] = max(merged[-1]["end"], c["end"])
            else:
                merged.append(c)
        self.data["cuts"] = merged
        # 잘라낸 구간 안의 문장은 목록에서 뺀다. 구간 밖으로 돌아온 자막(사용자가 지운 것 제외)은 다시 문장으로 만든다.
        self.data["sentences"] = [s for s in self.data["sentences"] if not self._in_cut(s["start"], s["end"])]
        kept = {c for s in self.data["sentences"] for c in s["caps"]}
        orphans = [c for c in self.data["captions"] if c["id"] not in kept and not c.get("deleted")
                   and not self._in_cut(c["start"], c["end"]) and c["text"]]
        for m in sentences.merge(orphans):
            new = {"id": self.data["next_id"], "caps": m["caps"], "start": m["start"], "end": m["end"], "raw": m["raw"],
                   "ai": None, "text": m["raw"], "reading": None, "speed": None, "pause": 0.0, "tts": None,
                   "tts_dur": None, "check": False}
            self.data["next_id"] += 1
            self.data["sentences"].append(new)
        self.data["sentences"].sort(key=lambda s: s["start"])
        self.save()
        return self.data["cuts"]

    def out_time(self, t):
        """원본 시간 -> 잘라낸 뒤의 출력 시간."""
        removed = 0.0
        for c in self.data["cuts"]:
            if c["end"] <= t:
                removed += c["end"] - c["start"]
            elif c["start"] < t:
                removed += t - c["start"]
        return t - removed


if __name__ == "__main__":
    import sys
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "new":
        p = Project.create(arg)
        print(p.dir)
    else:
        p = Project(arg)
        if cmd == "scan":
            n = p.scan(progress=lambda r: print(f"scan {r*100:.0f}%", flush=True))
            print("captions", n, "roi", p.data["roi"], "lyrics", p.data["ranges"]["lyrics"], "gaps", p.data["ranges"]["gaps"])
        elif cmd == "read":
            p.read(progress=lambda d, n: print(f"read {d}/{n}", flush=True))
            print("empty", sum(1 for c in p.data["captions"] if not c["text"]))
        elif cmd == "sentences":
            print("sentences", p.build_sentences())
        elif cmd == "correct":
            p.correct(progress=lambda d, n: print(f"correct {d}/{n}", flush=True))
            print("changed", sum(1 for s in p.data["sentences"] if s["ai"] and s["ai"] != s["raw"]))
