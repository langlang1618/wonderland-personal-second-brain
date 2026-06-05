"""faster-whisper local transcription provider."""

from __future__ import annotations

from pathlib import Path

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
                str(exc),
                "model_size",
                {"model_size": model_size},
            )

        try:
            raw_segments, info = model.transcribe(
                str(request.chunk.path),
                language=language,
            )
            segments = tuple(_segment(segment, index) for index, segment in enumerate(raw_segments))
        except Exception as exc:
            return _issue_result(
                TranscriptionErrorCode.AUDIO_TRANSCRIPTION_FAILED,
                str(exc),
                "chunk.path",
                {"path": str(request.chunk.path)},
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
        self._model = factory(
            model_size,
            device=self._config.device,
            compute_type=self._config.compute_type,
        )
        return self._model


def _default_model_factory(model_size: str, **kwargs):
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, **kwargs)


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
