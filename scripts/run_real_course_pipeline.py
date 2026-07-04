"""Run a real local course transcript through the knowledge pipeline."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

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
from ai_knowledge_pipeline.infra.runtime_logging import (
    STAGE_DEEPSEEK_CLEANING,
    STAGE_MARKDOWN_GENERATION,
    STAGE_PROFILE_LOADING,
    STAGE_SAVE_OUTPUT,
    RuntimeLogger,
    create_runtime_logger,
)
from ai_knowledge_pipeline.modules.chunking import (
    MediaChunkArtifact,
    MediaChunkingStatus,
)
from ai_knowledge_pipeline.modules.cleaning import (
    CleanedTranscriptArtifact,
    CleaningPromptSchema,
    DeepSeekCleaningProvider,
    KnowledgeProfileName,
    TranscriptCleaningConfig,
    TranscriptCleaningProvider,
    TranscriptCleaningRequest,
    compose_cleaning_prompt,
    create_default_transcript_cleaner,
    load_knowledge_profile,
)
from ai_knowledge_pipeline.modules.markdown import (
    MarkdownArtifact,
    MarkdownGenerationConfig,
    MarkdownGenerationRequest,
    create_default_markdown_generator,
)
from ai_knowledge_pipeline.modules.obsidian import (
    ObsidianConflictStrategy,
    ObsidianNoteArtifact,
    ObsidianWriteRequest,
    ObsidianWriterConfig,
    create_default_obsidian_writer,
)
from ai_knowledge_pipeline.modules.transcription import (
    LocalWhisperProvider,
    TranscriptArtifact,
    TranscriptionConfig,
    TranscriptionProviderKind,
    TranscriptionRequest,
    create_default_transcriber,
)


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True, slots=True)
class RealCoursePipelineRequest:
    """Input for processing one real local course transcript."""

    local_transcript_path: Path
    obsidian_vault_path: Path
    local_audio_path: Path | None = None
    title: str | None = None
    tags: tuple[str, ...] = ()
    model: str = DEFAULT_DEEPSEEK_MODEL
    profile: KnowledgeProfileName = KnowledgeProfileName.AI
    custom_profile_path: Path | None = None
    env_path: Path = Path(".env")
    run_id: str = "real-course-run"
    job_id: str = "real-course-job"


@dataclass(frozen=True, slots=True)
class RealCoursePipelineArtifacts:
    """Artifacts produced by the real course runner."""

    chunk: MediaChunkArtifact
    transcript: TranscriptArtifact
    cleaned_transcript: CleanedTranscriptArtifact
    markdown: MarkdownArtifact
    obsidian_note: ObsidianNoteArtifact


@dataclass(frozen=True, slots=True)
class RealCoursePipelineResult:
    """Output of the real course runner."""

    artifacts: RealCoursePipelineArtifacts
    obsidian_note_path: Path


class RealCoursePipelineError(RuntimeError):
    """Raised when the real course runner cannot complete."""


def run_real_course_pipeline(
    request: RealCoursePipelineRequest,
    cleaning_provider: TranscriptCleaningProvider | None = None,
    logger: RuntimeLogger | None = None,
) -> RealCoursePipelineResult:
    """Run one local transcript through cleaning, Markdown, and Obsidian."""

    runtime_logger = logger or create_runtime_logger()
    _validate_request(request, require_api_key=cleaning_provider is None)
    chunk = _create_transcript_backed_chunk(request)
    transcript = _import_local_transcript(request, chunk)
    cleaned = _clean_transcript(request, transcript, cleaning_provider, runtime_logger)
    with runtime_logger.stage(STAGE_MARKDOWN_GENERATION):
        markdown = _generate_markdown(request, cleaned)
    with runtime_logger.stage(STAGE_SAVE_OUTPUT):
        note = _write_obsidian_note(request, markdown)
    artifacts = RealCoursePipelineArtifacts(
        chunk=chunk,
        transcript=transcript,
        cleaned_transcript=cleaned,
        markdown=markdown,
        obsidian_note=note,
    )
    return RealCoursePipelineResult(
        artifacts=artifacts,
        obsidian_note_path=note.path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for the real course pipeline runner."""

    args = _parse_args(argv)
    env_values = _read_env_file(Path(".env"))
    vault = args.vault or _load_value("OBSIDIAN_VAULT_PATH", env_values)
    model = args.model or _load_value("DEEPSEEK_MODEL", env_values) or DEFAULT_DEEPSEEK_MODEL

    if vault is None:
        print(
            "Error: Obsidian vault path is required. Pass --vault or set OBSIDIAN_VAULT_PATH.",
            file=sys.stderr,
        )
        return 2

    request = RealCoursePipelineRequest(
        local_transcript_path=Path(args.transcript),
        local_audio_path=Path(args.audio) if args.audio else None,
        obsidian_vault_path=Path(vault),
        title=args.title,
        tags=_parse_tags(args.tags),
        model=model,
        profile=KnowledgeProfileName(args.profile),
        custom_profile_path=Path(args.profile_path) if args.profile_path else None,
    )
    try:
        result = run_real_course_pipeline(request)
    except RealCoursePipelineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(result.obsidian_note_path)
    return 0


