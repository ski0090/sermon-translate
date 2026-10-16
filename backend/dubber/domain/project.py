"""프로젝트(영상 한 편): 자막, 문장, 잘라내기 구간과 그 편집 규칙.
파일을 읽고 쓰는 일은 저장소(ports.ProjectRepository)가 하고, 여기서는 project.json에 담길 내용만 다룬다."""
import re
import time

from . import captions as caprules
from . import sentences

STEPS = ["load", "scan", "review", "tts", "export"]
DEFAULT_SETTINGS = {"voice": "F1", "speed": 1.05, "min_gap": 20, "tool": "claude", "orig_audio": "remove",
                    "per_strip": 25, "workers": 4, "dictionary": {}, "ai_tidy": True, "tts_steps": 8}
VOICE_KEYS = ("voice", "speed", "tts_steps")  # 바꾸면 모든 문장의 음성을 다시 만든다


def folder_name(name):
    """영상 이름으로 만든 프로젝트 폴더 이름(파일 이름에 못 쓰는 글자는 _로)."""
    s = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return s[:60] or "project"


def new_data(name, video, info, extra=None):
    """새 프로젝트의 project.json 내용."""
    return {"name": name, "video": video, "info": info, "roi": None, "step": "load", "captions": [],
            "sentences": [], "cuts": [], "ranges": {"gaps": [], "lyrics": []}, "settings": dict(DEFAULT_SETTINGS),
            "next_id": 1, "created": time.time(), **(extra or {})}


def summary(pid, data, updated):
    """프로젝트 목록 한 줄(진행 숫자)."""
    caps = data.get("captions", [])
    sents = data.get("sentences", [])
    return {"dir": pid, "name": data.get("name", pid), "video": data.get("video"), "step": data.get("step"),
            "updated": updated, "duration": data.get("info", {}).get("duration"),
            "captions": len(caps), "read": sum(1 for c in caps if c.get("text")),
            "sentences": len(sents), "tts": sum(1 for s in sents if s.get("tts")),
            "cuts": len(data.get("cuts", [])), "exported": bool(data.get("last_export")),
            "drive": (data.get("drive") or {}).get("path")}


