"""Acquire and normalize YouTube subtitles through the existing yt-dlp runtime."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping, Protocol

from ai_knowledge_pipeline.modules.download.runner import SubprocessYtDlpRunner
from ai_knowledge_pipeline.modules.download.types import MediaDownloadConfig


_VTT_TIMING_LINE = re.compile(
    r"^(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3}\s+-->\s+"
    r"(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3}(?:\s+.*)?$"
)
_VTT_CONTROL_TAG = re.compile(
    r"</?(?:c(?:\.[^ >]+)?|v(?:\s+[^>]*)?|i|b|u|ruby|rt)(?:\s+[^>]*)?>"
    r"|<\d{2}:\d{2}(?::\d{2})?[.,]\d{3}>",
    re.IGNORECASE,
)
_OVERLAP_TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
_MIN_ROLLING_OVERLAP_TOKENS = 4


class YouTubeSubtitleStatus(StrEnum):
    """Outcome of one best-effort YouTube subtitle extraction attempt."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class YouTubeSubtitleKind(StrEnum):
    """Subtitle category selected from yt-dlp metadata."""

    MANUAL = "manual"
    AUTOMATIC = "automatic"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class YouTubeSubtitleRequest:
    """Input for acquiring subtitles into the existing transcript handoff."""

    source_url: str
    output_dir: Path
    language: str | None = "zh"
    ytdlp_binary: str = "yt-dlp"
    subtitle_kind: YouTubeSubtitleKind = YouTubeSubtitleKind.BOTH
    language_preferences: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class YouTubeSubtitleResult:
    """Structured subtitle acquisition result used by orchestration."""

    status: YouTubeSubtitleStatus
    transcript_path: Path | None = None
    subtitle_path: Path | None = None
    message: str | None = None

    @property
    def is_available(self) -> bool:
        return self.status is YouTubeSubtitleStatus.AVAILABLE


@dataclass(frozen=True, slots=True)
class YouTubeSubtitleInspectionResult:
    """Structured subtitle inventory returned by yt-dlp metadata."""

    status: YouTubeSubtitleStatus
    manual_languages: tuple[str, ...] = ()
    automatic_languages: tuple[str, ...] = ()
    executable: str | None = None
    version: str | None = None
    message: str | None = None


class YtDlpRunner(Protocol):
    """Small runner boundary shared with the existing download runtime."""

    def run(self, command: tuple[str, ...], config: MediaDownloadConfig): ...


