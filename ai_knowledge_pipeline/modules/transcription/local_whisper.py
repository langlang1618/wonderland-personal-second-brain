"""Local Whisper transcript import provider.

This provider does not run Whisper. It imports transcript files produced by
local tools such as MacWhisper and converts them into the existing provider
result schema.
"""

from __future__ import annotations

import re
from pathlib import Path

from ai_knowledge_pipeline.modules.transcription.errors import (
    TranscriptionErrorCode,
    TranscriptionIssue,
)
from ai_knowledge_pipeline.modules.transcription.interfaces import TranscriptionProvider
from ai_knowledge_pipeline.modules.transcription.types import (
    ProviderTranscriptionResult,
    TranscriptSegment,
    TranscriptTimestamp,
    TranscriptionRequest,
)


class LocalWhisperProvider(TranscriptionProvider):
    """Import local `.txt` or `.srt` Whisper transcript exports."""

    name = "local-whisper"

    def transcribe(
        self,
        request: TranscriptionRequest,
    ) -> ProviderTranscriptionResult:
        path = request.config.local_transcript_path
        if path is None:
            return _issue_result(
                TranscriptionErrorCode.MISSING_TRANSCRIPT_FILE,
                "A local transcript path is required.",
                "config.local_transcript_path",
            )
        if not path.exists():
            return _issue_result(
                TranscriptionErrorCode.MISSING_TRANSCRIPT_FILE,
                "Local transcript file does not exist.",
                "config.local_transcript_path",
                {"path": str(path)},
            )

        suffix = path.suffix.lower()
        try:
            payload = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            return _issue_result(
                TranscriptionErrorCode.TRANSCRIPT_PARSE_FAILED,
                str(exc),
                "config.local_transcript_path",
                {"path": str(path)},
            )

        if suffix == ".txt":
            return self._txt_result(payload, request, path)
        if suffix == ".srt":
            return self._srt_result(payload, request, path)
        return _issue_result(
            TranscriptionErrorCode.UNSUPPORTED_TRANSCRIPT_FORMAT,
            "Only .txt and .srt transcript imports are supported.",
            "config.local_transcript_path",
            {"suffix": suffix},
        )

    def _txt_result(
        self,
        payload: str,
        request: TranscriptionRequest,
        path: Path,
    ) -> ProviderTranscriptionResult:
        text = payload.strip()
        if not text:
            return _issue_result(
                TranscriptionErrorCode.TRANSCRIPT_PARSE_FAILED,
                "Transcript text file is empty.",
                "config.local_transcript_path",
                {"path": str(path)},
            )
        segment = TranscriptSegment(
            segment_index=0,
            timestamp=TranscriptTimestamp(
                start_time=request.chunk.start_time,
                end_time=request.chunk.end_time,
            ),
            text=text,
            metadata={"source_format": "txt", "source_path": str(path)},
        )
        return ProviderTranscriptionResult(
            text=text,
            segments=(segment,),
            language=request.config.language,
            model_name=request.config.model_name or self.name,
            metadata={"source_format": "txt", "source_path": str(path)},
        )

    def _srt_result(
        self,
        payload: str,
        request: TranscriptionRequest,
        path: Path,
    ) -> ProviderTranscriptionResult:
        segments = _parse_srt(payload, path)
        if not segments:
            return _issue_result(
                TranscriptionErrorCode.TRANSCRIPT_PARSE_FAILED,
                "SRT transcript contained no parseable segments.",
                "config.local_transcript_path",
                {"path": str(path)},
            )
        text = "\n".join(segment.text for segment in segments)
        return ProviderTranscriptionResult(
            text=text,
            segments=segments,
            language=request.config.language,
            model_name=request.config.model_name or self.name,
            metadata={
                "source_format": "srt",
                "source_path": str(path),
                "segment_count": len(segments),
            },
        )


def _parse_srt(payload: str, path: Path) -> tuple[TranscriptSegment, ...]:
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ()

    blocks = re.split(r"\n\s*\n", normalized)
    segments: list[TranscriptSegment] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        time_line_index = _find_time_line(lines)
        if time_line_index is None:
            continue
        timestamp = _parse_srt_timestamp_line(lines[time_line_index])
        if timestamp is None:
            continue

        text_lines = lines[time_line_index + 1 :]
        if not text_lines:
            continue
        text = " ".join(text_lines)
        segments.append(
            TranscriptSegment(
                segment_index=len(segments),
                timestamp=timestamp,
                text=text,
                metadata={"source_format": "srt", "source_path": str(path)},
            )
        )
    return tuple(segments)


def _find_time_line(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if "-->" in line:
            return index
    return None


def _parse_srt_timestamp_line(line: str) -> TranscriptTimestamp | None:
    if "-->" not in line:
        return None
    start_raw, end_raw = [part.strip() for part in line.split("-->", maxsplit=1)]
    end_raw = end_raw.split()[0]
    start = _parse_srt_time(start_raw)
    end = _parse_srt_time(end_raw)
    if start is None or end is None:
        return None
    return TranscriptTimestamp(start_time=start, end_time=end)


def _parse_srt_time(value: str) -> float | None:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", value)
    if not match:
        return None
    hours, minutes, seconds, millis = (int(group) for group in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def _issue_result(
    code: TranscriptionErrorCode,
    message: str,
    field: str,
    details=None,
) -> ProviderTranscriptionResult:
    return ProviderTranscriptionResult(
        text="",
        issues=(
            TranscriptionIssue(
                code=code,
                message=message,
                field=field,
                details=details or {},
            ),
        ),
    )


__all__ = ["LocalWhisperProvider"]
