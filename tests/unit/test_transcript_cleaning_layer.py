from pathlib import Path

from ai_knowledge_pipeline.core.artifact import (
    ArtifactConsumerKind,
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
    ArtifactVisibility,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.modules.cleaning.contracts import (
    ActionItem,
    AgentMemoryCandidate,
    CleaningPromptSchema,
    CleaningProviderResult,
    KeyInsight,
    MarkdownBlockKind,
    MarkdownReadyBlock,
    MarkdownReadyChapter,
    MarkdownReadyTranscript,
    TranscriptCleaningConfig,
    TranscriptCleaningErrorCode,
    TranscriptCleaningIssue,
    TranscriptCleaningRequest,
    TranscriptCleaningStatus,
    create_default_transcript_cleaner,
)
from ai_knowledge_pipeline.modules.transcription.types import (
    TranscriptArtifact,
    TranscriptSegment,
    TranscriptTimestamp,
    TranscriptionStatus,
)


def transcript_artifact(text: str = "helo wrld") -> TranscriptArtifact:
    snapshot = ArtifactSnapshot(
        artifact_id="transcript_chunk_src_1_0000",
        snapshot_id="transcript_chunk_src_1_0000_v1",
        kind=ArtifactKind.RAW_TRANSCRIPT,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/transcripts/raw/src_1/chunk_0000.json",
            path=Path("data/transcripts/raw/src_1/chunk_0000.json"),
            media_type="application/json",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(
            source_id="src_1",
            input_snapshot_ids=("chunk_src_1_0000_v1",),
            upstream_artifact_ids=("chunk_src_1_0000",),
        ),
        metadata=ArtifactMetadata(
            title="Raw Lecture",
            language="en",
            tags=("ai",),
            duration_seconds=120,
            chunk_index=0,
            chunk_count=2,
        ),
    )
    return TranscriptArtifact(
        transcript_artifact_id="transcript_chunk_src_1_0000",
        source_id="src_1",
        parent_chunk_artifact_id="chunk_src_1_0000",
        chunk_index=0,
        status=TranscriptionStatus.TRANSCRIBED,
        text=text,
        segments=(
            TranscriptSegment(
                segment_index=0,
                timestamp=TranscriptTimestamp(start_time=0, end_time=5),
                text=text,
            ),
        ),
        language="en",
        confidence=0.8,
        path=Path("data/transcripts/raw/src_1/chunk_0000.json"),
        uri="file://data/transcripts/raw/src_1/chunk_0000.json",
        snapshot=snapshot,
    )


def prompt() -> CleaningPromptSchema:
    return CleaningPromptSchema(
        system_instruction="You clean transcripts.",
        task_instruction="Correct terms and structure the transcript.",
        terminology=("RAG", "LangGraph"),
        output_requirements=("Return structured content",),
        prompt_version="cleaning-v2",
    )


def markdown_ready() -> MarkdownReadyTranscript:
    return MarkdownReadyTranscript(
        title="Clean Lecture",
        summary="A short summary.",
        cleaned_text="Hello world.",
        chapters=(
            MarkdownReadyChapter(
                chapter_index=0,
                title="Intro",
                summary="Opening ideas.",
                blocks=(
                    MarkdownReadyBlock(
                        block_index=0,
                        kind=MarkdownBlockKind.PARAGRAPH,
                        text="Hello world.",
                    ),
                ),
                start_time=0,
                end_time=120,
                semantic_tags=("rag",),
            ),
        ),
        key_insights=(KeyInsight(insight_index=0, text="RAG needs clean input."),),
        action_items=(ActionItem(action_index=0, text="Review terminology."),),
        semantic_tags=("rag", "agent-memory"),
        agent_memory_candidates=(
            AgentMemoryCandidate(
                memory_index=0,
                text="User is building an AI knowledge pipeline.",
                memory_type="project_context",
                importance=0.9,
            ),
        ),
    )


class MockCleaningProvider:
    name = "mock-cleaner"

    def clean(self, request):
        return CleaningProviderResult(
            markdown_ready=markdown_ready(),
            model_name="mock-gpt",
            prompt_version=request.prompt.prompt_version,
            language="en",
            confidence=0.93,
            metadata={"provider_request_id": "clean_req_1"},
        )


class FailingCleaningProvider:
    name = "failing-cleaner"

    def clean(self, request):
        return CleaningProviderResult(
            markdown_ready=None,
            issues=(
                TranscriptCleaningIssue(
                    code=TranscriptCleaningErrorCode.PROVIDER_FAILED,
                    message="Provider failed.",
                    field="provider",
                ),
            ),
        )


def test_cleaner_generates_markdown_ready_artifact_with_lineage() -> None:
    cleaner = create_default_transcript_cleaner(provider=MockCleaningProvider())
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
        config=TranscriptCleaningConfig(
            cleaned_transcripts_dir=Path("custom-cleaned"),
            model_name="fallback-model",
            prompt_version="fallback-prompt",
        ),
        run_id="run_1",
        job_id="job_1",
        task_id="task_clean_1",
    )

    result = cleaner.clean(request)

    assert result.is_success
    assert result.status is TranscriptCleaningStatus.CLEANED
    assert result.cleaned_transcript is not None
    cleaned = result.cleaned_transcript
    assert cleaned.markdown_ready.title == "Clean Lecture"
    assert cleaned.markdown_ready.summary == "A short summary."
    assert cleaned.markdown_ready.chapters[0].blocks[0].text == "Hello world."
    assert cleaned.confidence == 0.93
    assert cleaned.path == Path("custom-cleaned/src_1/chunk_0000.json")
    assert cleaned.snapshot.kind is ArtifactKind.CLEAN_TRANSCRIPT
    assert cleaned.snapshot.lineage.input_snapshot_ids == (
        "transcript_chunk_src_1_0000_v1",
    )
    assert cleaned.snapshot.lineage.upstream_artifact_ids == (
        "transcript_chunk_src_1_0000",
    )
    assert ArtifactVisibility.RAG_INDEXABLE in cleaned.snapshot.visibility
    assert ArtifactConsumerKind.MARKDOWN_RENDERING in (
        cleaned.snapshot.metadata.consumer_kinds
    )
    assert ArtifactConsumerKind.AGENT_MEMORY in cleaned.snapshot.metadata.consumer_kinds
    assert cleaned.snapshot.metadata.extra["chapter_count"] == 1
    assert cleaned.snapshot.metadata.extra["key_insight_count"] == 1
    assert cleaned.snapshot.metadata.extra["action_item_count"] == 1
    assert cleaned.snapshot.metadata.extra["agent_memory_candidate_count"] == 1
    assert cleaned.snapshot.metadata.extra["provider_request_id"] == "clean_req_1"
    assert cleaned.metadata["provider"] == "mock-cleaner"
    assert cleaned.metadata["prompt_version"] == "cleaning-v2"


