"""음성 유스케이스: 문장마다 한국어 음성을 만들고 캐시한다(같은 글·목소리·속도·품질이면 다시 만들지 않는다)."""
import hashlib
import os

SAMPLE_TEXT = "하나님의 은혜가 여러분과 함께하시기를 바랍니다. 요한복음 3장 16절 말씀을 함께 읽겠습니다."


def key_for(text, voice, speed, steps=8):
    tail = "" if int(steps) == 8 else f"|s{int(steps)}"
    return hashlib.sha1(f"{text}|{voice}|{speed:.3f}{tail}".encode("utf-8")).hexdigest()[:16]


class VoiceService:
    def __init__(self, speech, projects):
        self.speech = speech      # ports.SpeechSynth
        self.projects = projects  # application.projects.ProjectService

    @property
    def voices(self):
        return self.speech.voices

    def ensure(self, p, s, force=False):
        """문장 s의 음성을 만들어 두고 파일 이름과 길이를 기록한다. 이미 있으면 다시 만들지 않는다."""
        text = p.reading_of(s)
        if not text:
            s["tts"], s["tts_dur"] = None, 0.0
            return
        speed = float(s.get("speed") or p.settings["speed"])
        voice = p.settings["voice"]
        steps = int(p.settings.get("tts_steps") or 8)
        key = key_for(text, voice, speed, steps)
        path = os.path.join(self.projects.workspace(p.id).ensure("tts"), key + ".wav")
        if force or not os.path.exists(path):
            self.speech.synth_to(path, text, voice, speed, steps)
        s["tts"], s["tts_dur"] = key + ".wav", round(self.speech.duration(path), 3)

    def run_all(self, p, progress=None, cancel=None, force=False):
        ws = self.projects.workspace(p.id)
        sents = p.data["sentences"]
        todo = [s for s in sents if force or not s.get("tts") or not os.path.exists(ws.path("tts", s["tts"]))]
        for i, s in enumerate(todo):
            if cancel and cancel():
                break
            self.ensure(p, s, force=force)
            if i % 10 == 9:
                self.projects.save(p)
            if progress:
                progress(i + 1, len(todo))
        self.projects.save(p)

    def regenerate(self, pid, sid, body):
        """문장 하나의 음성을 다시 만든다(읽는 글이나 속도를 함께 고칠 수 있다)."""
        p, lock = self.projects.get(pid)
        with lock:
            _, s = p.find(sid)
            if "reading" in body or "speed" in body:
                p.update_sentence(sid, **{k: body[k] for k in ("reading", "speed") if k in body})
            self.ensure(p, s, force=True)
            self.projects.save(p)
            return s

    def sample(self, voice, samples_dir):
        """목소리 고르기용 짧은 예시 음성. 없으면 만든다."""
        path = os.path.join(samples_dir, f"sample_{voice}.wav")
        if not os.path.exists(path):
            self.speech.synth_to(path, SAMPLE_TEXT, voice, 1.05, 8)
        return path