def _validate_request(
    request: RealCoursePipelineRequest,
    *,
    require_api_key: bool,
) -> None:
    if not request.local_transcript_path.exists():
        raise RealCoursePipelineError(
            f"Transcript file does not exist: {request.local_transcript_path}"
        )
    if request.local_transcript_path.suffix.lower() not in {".txt", ".srt"}:
        raise RealCoursePipelineError("Transcript must be a .txt or .srt file.")
    if request.local_audio_path is not None and not request.local_audio_path.exists():
        raise RealCoursePipelineError(
            f"Audio file does not exist: {request.local_audio_path}"
        )
    if not request.obsidian_vault_path.exists() or not request.obsidian_vault_path.is_dir():
        raise RealCoursePipelineError(
            f"Obsidian vault path does not exist: {request.obsidian_vault_path}"
        )

    if require_api_key:
        env_values = _read_env_file(request.env_path)
        if not _load_value("DEEPSEEK_API_KEY", env_values):
            raise RealCoursePipelineError(
                "Missing DEEPSEEK_API_KEY. Add it to .env or the process environment."
            )


def _create_transcript_backed_chunk(
    request: RealCoursePipelineRequest,
) -> MediaChunkArtifact:
    title = request.title or request.local_transcript_path.stem
    source_id = f"course_{_slugify(title)}"
    artifact_id = f"chunk_{source_id}_0000"
    snapshot_id = f"{artifact_id}_v1"
    chunk_path = request.local_audio_path or request.local_transcript_path
    uri = chunk_path.as_uri() if chunk_path.is_absolute() else f"file://{chunk_path}"
    tags = request.tags or ("course",)

    snapshot = ArtifactSnapshot(
        artifact_id=artifact_id,
        snapshot_id=snapshot_id,
        kind=ArtifactKind.CHUNK,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri=uri,
            path=chunk_path,
            media_type="audio/*" if request.local_audio_path else "text/plain",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(
            source_id=source_id,
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="real-course-transcript-import",
            stage_id="transcription",
        ),
        integrity=ArtifactIntegrity(algorithm=IntegrityAlgorithm.NONE),
        metadata=ArtifactMetadata(
            title=title,
            tags=tags,
            content_type="audio/*" if request.local_audio_path else "text/plain",
            duration_seconds=0,
            chunk_index=0,
            chunk_count=1,
            consumer_kinds=(),
            extra={
                "local_transcript_path": str(request.local_transcript_path),
                "local_audio_path": str(request.local_audio_path)
                if request.local_audio_path
                else "",
            },
        ),
        visibility=(ArtifactVisibility.INTERNAL,),
    )
    return MediaChunkArtifact(
        chunk_artifact_id=artifact_id,
        source_id=source_id,
        parent_media_artifact_id=f"local_media_{source_id}",
        chunk_index=0,
        start_time=0,
        end_time=0,
        duration=0,
        status=MediaChunkingStatus.MATERIALIZED,
        path=chunk_path,
        uri=uri,
        snapshot=snapshot,
        metadata={"runner": "real-course"},
    )


def _import_local_transcript(
    request: RealCoursePipelineRequest,
    chunk: MediaChunkArtifact,
) -> TranscriptArtifact:
    result = create_default_transcriber(provider=LocalWhisperProvider()).transcribe(
        TranscriptionRequest(
            chunk=chunk,
            config=TranscriptionConfig(
                provider=TranscriptionProviderKind.LOCAL_WHISPER,
                language=None,
                model_name="local-whisper-import",
                local_transcript_path=request.local_transcript_path,
            ),
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="real-course-transcription",
        )
    )
    if not result.is_success or result.transcript is None:
        raise RealCoursePipelineError(f"Transcript import failed: {result.issues}")
    return result.transcript


