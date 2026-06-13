"""faster-whisper local transcription provider."""

from __future__ import annotations

import signal
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ai_knowledge_pipeline.modules.transcription.errors import TranscriptionErrorCode
from ai_knowledge_pipeline.modules.transcription.interfaces import TranscriptionProvider
from ai_knowledge_pipeline.modules.transcription.runtime.errors import transcription_issue
from ai_knowledge_pipeline.modules.transcription.runtime.provider import (
    FasterWhisperModel,
    FasterWhisperModelFactory,
)
from ai_knowledge_pipeline.modules.transcription.runtime.types import (
    FasterWhisperConfig,
    FasterWhisperModelSize,
)
from ai_knowledge_pipeline.modules.transcription.types import (
    ProviderTranscriptionResult,
    TranscriptSegment,
    TranscriptTimestamp,
    TranscriptionRequest,
)


class FasterWhisperProvider(TranscriptionProvider):
    """Transcribe local audio chunks with faster-whisper."""

    name = "faster-whisper"

    def __init__(
        self,
        config: FasterWhisperConfig | None = None,
        model_factory: FasterWhisperModelFactory | None = None,
    ) -> None:
        self._config = config or FasterWhisperConfig()
        self._model_factory = model_factory
        self._model: FasterWhisperModel | None = None

    def transcribe(self, request: TranscriptionRequest) -> ProviderTranscriptionResult:
        if request.chunk.path is None:
            return _issue_result(
                TranscriptionErrorCode.MISSING_CHUNK_PATH,
                "faster-whisper requires a chunk audio path.",
                "chunk.path",
            )
        if not request.chunk.path.exists():
            return _issue_result(
                TranscriptionErrorCode.MISSING_CHUNK_PATH,
                "Chunk audio file does not exist.",
                "chunk.path",
                {"path": str(request.chunk.path)},
            )

        model_size = request.config.model_name or self._config.model_size.value
        language = request.config.language or self._config.language
        try:
            model = self._load_model(model_size)
        except ImportError:
            return _issue_result(
                TranscriptionErrorCode.MODEL_UNAVAILABLE,
                "faster-whisper package is not installed.",
                "faster_whisper",
            )
        except Exception as exc:
            return _issue_result(
                TranscriptionErrorCode.MODEL_LOAD_FAILED,
                _model_load_error_message(model_size, exc, self._config),
                "model_size",
                {
                    "model_size": model_size,
                    "attempts": str(_retry_count(self._config)),
                    "device": self._config.device,
                    "compute_type": self._config.compute_type,
                    "error_type": exc.__class__.__name__,
                },
            )

        try:
            raw_segments, info = _call_with_timeout(
                lambda: model.transcribe(
                    str(request.chunk.path),
                    language=language,
                ),
                timeout_seconds=self._config.transcription_timeout_seconds,
                operation="faster-whisper transcription",
            )
            segments = tuple(_segment(segment, index) for index, segment in enumerate(raw_segments))
        except Exception as exc:
            return _issue_result(
                TranscriptionErrorCode.AUDIO_TRANSCRIPTION_FAILED,
                _transcription_error_message(request.chunk.path, exc, self._config),
                "chunk.path",
                {
                    "path": str(request.chunk.path),
                    "model_size": model_size,
                    "timeout_seconds": str(self._config.transcription_timeout_seconds),
                    "error_type": exc.__class__.__name__,
                },
            )

        text = "\n".join(segment.text for segment in segments).strip()
        if not text:
            return _issue_result(
                TranscriptionErrorCode.INVALID_PROVIDER_RESULT,
                "faster-whisper returned no transcript text.",
                "segments",
            )

        detected_language = getattr(info, "language", None) or language
        confidence = _confidence(info)
        return ProviderTranscriptionResult(
            text=text,
            segments=segments,
            language=detected_language,
            confidence=confidence,
            model_name=model_size,
            metadata={
                "provider": self.name,
                "model_size": model_size,
                "source_path": str(request.chunk.path),
            },
        )

    def _load_model(self, model_size: str) -> FasterWhisperModel:
        if self._model is not None:
            return self._model
        factory = self._model_factory or _default_model_factory
        last_error: Exception | None = None
        for attempt in range(1, _retry_count(self._config) + 1):
            try:
                self._model = _call_with_timeout(
                    lambda: factory(
                        model_size,
                        device=self._config.device,
                        compute_type=self._config.compute_type,
                    ),
                    timeout_seconds=self._config.model_load_timeout_seconds,
                    operation="faster-whisper model load",
                )
                return self._model
            except ImportError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < _retry_count(self._config):
                    time.sleep(self._config.model_load_retry_delay_seconds)
        assert last_error is not None
        raise last_error
        return self._model


def _default_model_factory(model_size: str, **kwargs):
    from faster_whisper import WhisperModel

    try:
        return WhisperModel(model_size, local_files_only=True, **kwargs)
    except TypeError:
        raise
    except Exception:
        return WhisperModel(model_size, local_files_only=False, **kwargs)


def _retry_count(config: FasterWhisperConfig) -> int:
    return max(1, int(config.model_load_retries))


def _model_load_error_message(
    model_size: str,
    exc: Exception,
    config: FasterWhisperConfig,
) -> str:
    return (
        "Unable to load faster-whisper model "
        f"'{model_size}' after {_retry_count(config)} attempt(s). "
        "The provider tries the local HuggingFace cache first and then falls back "
        "to the normal faster-whisper loader. If this mentions 503 Service "
        "Unavailable, it is usually a transient HuggingFace/network issue; retry "
        "the command or pre-download the model cache. "
        f"Last error: {exc}"
    )


def _transcription_error_message(
    path: Path,
    exc: Exception,
    config: FasterWhisperConfig,
) -> str:
    return (
        f"faster-whisper failed while transcribing {path}. "
        f"Timeout protection: {config.transcription_timeout_seconds} seconds. "
        f"Last error: {exc}"
    )


def _call_with_timeout(function, *, timeout_seconds: float | None, operation: str):
    with _timeout(timeout_seconds, operation):
        return function()


@contextmanager
def _timeout(timeout_seconds: float | None, operation: str) -> Iterator[None]:
    if (
        timeout_seconds is None
        or timeout_seconds <= 0
        or threading.current_thread() is not threading.main_thread()
        or not hasattr(signal, "SIGALRM")
    ):
        yield
        return

    def _raise_timeout(signum, frame):
        raise TimeoutError(f"{operation} timed out after {timeout_seconds} seconds")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    signal.signal(signal.SIGALRM, _raise_timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def _segment(raw_segment, index: int) -> TranscriptSegment:
    return TranscriptSegment(
        segment_index=index,
        timestamp=TranscriptTimestamp(
            start_time=float(getattr(raw_segment, "start", 0.0)),
            end_time=float(getattr(raw_segment, "end", 0.0)),
        ),
        text=str(getattr(raw_segment, "text", "")).strip(),
        confidence=None,
    )


def _confidence(info) -> float | None:
    probability = getattr(info, "language_probability", None)
    return None if probability is None else float(probability)


def _issue_result(
    code: TranscriptionErrorCode,
    message: str,
    field: str,
    details=None,
) -> ProviderTranscriptionResult:
    return ProviderTranscriptionResult(
        text="",
        issues=(transcription_issue(code, message, field, details),),
    )


__all__ = ["FasterWhisperProvider"]
