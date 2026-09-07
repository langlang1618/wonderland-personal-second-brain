"""Deterministic transcript acquisition coordination.

The coordinator selects native subtitles when policy permits and delegates the
existing media/Whisper route through a small callback. It contains no profile,
Markdown, cleaning, or Obsidian behavior.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Callable, Mapping

from ai_knowledge_pipeline.core.artifact import (
    ArtifactIntegrity,
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
    ArtifactVisibility,
    IntegrityAlgorithm,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.core.source import SourceData, SourceKind
from ai_knowledge_pipeline.infra.runtime_logging import (
    STAGE_YOUTUBE_SUBTITLE_EXTRACTION,
    RuntimeLogger,
    create_runtime_logger,
)
from ai_knowledge_pipeline.modules.chunking import MediaChunkArtifact, MediaChunkingStatus
from ai_knowledge_pipeline.modules.transcription.local_whisper import LocalWhisperProvider
from ai_knowledge_pipeline.modules.transcription.runtime.youtube_subtitles import (
    YouTubeSubtitleExtractor,
    YouTubeSubtitleInspectionResult,
    YouTubeSubtitleInspector,
    YouTubeSubtitleKind,
    YouTubeSubtitleRequest,
    YouTubeSubtitleResult,
    YouTubeSubtitleStatus,
)
from ai_knowledge_pipeline.modules.transcription.transcriber import create_default_transcriber
from ai_knowledge_pipeline.modules.transcription.types import (
    TranscriptArtifact,
    TranscriptionConfig,
    TranscriptionProviderKind,
    TranscriptionRequest,
)


class TranscriptAcquisitionGoal(StrEnum):
    """User intent that influences transcript acquisition policy."""

    KNOWLEDGE_INGESTION = "knowledge-ingestion"
    ENGLISH_LEARNING = "english-learning"


class TranscriptAcquisitionMethod(StrEnum):
    """Method that produced the accepted transcript."""

    CACHED = "cached"
    YOUTUBE_MANUAL_SUBTITLE = "youtube-manual-subtitle"
    YOUTUBE_AUTOMATIC_CAPTION = "youtube-automatic-caption"
    WHISPER = "whisper"


@dataclass(frozen=True, slots=True)
class TranscriptAcquisitionPolicy:
    """Explicit subtitle and Whisper language choices for one acquisition."""

    goal: TranscriptAcquisitionGoal
    subtitle_language_preferences: tuple[str, ...]
    whisper_language: str | None
    expected_language: str | None = None
    minimum_useful_characters: int = 20


@dataclass(frozen=True, slots=True)
class TranscriptAcquisitionRequest:
    """Input to deterministic transcript acquisition."""

    source: SourceData
    output_dir: Path
    policy: TranscriptAcquisitionPolicy
    skip_existing: bool = False


@dataclass(frozen=True, slots=True)
class WhisperFallbackResult:
    """Compatibility result supplied by the existing media/Whisper runtime."""

    transcript_path: Path
    metadata: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TranscriptAcquisitionResult:
    """Accepted transcript plus compatibility path and acquisition metadata."""

    transcript: TranscriptArtifact
    transcript_path: Path
    method: TranscriptAcquisitionMethod
    language: str | None
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TranscriptValidationResult:
    """Conservative deterministic validation outcome."""

    is_valid: bool
    reason: str | None = None


class TranscriptAcquisitionError(RuntimeError):
    """Raised when no acquisition route produces a usable transcript."""


SubtitleInspector = Callable[[str], YouTubeSubtitleInspectionResult]
SubtitleExtractor = Callable[[YouTubeSubtitleRequest], YouTubeSubtitleResult]
WhisperFallback = Callable[[str | None], WhisperFallbackResult]


class TranscriptAcquisitionCoordinator:
    """Choose, validate, and materialize a transcript using existing runtimes."""

    def __init__(
        self,
        *,
        subtitle_inspector: SubtitleInspector | None = None,
        subtitle_extractor: SubtitleExtractor | None = None,
        logger: RuntimeLogger | None = None,
    ) -> None:
        self._subtitle_inspector = subtitle_inspector or YouTubeSubtitleInspector().inspect
        self._subtitle_extractor = subtitle_extractor or YouTubeSubtitleExtractor().extract
        self._logger = logger or create_runtime_logger()

    def acquire(
        self,
        request: TranscriptAcquisitionRequest,
        *,
        whisper_fallback: WhisperFallback,
    ) -> TranscriptAcquisitionResult:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        cached = self._load_compatible_cache(request)
        if cached is not None:
            return cached

        warnings: list[str] = []
        if request.source.kind is SourceKind.YOUTUBE:
            with self._logger.stage(STAGE_YOUTUBE_SUBTITLE_EXTRACTION):
                native = self._try_youtube_subtitles(request, warnings)
            if native is not None:
                self._write_manifest(request, native)
                return native

        self._logger.info(
            "Transcript Acquisition: using Whisper fallback "
            f"(language={request.policy.whisper_language or 'auto'})"
        )
        fallback = whisper_fallback(request.policy.whisper_language)
        validation = validate_transcript_path(fallback.transcript_path, request.policy)
        if not validation.is_valid:
            raise TranscriptAcquisitionError(
                "Whisper transcript failed validation: "
                f"{validation.reason or 'unknown validation error'}"
            )
        warnings.extend(fallback.warnings)
        result = self._result_from_path(
            request,
            fallback.transcript_path,
            method=TranscriptAcquisitionMethod.WHISPER,
            language=request.policy.whisper_language,
            warnings=tuple(warnings),
            metadata=fallback.metadata,
        )
        self._write_manifest(request, result)
        return result

    def _try_youtube_subtitles(
        self,
        request: TranscriptAcquisitionRequest,
        warnings: list[str],
    ) -> TranscriptAcquisitionResult | None:
        try:
            inspection = self._subtitle_inspector(request.source.location.uri)
        except Exception as exc:
            warning = f"YouTube subtitle inspection failed: {exc}"
            warnings.append(warning)
            self._logger.warning(
                f"YouTube subtitle inspection failed; falling back to Whisper. {exc}"
            )
            return None
        if inspection.executable:
            self._logger.info(f"yt-dlp executable: {inspection.executable}")
        self._logger.info(f"yt-dlp version: {inspection.version or 'unknown'}")
        if inspection.status is YouTubeSubtitleStatus.FAILED:
            warning = inspection.message or "YouTube subtitle inspection failed."
            warnings.append(warning)
            self._logger.warning(f"{warning} Falling back to Whisper.")
            return None

        selected = _select_subtitle(inspection, request.policy.subtitle_language_preferences)
        if selected is None:
            warning = "No preferred YouTube subtitle language is available."
            warnings.append(warning)
            self._logger.warning(f"{warning} Falling back to Whisper.")
            return None
        kind, language = selected
        self._logger.info(
            f"YouTube subtitle selected: category={kind.value}, language={language}"
        )
        try:
            result = self._subtitle_extractor(
                YouTubeSubtitleRequest(
                    source_url=request.source.location.uri,
                    output_dir=request.output_dir,
                    language=language,
                    ytdlp_binary=inspection.executable or "yt-dlp",
                    subtitle_kind=kind,
                    language_preferences=(language,),
                )
            )
        except Exception as exc:
            warning = f"YouTube subtitle extraction failed: {exc}"
            warnings.append(warning)
            self._logger.warning(
                f"YouTube subtitle extraction failed; falling back to Whisper. {exc}"
            )
            return None
        if not result.is_available or result.transcript_path is None:
            warning = result.message or "Selected YouTube subtitle could not be acquired."
            warnings.append(warning)
            self._logger.warning(f"{warning} Falling back to Whisper.")
            return None
        validation = validate_transcript_path(result.transcript_path, request.policy)
        if not validation.is_valid:
            warning = f"YouTube subtitle failed validation: {validation.reason}"
            warnings.append(warning)
            self._logger.warning(f"{warning}. Falling back to Whisper.")
            return None
        method = (
            TranscriptAcquisitionMethod.YOUTUBE_MANUAL_SUBTITLE
            if kind is YouTubeSubtitleKind.MANUAL
            else TranscriptAcquisitionMethod.YOUTUBE_AUTOMATIC_CAPTION
        )
        return self._result_from_path(
            request,
            result.transcript_path,
            method=method,
            language=language,
            warnings=tuple(warnings),
            metadata={
                "subtitle_path": str(result.subtitle_path) if result.subtitle_path else "",
                "ytdlp_executable": inspection.executable or "",
                "ytdlp_version": inspection.version or "",
                "subtitle_kind": kind.value,
            },
        )

    def _load_compatible_cache(
        self,
        request: TranscriptAcquisitionRequest,
    ) -> TranscriptAcquisitionResult | None:
        transcript_path = request.output_dir / "merged_transcript.txt"
        manifest_path = _manifest_path(request.output_dir)
        if not request.skip_existing or not transcript_path.exists() or not manifest_path.exists():
            return None
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not _cache_is_compatible(payload, request):
            self._logger.warning(
                "Existing transcript acquisition cache is incompatible; reacquiring."
            )
            return None
        validation = validate_transcript_path(transcript_path, request.policy)
        if not validation.is_valid:
            self._logger.warning(
                f"Existing transcript cache failed validation: {validation.reason}; reacquiring."
            )
            return None
        self._logger.info(f"skip_existing: using compatible transcript: {transcript_path}")
        return self._result_from_path(
            request,
            transcript_path,
            method=TranscriptAcquisitionMethod.CACHED,
            language=_optional_string(payload.get("language")),
            metadata={"cached_method": str(payload.get("method", "unknown"))},
        )

    def _result_from_path(
        self,
        request: TranscriptAcquisitionRequest,
        transcript_path: Path,
        *,
        method: TranscriptAcquisitionMethod,
        language: str | None,
        warnings: tuple[str, ...] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> TranscriptAcquisitionResult:
        transcript = _materialize_transcript(request.source, transcript_path, language)
        return TranscriptAcquisitionResult(
            transcript=transcript,
            transcript_path=transcript_path,
            method=method,
            language=language,
            warnings=warnings,
            metadata=metadata or {},
        )

    def _write_manifest(
        self,
        request: TranscriptAcquisitionRequest,
        result: TranscriptAcquisitionResult,
    ) -> None:
        payload = {
            "source_id": request.source.source_id,
            "source_uri": request.source.location.uri,
            "goal": request.policy.goal.value,
            "subtitle_language_preferences": list(
                request.policy.subtitle_language_preferences
            ),
            "whisper_language": request.policy.whisper_language,
            "expected_language": request.policy.expected_language,
            "method": result.method.value,
            "language": result.language,
            "transcript_path": str(result.transcript_path),
            "warnings": list(result.warnings),
            "metadata": dict(result.metadata),
        }
        _manifest_path(request.output_dir).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def validate_transcript_path(
    transcript_path: Path,
    policy: TranscriptAcquisitionPolicy,
) -> TranscriptValidationResult:
    """Validate useful length and reject only clearly wrong English output."""

    try:
        text = transcript_path.read_text(encoding="utf-8-sig").strip()
    except OSError as exc:
        return TranscriptValidationResult(False, f"transcript is unreadable: {exc}")
    useful = re.sub(r"\s+", "", text)
    if not useful:
        return TranscriptValidationResult(False, "transcript is empty")
    if len(useful) < max(1, policy.minimum_useful_characters):
        return TranscriptValidationResult(
            False,
            f"transcript has fewer than {policy.minimum_useful_characters} useful characters",
        )
    if (policy.expected_language or "").lower().startswith("en"):
        latin_count = len(re.findall(r"[A-Za-z]", text))
        cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
        language_chars = latin_count + cjk_count
        if cjk_count >= 12 and language_chars and cjk_count / language_chars >= 0.7:
            return TranscriptValidationResult(
                False,
                "transcript is strongly CJK-dominant but English was expected",
            )
    return TranscriptValidationResult(True)


def _select_subtitle(
    inspection: YouTubeSubtitleInspectionResult,
    preferences: tuple[str, ...],
) -> tuple[YouTubeSubtitleKind, str] | None:
    manual = _preferred_language(inspection.manual_languages, preferences)
    if manual is not None:
        return YouTubeSubtitleKind.MANUAL, manual
    automatic = _preferred_language(inspection.automatic_languages, preferences)
    if automatic is not None:
        return YouTubeSubtitleKind.AUTOMATIC, automatic
    return None


def _preferred_language(
    available: tuple[str, ...],
    preferences: tuple[str, ...],
) -> str | None:
    by_lower = {language.lower(): language for language in available}
    for preference in preferences:
        exact = by_lower.get(preference.lower())
        if exact is not None:
            return exact
    for preference in preferences:
        prefix = f"{preference.lower()}-"
        match = next(
            (language for language in available if language.lower().startswith(prefix)),
            None,
        )
        if match is not None:
            return match
    return None


def _materialize_transcript(
    source: SourceData,
    transcript_path: Path,
    language: str | None,
) -> TranscriptArtifact:
    artifact_id = f"chunk_{source.source_id}_acquired"
    uri = transcript_path.as_uri() if transcript_path.is_absolute() else f"file://{transcript_path}"
    snapshot = ArtifactSnapshot(
        artifact_id=artifact_id,
        snapshot_id=f"{artifact_id}_v1",
        kind=ArtifactKind.CHUNK,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri=uri,
            path=transcript_path,
            media_type="text/plain",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(source_id=source.source_id, stage_id="transcript-acquisition"),
        integrity=ArtifactIntegrity(algorithm=IntegrityAlgorithm.NONE),
        metadata=ArtifactMetadata(
            title=source.metadata.title,
            language=language,
            tags=source.metadata.tags,
            content_type="text/plain",
            duration_seconds=source.metadata.duration_seconds or 0,
            chunk_index=0,
            chunk_count=1,
        ),
        visibility=(ArtifactVisibility.INTERNAL,),
    )
    chunk = MediaChunkArtifact(
        chunk_artifact_id=artifact_id,
        source_id=source.source_id,
        parent_media_artifact_id=f"source_{source.source_id}",
        chunk_index=0,
        start_time=0,
        end_time=source.metadata.duration_seconds or 0,
        duration=source.metadata.duration_seconds or 0,
        status=MediaChunkingStatus.MATERIALIZED,
        path=transcript_path,
        uri=uri,
        snapshot=snapshot,
    )
    result = create_default_transcriber(provider=LocalWhisperProvider()).transcribe(
        TranscriptionRequest(
            chunk=chunk,
            config=TranscriptionConfig(
                raw_transcripts_dir=transcript_path.parent,
                provider=TranscriptionProviderKind.LOCAL_WHISPER,
                language=language,
                model_name="transcript-acquisition",
                local_transcript_path=transcript_path,
            ),
            task_id="transcript-acquisition-materialization",
        )
    )
    if not result.is_success or result.transcript is None:
        raise TranscriptAcquisitionError(f"Transcript materialization failed: {result.issues}")
    return result.transcript


def _cache_is_compatible(
    payload: object,
    request: TranscriptAcquisitionRequest,
) -> bool:
    if not isinstance(payload, dict):
        return False
    return (
        payload.get("source_id") == request.source.source_id
        and payload.get("source_uri") == request.source.location.uri
        and payload.get("goal") == request.policy.goal.value
        and payload.get("subtitle_language_preferences")
        == list(request.policy.subtitle_language_preferences)
        and payload.get("whisper_language") == request.policy.whisper_language
        and payload.get("expected_language") == request.policy.expected_language
    )


def _manifest_path(output_dir: Path) -> Path:
    return output_dir / "transcript_acquisition.json"


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = [
    "TranscriptAcquisitionCoordinator",
    "TranscriptAcquisitionError",
    "TranscriptAcquisitionGoal",
    "TranscriptAcquisitionMethod",
    "TranscriptAcquisitionPolicy",
    "TranscriptAcquisitionRequest",
    "TranscriptAcquisitionResult",
    "TranscriptValidationResult",
    "WhisperFallbackResult",
    "validate_transcript_path",
]
