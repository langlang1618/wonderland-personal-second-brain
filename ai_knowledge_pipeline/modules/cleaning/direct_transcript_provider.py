"""Deterministic transcript passthrough for transcript-first output profiles."""

from __future__ import annotations

import re

from ai_knowledge_pipeline.modules.cleaning.types import (
    CleaningProviderResult,
    MarkdownReadyTranscript,
    TranscriptCleaningRequest,
)


_SUBTITLE_TIMING_LINE = re.compile(
    r"^(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3}\s+-->\s+"
    r"(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3}(?:\s+.*)?$"
)
_SUBTITLE_CONTROL_TAG = re.compile(
    r"</?(?:c(?:\.[^ >]+)?|v(?:\s+[^>]*)?|i|b|u|ruby|rt)(?:\s+[^>]*)?>"
    r"|<\d{2}:\d{2}(?::\d{2})?[.,]\d{3}>",
    re.IGNORECASE,
)


class DirectTranscriptCleaningProvider:
    """Prepare a readable transcript without semantic rewriting or an AI call."""

    name = "direct-transcript"

    def clean(self, request: TranscriptCleaningRequest) -> CleaningProviderResult:
        transcript = request.transcript
        title = str(
            request.metadata.get("title")
            or transcript.snapshot.metadata.title
            or "Transcript"
        )
        text = _direct_transcript_text(transcript.text, transcript.segments)
        return CleaningProviderResult(
            markdown_ready=MarkdownReadyTranscript(
                title=title,
                summary="",
                cleaned_text=text,
                readable_transcript_text=text,
            ),
            model_name=self.name,
            prompt_version="direct-transcript-v1",
            language=transcript.language,
            metadata={"output_strategy": "direct_transcript"},
        )


def _direct_transcript_text(text: str, segments) -> str:
    usable_segments = []
    for segment in segments:
        normalized = _normalize_plain_text(segment.text)
        if normalized and (not usable_segments or normalized != usable_segments[-1][1]):
            usable_segments.append((segment, normalized))

    has_srt_segments = any(
        segment.metadata.get("source_format") == "srt"
        for segment, _ in usable_segments
    )
    if len(usable_segments) > 1 or has_srt_segments:
        return "\n\n".join(
            f"[{_format_timestamp(segment.timestamp.start_time)}] {normalized}"
            for segment, normalized in usable_segments
        )
    return _normalize_plain_text(text)


def _normalize_plain_text(text: str) -> str:
    lines: list[str] = []
    previous = ""
    normalized_source = text.replace("\r\n", "\n").replace("\r", "\n")
    contains_subtitle_timing = any(
        _SUBTITLE_TIMING_LINE.fullmatch(line.strip())
        for line in normalized_source.splitlines()
    )
    for raw_line in normalized_source.splitlines():
        line = raw_line.strip()
        if not line or line.upper() == "WEBVTT":
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if _SUBTITLE_TIMING_LINE.fullmatch(line) or (
            contains_subtitle_timing and re.fullmatch(r"\d+", line)
        ):
            continue
        line = _SUBTITLE_CONTROL_TAG.sub("", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line or line == previous:
            continue
        lines.append(line)
        previous = line
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


__all__ = ["DirectTranscriptCleaningProvider"]