class YouTubeSubtitleInspector:
    """Inspect available subtitle categories using structured yt-dlp JSON."""

    def __init__(self, runner: YtDlpRunner | None = None) -> None:
        self._runner = runner or SubprocessYtDlpRunner()

    def inspect(
        self,
        source_url: str,
        *,
        ytdlp_binary: str = "yt-dlp",
    ) -> YouTubeSubtitleInspectionResult:
        executable = resolve_ytdlp_executable(ytdlp_binary)
        if executable is None:
            return YouTubeSubtitleInspectionResult(
                status=YouTubeSubtitleStatus.FAILED,
                message=f"yt-dlp executable not found: {ytdlp_binary}",
            )
        config = MediaDownloadConfig(ytdlp_binary=executable)
        version_result = self._runner.run((executable, "--version"), config)
        version = (
            version_result.output.stdout.strip().splitlines()[0]
            if version_result.returncode == 0 and version_result.output.stdout.strip()
            else None
        )
        command = build_youtube_subtitle_inspection_command(source_url, executable)
        process_result = self._runner.run(command, config)
        if process_result.returncode != 0:
            return YouTubeSubtitleInspectionResult(
                status=YouTubeSubtitleStatus.FAILED,
                executable=executable,
                version=version,
                message=f"yt-dlp subtitle inspection failed: {_error_excerpt(process_result.output.stderr)}",
            )
        try:
            payload = _structured_json(process_result.output.stdout)
            manual = _language_keys(payload.get("subtitles"))
            automatic = _language_keys(payload.get("automatic_captions"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return YouTubeSubtitleInspectionResult(
                status=YouTubeSubtitleStatus.FAILED,
                executable=executable,
                version=version,
                message=f"Invalid yt-dlp subtitle metadata: {exc}",
            )
        return YouTubeSubtitleInspectionResult(
            status=YouTubeSubtitleStatus.AVAILABLE,
            manual_languages=manual,
            automatic_languages=automatic,
            executable=executable,
            version=version,
        )


class YouTubeSubtitleExtractor:
    """Best-effort yt-dlp subtitle acquisition without downloading media."""

    def __init__(self, runner: YtDlpRunner | None = None) -> None:
        self._runner = runner or SubprocessYtDlpRunner()

    def extract(self, request: YouTubeSubtitleRequest) -> YouTubeSubtitleResult:
        executable = resolve_ytdlp_executable(request.ytdlp_binary)
        if executable is None:
            return YouTubeSubtitleResult(
                status=YouTubeSubtitleStatus.FAILED,
                message=f"yt-dlp executable not found: {request.ytdlp_binary}",
            )
        request.output_dir.mkdir(parents=True, exist_ok=True)
        subtitle_dir = request.output_dir / "youtube_subtitles"
        subtitle_dir.mkdir(parents=True, exist_ok=True)
        for stale_subtitle in subtitle_dir.glob("subtitle*.vtt"):
            stale_subtitle.unlink()
        command = build_youtube_subtitle_command(
            request,
            subtitle_dir,
            executable=executable,
        )
        process_result = self._runner.run(
            command,
            MediaDownloadConfig(ytdlp_binary=executable),
        )

        for subtitle_path in _subtitle_candidates(subtitle_dir, request.language):
            transcript_text = normalize_vtt(
                subtitle_path.read_text(encoding="utf-8"),
                remove_rolling_overlap=(
                    request.subtitle_kind is YouTubeSubtitleKind.AUTOMATIC
                ),
            )
            if transcript_text:
                transcript_path = request.output_dir / "merged_transcript.txt"
                transcript_path.write_text(transcript_text + "\n", encoding="utf-8")
                return YouTubeSubtitleResult(
                    status=YouTubeSubtitleStatus.AVAILABLE,
                    transcript_path=transcript_path,
                    subtitle_path=subtitle_path,
                )

        if process_result.returncode != 0:
            detail = _error_excerpt(process_result.output.stderr)
            return YouTubeSubtitleResult(
                status=YouTubeSubtitleStatus.FAILED,
                message=f"yt-dlp subtitle extraction failed: {detail}",
            )
        return YouTubeSubtitleResult(
            status=YouTubeSubtitleStatus.UNAVAILABLE,
            message="YouTube subtitles are unavailable or empty.",
        )


def build_youtube_subtitle_command(
    request: YouTubeSubtitleRequest,
    subtitle_dir: Path,
    *,
    executable: str | None = None,
) -> tuple[str, ...]:
    """Build a subtitle-only yt-dlp command with deterministic language order."""

    output_template = subtitle_dir / "subtitle.%(ext)s"
    args = [
        executable or request.ytdlp_binary,
        "--no-playlist",
        "--skip-download",
    ]
    if request.subtitle_kind in {YouTubeSubtitleKind.MANUAL, YouTubeSubtitleKind.BOTH}:
        args.append("--write-subs")
    if request.subtitle_kind in {YouTubeSubtitleKind.AUTOMATIC, YouTubeSubtitleKind.BOTH}:
        args.append("--write-auto-subs")
    args.extend([
        "--sub-langs",
        ",".join(request.language_preferences or _language_preferences(request.language)),
        "--sub-format",
        "vtt",
        "--output",
        str(output_template),
        request.source_url,
    ])
    return tuple(args)


def build_youtube_subtitle_inspection_command(
    source_url: str,
    executable: str = "yt-dlp",
) -> tuple[str, ...]:
    """Build a metadata-only command whose stdout is one JSON object."""

    return (
        executable,
        "--no-playlist",
        "--skip-download",
        "--dump-single-json",
        source_url,
    )


def resolve_ytdlp_executable(binary: str = "yt-dlp") -> str | None:
    """Resolve yt-dlp predictably, preferring the active Python environment."""

    candidate = Path(binary).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        resolved = candidate.resolve()
        return str(resolved) if resolved.is_file() and os.access(resolved, os.X_OK) else None
    environment_binary = Path(sys.executable).resolve().parent / binary
    if environment_binary.is_file() and os.access(environment_binary, os.X_OK):
        return str(environment_binary)
    return shutil.which(binary)


def normalize_vtt(content: str, *, remove_rolling_overlap: bool = False) -> str:
    """Convert VTT cues to plain text and collapse obvious rolling duplicates."""

    cues: list[str] = []
    for block in re.split(r"\r?\n\s*\r?\n", content.lstrip("\ufeff")):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].upper().startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        timestamp_index = next(
            (
                index
                for index, line in enumerate(lines)
                if _VTT_TIMING_LINE.fullmatch(line)
            ),
            None,
        )
        if timestamp_index is None:
            continue
        cue = " ".join(_clean_caption_line(line) for line in lines[timestamp_index + 1 :])
        cue = re.sub(r"\s+", " ", cue).strip()
        if cue:
            _append_nonduplicate(
                cues,
                cue,
                remove_rolling_overlap=remove_rolling_overlap,
            )
    return "\n".join(cues).strip()


def _clean_caption_line(line: str) -> str:
    line = _VTT_CONTROL_TAG.sub("", line)
    return html.unescape(line).strip()


def _append_nonduplicate(
    cues: list[str],
    cue: str,
    *,
    remove_rolling_overlap: bool = False,
) -> None:
    if not cues:
        cues.append(cue)
        return
    previous = cues[-1]
    if cue == previous or previous.startswith(cue):
        return
    if remove_rolling_overlap:
        suffix = _non_overlapping_suffix(previous, cue)
        if suffix is not None:
            if suffix:
                cues.append(suffix)
            return
    if cue.startswith(previous):
        cues[-1] = cue
        return
    cues.append(cue)


def _non_overlapping_suffix(previous: str, current: str) -> str | None:
    """Return new cue text after a confident adjacent word overlap."""

    previous_tokens = [
        match.group(0).casefold() for match in _OVERLAP_TOKEN.finditer(previous)
    ]
    current_matches = list(_OVERLAP_TOKEN.finditer(current))
    current_tokens = [match.group(0).casefold() for match in current_matches]
    maximum = min(len(previous_tokens), len(current_tokens))

    for size in range(maximum, _MIN_ROLLING_OVERLAP_TOKENS - 1, -1):
        if previous_tokens[-size:] != current_tokens[:size]:
            continue
        suffix = current[current_matches[size - 1].end() :].lstrip()
        return re.sub(r"^[,;:]\s*", "", suffix)
    return None


def _language_preferences(language: str | None) -> tuple[str, ...]:
    normalized = (language or "").lower()
    if normalized.startswith("zh"):
        return ("zh-Hans", "zh-Hant", "zh", "en")
    if normalized:
        return (language or normalized, "en") if normalized != "en" else ("en",)
    return ("zh-Hans", "zh-Hant", "zh", "en")


def _structured_json(stdout: str) -> Mapping[str, object]:
    value = stdout.strip()
    if not value:
        raise ValueError("yt-dlp returned empty metadata")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        json_lines = [line for line in value.splitlines() if line.lstrip().startswith("{")]
        if not json_lines:
            raise
        payload = json.loads(json_lines[-1])
    if not isinstance(payload, dict):
        raise TypeError("yt-dlp metadata must be a JSON object")
    return payload


def _language_keys(value: object) -> tuple[str, ...]:
    if not isinstance(value, dict):
        return ()
    return tuple(sorted(str(key) for key in value if str(key).strip()))


def _subtitle_candidates(subtitle_dir: Path, language: str | None) -> tuple[Path, ...]:
    preferences = _language_preferences(language)
    paths = tuple(subtitle_dir.glob("subtitle*.vtt"))

    def sort_key(path: Path) -> tuple[int, str]:
        name = path.name.lower()
        rank = next(
            (index for index, code in enumerate(preferences) if f".{code.lower()}." in name),
            len(preferences),
        )
        return rank, name

    return tuple(sorted(paths, key=sort_key))


def _error_excerpt(value: str, limit: int = 300) -> str:
    text = " ".join(value.split()) or "unknown yt-dlp error"
    return text if len(text) <= limit else f"{text[:limit]}..."


__all__ = [
    "YouTubeSubtitleExtractor",
    "YouTubeSubtitleInspectionResult",
    "YouTubeSubtitleInspector",
    "YouTubeSubtitleKind",
    "YouTubeSubtitleRequest",
    "YouTubeSubtitleResult",
    "YouTubeSubtitleStatus",
    "build_youtube_subtitle_command",
    "build_youtube_subtitle_inspection_command",
    "normalize_vtt",
    "resolve_ytdlp_executable",
]
