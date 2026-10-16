"""음성 만들기: Supertonic(CPU, ONNX)으로 문장마다 한국어 음성을 만들고 캐시한다."""
import hashlib
import os
import threading
import wave

import numpy as np

SR = 44100
VOICES = ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"]
SAMPLE_TEXT = "하나님의 은혜가 여러분과 함께하시기를 바랍니다. 요한복음 3장 16절 말씀을 함께 읽겠습니다."

# 문장 하나를 만들 때 쓰는 CPU 스레드 수. 엔진은 한 문장으로 코어를 다 쓰지 못해서 여러 영상을 동시에 만드는 게
# 빠르지만, 작업마다 코어를 전부 쓰려 하면 서로 다툰다. 동시 작업 수 × 이 값이 코어 수쯤 되게 맞춘다.
THREADS = int(os.environ.get("DUBBER_TTS_THREADS", "4"))

_engine = None
_lock = threading.Lock()
_styles = {}


def engine():
    global _engine
    with _lock:
        if _engine is None:
            from supertonic import TTS
            _engine = TTS(intra_op_num_threads=THREADS, inter_op_num_threads=1)
        return _engine


def style(voice):
    if voice not in _styles:
        _styles[voice] = engine().get_voice_style(voice)
    return _styles[voice]


def synth(text, voice="F1", speed=1.05, steps=8):
    """float32 mono, SR Hz. steps는 합성 단계 수(8 표준, 4 빠름)."""
    wav, _ = engine().synthesize(text, voice_style=style(voice), lang="ko", speed=float(speed), total_steps=int(steps))
    return np.asarray(wav, dtype=np.float32).reshape(-1)


def write_wav(path, samples, sr=SR):
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32767.0
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
    return data, sr


def key_for(text, voice, speed, steps=8):
    tail = "" if int(steps) == 8 else f"|s{int(steps)}"
    return hashlib.sha1(f"{text}|{voice}|{speed:.3f}{tail}".encode("utf-8")).hexdigest()[:16]


def ensure(project, s, force=False):
    """문장 s의 음성을 만들어 두고 파일 이름과 길이를 기록한다. 이미 있으면 다시 만들지 않는다."""
    text = project.reading_of(s)
    if not text:
        s["tts"], s["tts_dur"] = None, 0.0
        return
    speed = float(s.get("speed") or project.data["settings"]["speed"])
    voice = project.data["settings"]["voice"]
    steps = int(project.data["settings"].get("tts_steps") or 8)
    key = key_for(text, voice, speed, steps)
    path = os.path.join(project.sub("tts"), key + ".wav")
    if force or not os.path.exists(path):
        write_wav(path, synth(text, voice, speed, steps))
    with wave.open(path, "rb") as w:
        dur = w.getnframes() / w.getframerate()
    s["tts"], s["tts_dur"] = key + ".wav", round(dur, 3)


def run_all(project, progress=None, cancel=None, force=False):
    sents = project.data["sentences"]
    todo = [s for s in sents if force or not s.get("tts") or not os.path.exists(os.path.join(project.dir, "tts", s["tts"]))]
    for i, s in enumerate(todo):
        if cancel and cancel():
            break
        ensure(project, s, force=force)
        if i % 10 == 9:
            project.save()
        if progress:
            progress(i + 1, len(todo))
    project.save()


def voice_sample(voice, out_dir):
    """목소리 고르기용 짧은 예시 음성. 없으면 만든다."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"sample_{voice}.wav")
    if not os.path.exists(path):
        write_wav(path, synth(SAMPLE_TEXT, voice, 1.05))
    return path


if __name__ == "__main__":
    import sys
    import time
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    t0 = time.time()
    a = synth("예수님이 재림 후 다스리실 새천년에 대한 것이라 하는데", "F1", 1.05)
    t1 = time.time()
    b = synth("우리는 이 땅이나 만민에 속하지 않습니다.", "F1", 1.05)
    t2 = time.time()
    print("warm", round(t1 - t0, 1), "s for", round(len(a) / SR, 1), "s audio; steady", round(t2 - t1, 2), "s for",
          round(len(b) / SR, 1), "s audio")
    write_wav(os.path.join(out, "tts_check.wav"), b)
    x, sr = read_wav(os.path.join(out, "tts_check.wav"))
    assert sr == SR and abs(len(x) - len(b)) < 2 and float(np.abs(x).max()) > 0.05
    print("ok")
