"""음성 합성(ports.SpeechSynth): Supertonic(CPU, ONNX)으로 한국어 음성을 만든다."""
import threading

import numpy as np

from . import wav

VOICES = ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"]


class SupertonicSpeech:
    voices = VOICES

    def __init__(self, threads=4):
        # 문장 하나를 만들 때 쓰는 CPU 스레드 수. 엔진은 한 문장으로 코어를 다 쓰지 못해서 여러 영상을 동시에 만드는
        # 게 빠르지만, 작업마다 코어를 전부 쓰려 하면 서로 다툰다. 동시 작업 수 × 이 값이 코어 수쯤 되게 맞춘다.
        self.threads = threads
        self._engine = None
        self._lock = threading.Lock()
        self._styles = {}

    def engine(self):
        with self._lock:
            if self._engine is None:
                from supertonic import TTS
                self._engine = TTS(intra_op_num_threads=self.threads, inter_op_num_threads=1)
            return self._engine

    def style(self, voice):
        if voice not in self._styles:
            self._styles[voice] = self.engine().get_voice_style(voice)
        return self._styles[voice]

    def synth(self, text, voice="F1", speed=1.05, steps=8):
        """float32 mono, wav.SR Hz. steps는 합성 단계 수(8 표준, 4 빠름)."""
        out, _ = self.engine().synthesize(text, voice_style=self.style(voice), lang="ko", speed=float(speed),
                                          total_steps=int(steps))
        return np.asarray(out, dtype=np.float32).reshape(-1)

    def synth_to(self, path, text, voice, speed, steps):
        wav.write(path, self.synth(text, voice, speed, steps))

    def duration(self, path):
        return wav.duration(path)