def _clean_transcript(
    request: RealCoursePipelineRequest,
    transcript: TranscriptArtifact,
    cleaning_provider: TranscriptCleaningProvider | None,
    logger: RuntimeLogger,
) -> CleanedTranscriptArtifact:
    provider = cleaning_provider or DeepSeekCleaningProvider(model=request.model)
    title_hint = f"Use this title if it fits the content: {request.title}." if request.title else ""
    prompt = CleaningPromptSchema(
        system_instruction="You clean real course transcripts for a local knowledge pipeline.",
        task_instruction=(
            "Repair transcription errors, remove spoken filler, structure the course "
            f"as an Obsidian-ready knowledge note. {title_hint}"
        ).strip(),
        terminology=("RAG", "Agent Memory", "Obsidian", "AI Knowledge Pipeline"),
        output_requirements=(
            "title",
            "summary",
            "chapters",
            "key insights",
            "action items",
            "semantic tags",
            "agent memory candidates",
        ),
        style_guide="Clear, structured course notes for long-term review.",
        prompt_version="real-course-cleaning-v1",
    )
    with logger.stage(STAGE_PROFILE_LOADING):
        try:
            profile = load_knowledge_profile(
                request.profile,
                custom_profile_path=request.custom_profile_path,
            )
        except ValueError as exc:
            raise RealCoursePipelineError(str(exc)) from exc
    prompt = compose_cleaning_prompt(prompt, profile)
    with logger.stage(STAGE_DEEPSEEK_CLEANING):
        result = create_default_transcript_cleaner(provider=provider).clean(
            TranscriptCleaningRequest(
                transcript=transcript,
                prompt=prompt,
                config=TranscriptCleaningConfig(
                    model_name=request.model,
                    prompt_version=prompt.prompt_version,
                    env_path=request.env_path,
                ),
                run_id=request.run_id,
                job_id=request.job_id,
                task_id="real-course-cleaning",
            )
        )
    if not result.is_success or result.cleaned_transcript is None:
        raise RealCoursePipelineError(f"Transcript cleaning failed: {result.issues}")
    return result.cleaned_transcript


def _generate_markdown(
    request: RealCoursePipelineRequest,
    cleaned: CleanedTranscriptArtifact,
) -> MarkdownArtifact:
    result = create_default_markdown_generator().generate(
        MarkdownGenerationRequest(
            cleaned_transcript=cleaned,
            config=MarkdownGenerationConfig(),
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="real-course-markdown",
        )
    )
    if not result.is_success or result.markdown is None:
        raise RealCoursePipelineError(f"Markdown generation failed: {result.issues}")
    return result.markdown


def _write_obsidian_note(
    request: RealCoursePipelineRequest,
    markdown: MarkdownArtifact,
) -> ObsidianNoteArtifact:
    result = create_default_obsidian_writer().write(
        ObsidianWriteRequest(
            markdown=markdown,
            config=ObsidianWriterConfig(
                vault_path=request.obsidian_vault_path,
                conflict_strategy=ObsidianConflictStrategy.VERSIONED,
            ),
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="real-course-obsidian",
        )
    )
    if not result.is_success or result.note is None:
        raise RealCoursePipelineError(f"Obsidian writing failed: {result.issues}")
    return result.note


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one local course transcript through the AI knowledge pipeline.",
    )
    parser.add_argument("--transcript", required=True, help="Path to .txt or .srt transcript.")
    parser.add_argument("--audio", help="Optional local audio file path.")
    parser.add_argument("--vault", help="Obsidian vault path. Falls back to OBSIDIAN_VAULT_PATH.")
    parser.add_argument("--title", help="Optional course title hint.")
    parser.add_argument("--tags", help="Comma-separated note tags.")
    parser.add_argument("--model", help="DeepSeek model. Defaults to DEEPSEEK_MODEL.")
    parser.add_argument(
        "--profile",
        choices=tuple(profile.value for profile in KnowledgeProfileName),
        default=KnowledgeProfileName.AI.value,
        help="Knowledge profile used to compose the cleaning prompt.",
    )
    parser.add_argument(
        "--profile-path",
        help="Custom Markdown prompt path. Required when --profile custom is used.",
    )
    return parser.parse_args(argv)


def _parse_tags(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(tag.strip().lstrip("#") for tag in value.split(",") if tag.strip())


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_value(env_var: str, env_values: dict[str, str]) -> str | None:
    return os.environ.get(env_var) or env_values.get(env_var)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return slug.lower() or "untitled"


if __name__ == "__main__":
    raise SystemExit(main())