class Project:
    def __init__(self, pid, data, stamp=None):
        self.id = pid
        self.data = data
        self.stamp = stamp  # 저장소가 다른 프로세스의 변경을 알아보려고 쓰는 값(파일 수정 시각)
        self.data.setdefault("settings", {})
        for k, v in DEFAULT_SETTINGS.items():
            self.data["settings"].setdefault(k, v)

    @property
    def name(self):
        return self.data["name"]

    @property
    def settings(self):
        return self.data["settings"]

    def set_step(self, step):
        if STEPS.index(step) > STEPS.index(self.data.get("step", "load")):
            self.data["step"] = step

    def view(self):
        """화면에 보낼 내용: 문장마다 지금 읽을 글(reading_auto)을 붙인다."""
        d = dict(self.data)
        d["sentences"] = [dict(s, reading_auto=self.reading_of(s)) for s in self.data["sentences"]]
        d["id"] = self.id
        return d

    # ---------- 진행 중인 단계 표시(서버가 꺼졌다 켜지면 이 표시로 이어 한다) ----------
    def mark_running(self, kind, params, restarts=0):
        self.data["running_step"] = {"kind": kind, "params": params, "restarts": restarts}

    def clear_running(self):
        self.data.pop("running_step", None)

    # ---------- 자막 읽기 ----------
    def set_roi(self, roi):
        self.data["roi"] = roi

    def set_captions(self, segs):
        """자막 바뀜 찾기 결과로 자막 목록을 새로 만든다(문장 목록은 지운다)."""
        self.data["captions"] = [dict(id=i, text="", check=False, **s) for i, s in enumerate(segs)]
        self.update_ranges()
        self.data["sentences"] = []
        self.set_step("scan")
        return len(segs)

    def update_ranges(self):
        d = self.data
        d["ranges"] = {"gaps": caprules.gaps(d["captions"], d["info"]["duration"], d["settings"]["min_gap"]),
                       "lyrics": caprules.lyric_ranges(d["captions"])}

    def set_caption_texts(self, texts):
        """AI가 읽은 글을 자막에 넣는다. 못 읽은 자막은 확인 필요로 둔다."""
        for c, t in zip(self.data["captions"], texts):
            c["text"] = t
            c["check"] = (t == "")

    def unread_ratio(self):
        caps = self.data["captions"]
        return sum(1 for c in caps if not (c.get("text") or "").strip()) / max(len(caps), 1)

    # ---------- 문장 정리 ----------
    def uncut_captions(self):
        return [c for c in self.data["captions"] if not c.get("deleted") and not self._in_cut(c["start"], c["end"])]

    def build_sentences(self, merged=None):
        """문장 목록을 새로 만든다. merged(AI 정리 결과)가 없으면 규칙으로 합친다."""
        self.data["sentences"] = [self._new(m) for m in (merged or sentences.merge(self.uncut_captions()))]
        self.set_step("review")
        return len(self.data["sentences"])

    def _new(self, m):
        """합친 결과 m(caps, raw와 AI 정리 결과)으로 새 문장을 만든다."""
        s = {"id": self.data["next_id"], "caps": m["caps"], "raw": m["raw"], "ai": m.get("ai"),
             "text": m.get("text", m["raw"]), "reading": None, "reading_ai": m.get("reading_ai"), "speed": None,
             "pause": 0.0, "tts": None, "tts_dur": None, "check": m.get("check", False), "note": m.get("note")}
        self.data["next_id"] += 1
        self._recalc(s)
        return s

    def _text_of(self, cap_ids):
        return " ".join(r["text"] for r in sentences.collapse([self.cap(c) for c in cap_ids]))

    def cap(self, cid):
        return self.data["captions"][cid]

    def _in_cut(self, start, end):
        mid = (start + end) / 2
        return any(c["start"] <= mid <= c["end"] for c in self.data["cuts"])

    def reading_of(self, s):
        if s.get("reading"):
            return s["reading"]
        return sentences.reading(s.get("reading_ai") or s["text"], self.data["settings"].get("dictionary"))

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
                    if k == "text":
                        s["reading_ai"] = None
                s[k] = v
        return s

    def split_sentence(self, sid, at_cap):
        """at_cap(자막 id)부터 뒤를 새 문장으로 나눈다. 자막이 하나뿐이면 글만 둘로 나눌 수 없으므로 그대로 둔다."""
        i, s = self.find(sid)
        if at_cap not in s["caps"] or at_cap == s["caps"][0]:
            return None
        k = s["caps"].index(at_cap)
        caps_a, caps_b = s["caps"][:k], s["caps"][k:]
        text_a = self._text_of(caps_a)
        s["caps"], s["raw"], s["text"], s["ai"], s["reading"], s["reading_ai"] = caps_a, text_a, text_a, None, None, None
        self._recalc(s)
        new = self._new({"caps": caps_b, "raw": self._text_of(caps_b)})
        self.data["sentences"].insert(i + 1, new)
        return new

    def merge_next(self, sid):
        i, s = self.find(sid)
        if i + 1 >= len(self.data["sentences"]):
            return None
        n = self.data["sentences"].pop(i + 1)
        s["caps"] += n["caps"]
        s["raw"] = (s["raw"] + " " + n["raw"]).strip()
        s["text"] = (s["text"] + " " + n["text"]).strip()
        s["ai"], s["reading"], s["reading_ai"] = None, None, None
        s["check"] = s["check"] or n["check"]
        s["note"] = s.get("note") or n.get("note")
        self._recalc(s)
        return s

    def delete_sentence(self, sid):
        i, s = self.find(sid)
        for c in s["caps"]:
            self.cap(c)["deleted"] = True
        self.data["sentences"].pop(i)

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
        orphans = [c for c in self.uncut_captions() if c["id"] not in kept]
        self.data["sentences"] += [self._new(m) for m in sentences.merge(orphans)]
        self.data["sentences"].sort(key=lambda s: s["start"])
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

    # ---------- 설정 ----------
    def apply_settings(self, body):
        """프로젝트 설정을 바꾼다. 목소리·속도·품질이 바뀌면 모든 문장의 음성을 다시 만들도록 지운다."""
        for k, v in body.items():
            if k in DEFAULT_SETTINGS:
                self.data["settings"][k] = v
        if "min_gap" in body:
            self.update_ranges()
        if any(k in body for k in VOICE_KEYS):
            for s in self.data["sentences"]:
                s["tts"], s["tts_dur"] = None, None
        return self.data["settings"]
