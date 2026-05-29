"""Mock providers used only by the end-to-end demo pipeline."""

from __future__ import annotations

from ai_knowledge_pipeline.modules.cleaning.types import (
    ActionItem,
    AgentMemoryCandidate,
    CleaningProviderResult,
    KeyInsight,
    MarkdownBlockKind,
    MarkdownReadyBlock,
    MarkdownReadyChapter,
    MarkdownReadyTranscript,
    TranscriptCleaningRequest,
)
from ai_knowledge_pipeline.modules.transcription.types import (
    ProviderTranscriptionResult,
    TranscriptSegment,
    TranscriptTimestamp,
    TranscriptionRequest,
)


class DemoTranscriptionProvider:
    """Deterministic transcription provider for local demos and tests."""

    name = "demo-transcription-provider"

    def transcribe(
        self,
        request: TranscriptionRequest,
    ) -> ProviderTranscriptionResult:
        chunk = request.chunk
        text = (
            "This local demo transcript explains how an AI knowledge pipeline "
            "turns audio into structured notes for Obsidian."
        )
        return ProviderTranscriptionResult(
            text=text,
            language=request.config.language or "en",
            confidence=0.99,
            model_name="demo-whisper",
            segments=(
                TranscriptSegment(
                    segment_index=0,
                    timestamp=TranscriptTimestamp(
                        start_time=chunk.start_time,
                        end_time=min(chunk.start_time + 5, chunk.end_time),
                    ),
                    text="This local demo transcript explains how an AI knowledge pipeline works.",
                    confidence=0.99,
                ),
                TranscriptSegment(
                    segment_index=1,
                    timestamp=TranscriptTimestamp(
                        start_time=min(chunk.start_time + 5, chunk.end_time),
                        end_time=chunk.end_time,
                    ),
                    text="It produces structured notes for Obsidian.",
                    confidence=0.98,
                ),
            ),
            metadata={"demo": True},
        )


class DemoCleaningProvider:
    """Deterministic cleaning provider for local demos and tests."""

    name = "demo-cleaning-provider"

    def clean(self, request: TranscriptCleaningRequest) -> CleaningProviderResult:
        transcript = request.transcript
        title = "AI Knowledge Pipeline Demo"
        summary = (
            "A local demo showing how audio flows through source detection, "
            "media artifacts, transcription, cleaning, Markdown generation, "
            "and Obsidian writing."
        )
        markdown_ready = MarkdownReadyTranscript(
            title=title,
            summary=summary,
            cleaned_text=(
                "The demo pipeline converts a local audio path into an "
                "Obsidian-ready Markdown note without calling external services."
            ),
            chapters=(
                MarkdownReadyChapter(
                    chapter_index=0,
                    title="Pipeline Flow",
                    summary="The local audio file is transformed through each artifact layer.",
                    start_time=transcript.segments[0].timestamp.start_time
                    if transcript.segments
                    else None,
                    end_time=transcript.segments[-1].timestamp.end_time
                    if transcript.segments
                    else None,
                    semantic_tags=("pipeline", "obsidian"),
                    blocks=(
                        MarkdownReadyBlock(
                            block_index=0,
                            kind=MarkdownBlockKind.PARAGRAPH,
                            text=(
                                "The pipeline keeps every stage modular and "
                                "preserves artifact lineage from source to note."
                            ),
                        ),
                    ),
                ),
            ),
            key_insights=(
                KeyInsight(
                    insight_index=0,
                    text="Artifact lineage makes the generated note auditable.",
                    tags=("lineage",),
                ),
                KeyInsight(
                    insight_index=1,
                    text="Mock providers allow local demos without network or AI APIs.",
                    tags=("local-first",),
                ),
            ),
            action_items=(
                ActionItem(
                    action_index=0,
                    text="Replace demo providers with real providers when ready.",
                ),
            ),
            semantic_tags=("ai-pipeline", "obsidian", "demo"),
            agent_memory_candidates=(
                AgentMemoryCandidate(
                    memory_index=0,
                    text="The project has a working local demo pipeline.",
                    memory_type="project_status",
                    importance=0.8,
                    tags=("demo", "pipeline"),
                ),
            ),
        )
        return CleaningProviderResult(
            markdown_ready=markdown_ready,
            model_name="demo-cleaner",
            prompt_version=request.prompt.prompt_version,
            language=transcript.language or "en",
            confidence=0.99,
            metadata={"demo": True},
        )


__all__ = ["DemoCleaningProvider", "DemoTranscriptionProvider"]
