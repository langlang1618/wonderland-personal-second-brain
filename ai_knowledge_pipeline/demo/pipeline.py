"""End-to-end local demo pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_knowledge_pipeline.core.source import SourceData, SourceModelConfig
from ai_knowledge_pipeline.demo.providers import (
    DemoCleaningProvider,
    DemoTranscriptionProvider,
)
from ai_knowledge_pipeline.modules.chunking import (
    MediaChunkArtifact,
    MediaChunkingConfig,
    MediaChunkingMode,
    MediaChunkingRequest,
    create_default_media_chunker,
)
from ai_knowledge_pipeline.modules.cleaning import (
    CleanedTranscriptArtifact,
    CleaningPromptSchema,
    TranscriptCleaningConfig,
    TranscriptCleaningRequest,
    create_default_transcript_cleaner,
)
from ai_knowledge_pipeline.modules.download import (
    LocalMediaArtifact,
    MediaDownloadConfig,
    MediaDownloadRequest,
    create_default_media_downloader,
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
from ai_knowledge_pipeline.modules.sources import (
    SourceParseContext,
    create_default_sources_normalizer,
)
from ai_knowledge_pipeline.modules.transcription import (
    LocalWhisperProvider,
    TranscriptArtifact,
    TranscriptionConfig,
    TranscriptionProviderKind,
    TranscriptionRequest,
    create_default_transcriber,
)


@dataclass(frozen=True, slots=True)
class DemoPipelineRequest:
    """Input for the local audio demo pipeline."""

    local_audio_path: Path
    temp_vault_path: Path
    local_transcript_path: Path | None = None
    media_duration_seconds: float = 120
    chunk_duration_seconds: float = 120
    run_id: str = "demo-run"
    job_id: str = "demo-job"
    conflict_strategy: ObsidianConflictStrategy = (
        ObsidianConflictStrategy.VERSIONED
    )


@dataclass(frozen=True, slots=True)
class DemoPipelineArtifacts:
    """All artifacts produced by the demo pipeline."""

    source: SourceData
    media: LocalMediaArtifact
    chunk: MediaChunkArtifact
    transcript: TranscriptArtifact
    cleaned_transcript: CleanedTranscriptArtifact
    markdown: MarkdownArtifact
    obsidian_note: ObsidianNoteArtifact


@dataclass(frozen=True, slots=True)
class DemoPipelineResult:
    """Output of the local audio demo pipeline."""

    artifacts: DemoPipelineArtifacts
    obsidian_note_path: Path
    lineage_chain: tuple[str, ...]


def run_local_audio_demo_pipeline(
    request: DemoPipelineRequest,
) -> DemoPipelineResult:
    """Run the local demo pipeline from audio path to Obsidian note."""

    source = _normalize_source(request)
    media = _download_local_reference(request, source)
    chunk = _chunk_media(request, media)
    transcript = _transcribe_chunk(request, chunk)
    cleaned = _clean_transcript(request, transcript)
    markdown = _generate_markdown(request, cleaned)
    note = _write_obsidian_note(request, markdown)
    artifacts = DemoPipelineArtifacts(
        source=source,
        media=media,
        chunk=chunk,
        transcript=transcript,
        cleaned_transcript=cleaned,
        markdown=markdown,
        obsidian_note=note,
    )
    lineage_chain = _lineage_chain(artifacts)
    return DemoPipelineResult(
        artifacts=artifacts,
        obsidian_note_path=note.path,
        lineage_chain=lineage_chain,
    )


def run_local_whisper_demo_pipeline(
    local_audio_path: Path,
    local_transcript_path: Path,
    temp_vault_path: Path,
) -> DemoPipelineResult:
    """Run the demo pipeline using a local Whisper transcript export."""

    return run_local_audio_demo_pipeline(
        DemoPipelineRequest(
            local_audio_path=local_audio_path,
            local_transcript_path=local_transcript_path,
            temp_vault_path=temp_vault_path,
        )
    )


def _normalize_source(request: DemoPipelineRequest) -> SourceData:
    normalizer = create_default_sources_normalizer()
    result = normalizer.normalize(
        str(request.local_audio_path),
        SourceParseContext(
            config=SourceModelConfig(default_tags=("demo", "local-audio")),
            config_profile="demo",
        ),
    )
    if not result.is_success or result.source is None:
        raise RuntimeError(f"Source normalization failed: {result.issues}")
    return result.source


def _download_local_reference(
    request: DemoPipelineRequest,
    source: SourceData,
) -> LocalMediaArtifact:
    result = create_default_media_downloader().download(
        MediaDownloadRequest(
            source=source,
            config=MediaDownloadConfig(keep_original_local_path=True),
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="demo-download",
        )
    )
    if not result.is_success or result.artifact is None:
        raise RuntimeError(f"Media download failed: {result.issues}")
    return result.artifact


def _chunk_media(
    request: DemoPipelineRequest,
    media: LocalMediaArtifact,
) -> MediaChunkArtifact:
    result = create_default_media_chunker().chunk(
        MediaChunkingRequest(
            media=media,
            media_duration_seconds=request.media_duration_seconds,
            config=MediaChunkingConfig(
                mode=MediaChunkingMode.DRY_RUN,
                chunk_duration_seconds=request.chunk_duration_seconds,
            ),
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="demo-chunking",
        )
    )
    if not result.is_success or not result.chunks:
        raise RuntimeError(f"Media chunking failed: {result.issues}")
    return result.chunks[0]


def _transcribe_chunk(
    request: DemoPipelineRequest,
    chunk: MediaChunkArtifact,
) -> TranscriptArtifact:
    provider = (
        LocalWhisperProvider()
        if request.local_transcript_path is not None
        else DemoTranscriptionProvider()
    )
    provider_kind = (
        TranscriptionProviderKind.LOCAL_WHISPER
        if request.local_transcript_path is not None
        else TranscriptionProviderKind.MOCK
    )
    result = create_default_transcriber(provider=provider).transcribe(
        TranscriptionRequest(
            chunk=chunk,
            config=TranscriptionConfig(
                language="en",
                model_name="local-whisper-import"
                if request.local_transcript_path is not None
                else "demo-whisper",
                provider=provider_kind,
                local_transcript_path=request.local_transcript_path,
            ),
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="demo-transcription",
        )
    )
    if not result.is_success or result.transcript is None:
        raise RuntimeError(f"Transcription failed: {result.issues}")
    return result.transcript


def _clean_transcript(
    request: DemoPipelineRequest,
    transcript: TranscriptArtifact,
) -> CleanedTranscriptArtifact:
    prompt = CleaningPromptSchema(
        system_instruction="You clean transcripts for a local demo.",
        task_instruction="Return Markdown-ready structured knowledge.",
        terminology=("AI Knowledge Pipeline", "Obsidian", "artifact lineage"),
        output_requirements=(
            "title",
            "summary",
            "chapters",
            "key insights",
            "action items",
            "semantic tags",
        ),
        prompt_version="demo-cleaning-v1",
    )
    result = create_default_transcript_cleaner(provider=DemoCleaningProvider()).clean(
        TranscriptCleaningRequest(
            transcript=transcript,
            prompt=prompt,
            config=TranscriptCleaningConfig(
                language="en",
                model_name="demo-cleaner",
                prompt_version=prompt.prompt_version,
            ),
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="demo-cleaning",
        )
    )
    if not result.is_success or result.cleaned_transcript is None:
        raise RuntimeError(f"Transcript cleaning failed: {result.issues}")
    return result.cleaned_transcript


def _generate_markdown(
    request: DemoPipelineRequest,
    cleaned: CleanedTranscriptArtifact,
) -> MarkdownArtifact:
    result = create_default_markdown_generator().generate(
        MarkdownGenerationRequest(
            cleaned_transcript=cleaned,
            config=MarkdownGenerationConfig(),
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="demo-markdown",
        )
    )
    if not result.is_success or result.markdown is None:
        raise RuntimeError(f"Markdown generation failed: {result.issues}")
    return result.markdown


def _write_obsidian_note(
    request: DemoPipelineRequest,
    markdown: MarkdownArtifact,
) -> ObsidianNoteArtifact:
    result = create_default_obsidian_writer().write(
        ObsidianWriteRequest(
            markdown=markdown,
            config=ObsidianWriterConfig(
                vault_path=request.temp_vault_path,
                conflict_strategy=request.conflict_strategy,
            ),
            run_id=request.run_id,
            job_id=request.job_id,
            task_id="demo-obsidian",
        )
    )
    if not result.is_success or result.note is None:
        raise RuntimeError(f"Obsidian writing failed: {result.issues}")
    return result.note


def _lineage_chain(artifacts: DemoPipelineArtifacts) -> tuple[str, ...]:
    return (
        artifacts.obsidian_note.snapshot.snapshot_id,
        artifacts.markdown.snapshot.snapshot_id,
        artifacts.cleaned_transcript.snapshot.snapshot_id,
        artifacts.transcript.snapshot.snapshot_id,
        artifacts.chunk.snapshot.snapshot_id,
        artifacts.media.snapshot.snapshot_id,
        artifacts.source.source_id,
    )


__all__ = [
    "DemoPipelineArtifacts",
    "DemoPipelineRequest",
    "DemoPipelineResult",
    "run_local_audio_demo_pipeline",
    "run_local_whisper_demo_pipeline",
]
