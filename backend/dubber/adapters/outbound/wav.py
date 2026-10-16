"""wav 파일 읽고 쓰기(16비트 모노). 음성 엔진, 더빙 트랙, 음성 영상이 함께 쓴다."""
import wave

import numpy as np

SR = 44100


def write(path, samples, sr=SR):
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def read(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32767.0
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
    return data, sr


def duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()
