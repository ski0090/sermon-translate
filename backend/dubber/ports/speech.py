"""음성 합성 포트."""
from typing import Protocol


class SpeechSynth(Protocol):
    voices: list  # 고를 수 있는 목소리 이름

    def synth_to(self, path, text, voice, speed, steps) -> None:
        """text를 읽은 음성을 path(wav)에 쓴다. steps는 합성 단계 수(8 표준, 4 빠름)."""

    def duration(self, path) -> float:
        """wav 길이(초)."""
