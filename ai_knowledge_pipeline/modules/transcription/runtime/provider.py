"""Runtime provider protocols."""

from __future__ import annotations

from typing import Protocol


class FasterWhisperModel(Protocol):
    """Minimal faster-whisper model protocol."""

    def transcribe(self, audio, **kwargs): ...


class FasterWhisperModelFactory(Protocol):
    """Factory used to construct faster-whisper models."""

    def __call__(self, model_size: str, **kwargs) -> FasterWhisperModel: ...


__all__ = ["FasterWhisperModel", "FasterWhisperModelFactory"]