def test_default_cleaner_requires_provider() -> None:
    result = create_default_transcript_cleaner().clean(
        TranscriptCleaningRequest(transcript=transcript_artifact(), prompt=prompt())
    )

    assert not result.is_success
    assert result.status is TranscriptCleaningStatus.FAILED
    assert result.issues[0].code is TranscriptCleaningErrorCode.PROVIDER_REQUIRED


def test_cleaner_requires_transcript_text() -> None:
    result = create_default_transcript_cleaner(provider=MockCleaningProvider()).clean(
        TranscriptCleaningRequest(transcript=transcript_artifact(text=""), prompt=prompt())
    )

    assert not result.is_success
    assert result.issues[0].code is TranscriptCleaningErrorCode.MISSING_TRANSCRIPT_TEXT


def test_provider_failure_is_structured() -> None:
    result = create_default_transcript_cleaner(provider=FailingCleaningProvider()).clean(
        TranscriptCleaningRequest(transcript=transcript_artifact(), prompt=prompt())
    )

    assert not result.is_success
    assert result.issues[0].code is TranscriptCleaningErrorCode.PROVIDER_FAILED


def test_prompt_schema_is_provider_portable() -> None:
    schema = prompt()

    assert schema.prompt_version == "cleaning-v2"
    assert "RAG" in schema.terminology
    assert schema.output_requirements == ("Return structured content",)
