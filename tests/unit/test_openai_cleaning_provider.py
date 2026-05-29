import json
from pathlib import Path

from ai_knowledge_pipeline.core.artifact import (
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.modules.cleaning import openai_provider as provider_module
from ai_knowledge_pipeline.modules.cleaning.contracts import (
    CleaningPromptSchema,
    OpenAICleaningProvider,
    TranscriptCleaningConfig,
    TranscriptCleaningErrorCode,
    TranscriptCleaningRequest,
    create_default_transcript_cleaner,
)
from ai_knowledge_pipeline.modules.markdown.contracts import (
    MarkdownGenerationConfig,
    MarkdownGenerationRequest,
    create_default_markdown_generator,
)
from ai_knowledge_pipeline.modules.obsidian.contracts import (
    ObsidianConflictStrategy,
    ObsidianWriteRequest,
    ObsidianWriterConfig,
    create_default_obsidian_writer,
)
from ai_knowledge_pipeline.modules.transcription.types import (
    TranscriptArtifact,
    TranscriptSegment,
    TranscriptTimestamp,
    TranscriptionStatus,
)


def transcript_artifact(text: str = "helo wrld this is about rag and agent memory") -> TranscriptArtifact:
    snapshot = ArtifactSnapshot(
        artifact_id="transcript_chunk_src_openai_0000",
        snapshot_id="transcript_chunk_src_openai_0000_v1",
        kind=ArtifactKind.RAW_TRANSCRIPT,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/transcripts/raw/src_openai/chunk_0000.json",
            path=Path("data/transcripts/raw/src_openai/chunk_0000.json"),
            media_type="application/json",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(
            source_id="src_openai",
            input_snapshot_ids=("chunk_src_openai_0000_v1",),
            upstream_artifact_ids=("chunk_src_openai_0000",),
        ),
        metadata=ArtifactMetadata(
            title="Raw OpenAI Lecture",
            language="en",
            tags=("ai",),
            duration_seconds=180,
            chunk_index=0,
            chunk_count=1,
        ),
    )
    return TranscriptArtifact(
        transcript_artifact_id="transcript_chunk_src_openai_0000",
        source_id="src_openai",
        parent_chunk_artifact_id="chunk_src_openai_0000",
        chunk_index=0,
        status=TranscriptionStatus.TRANSCRIBED,
        text=text,
        segments=(
            TranscriptSegment(
                segment_index=0,
                timestamp=TranscriptTimestamp(start_time=0, end_time=10),
                text=text,
            ),
        ),
        language="en",
        confidence=0.8,
        path=Path("data/transcripts/raw/src_openai/chunk_0000.json"),
        uri="file://data/transcripts/raw/src_openai/chunk_0000.json",
        snapshot=snapshot,
    )


def prompt() -> CleaningPromptSchema:
    return CleaningPromptSchema(
        system_instruction="You clean transcripts for a knowledge pipeline.",
        task_instruction="Repair terms and return structured Markdown-ready content.",
        terminology=("RAG", "Agent Memory", "LangGraph"),
        output_requirements=("Return valid JSON only",),
        style_guide="Concise technical notes for Obsidian.",
        prompt_version="cleaning-v2",
    )


def provider_payload() -> dict:
    return {
        "title": "AI Knowledge Pipeline Foundations",
        "summary": "A cleaned summary of RAG and agent memory pipeline ideas.",
        "cleaned_text": (
            "Hello world. This lesson explains how clean transcripts support "
            "RAG, Markdown generation, and agent memory."
        ),
        "chapters": [
            {
                "title": "Pipeline Overview",
                "summary": "The source transcript is converted into durable artifacts.",
                "start_time": 0,
                "end_time": 180,
                "semantic_tags": ["rag", "agent-memory"],
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": "Clean transcripts become reusable knowledge assets.",
                    },
                    {
                        "kind": "bullet_list",
                        "text": "Normalize sources\nPreserve lineage\nGenerate notes",
                    },
                ],
            }
        ],
        "key_insights": [
            {
                "text": "Clean transcript artifacts are the bridge between raw media and RAG.",
                "confidence": 0.95,
                "tags": ["rag"],
            }
        ],
        "action_items": [
            {
                "text": "Review terminology before publishing the note.",
                "owner": "team",
                "due": "later",
            }
        ],
        "semantic_tags": ["rag", "obsidian", "agent-memory"],
        "agent_memory_candidates": [
            {
                "text": "The project treats cleaned transcripts as reusable memory inputs.",
                "memory_type": "project_context",
                "importance": 0.9,
                "tags": ["memory"],
            }
        ],
        "confidence": 0.92,
    }


class FakeOpenAIResponse:
    id = "resp_test_1"

    def __init__(self, payload: dict | str) -> None:
        self.output_text = payload if isinstance(payload, str) else json.dumps(payload)


class FakeResponsesEndpoint:
    def __init__(self, payload: dict | str) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeOpenAIResponse(self.payload)


class FakeOpenAIClient:
    def __init__(self, payload: dict | str) -> None:
        self.responses = FakeResponsesEndpoint(payload)


def test_openai_provider_parses_mock_responses_output() -> None:
    client = FakeOpenAIClient(provider_payload())
    provider = OpenAICleaningProvider(client=client)
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
        config=TranscriptCleaningConfig(
            model_name="gpt-5-mini",
            prompt_version="cleaning-v2",
            language="en",
        ),
    )

    result = provider.clean(request)

    assert result.is_success
    assert result.markdown_ready is not None
    assert result.markdown_ready.title == "AI Knowledge Pipeline Foundations"
    assert result.markdown_ready.summary.startswith("A cleaned summary")
    assert result.markdown_ready.chapters[0].title == "Pipeline Overview"
    assert result.markdown_ready.chapters[0].blocks[1].text.startswith("Normalize")
    assert result.markdown_ready.key_insights[0].tags == ("rag",)
    assert result.markdown_ready.action_items[0].owner == "team"
    assert result.markdown_ready.semantic_tags == ("rag", "obsidian", "agent-memory")
    assert result.markdown_ready.agent_memory_candidates[0].memory_type == "project_context"
    assert result.model_name == "gpt-5-mini"
    assert result.prompt_version == "cleaning-v2"
    assert result.confidence == 0.92
    assert result.metadata["provider"] == "openai-cleaning"
    assert result.metadata["response_id"] == "resp_test_1"
    assert client.responses.calls[0]["model"] == "gpt-5-mini"
    assert "Return valid JSON only" in client.responses.calls[0]["input"][1]["content"]
    assert "helo wrld" in client.responses.calls[0]["input"][1]["content"]


def test_openai_provider_missing_api_key_returns_structured_issue(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAICleaningProvider()
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
        config=TranscriptCleaningConfig(env_path=tmp_path / ".env"),
    )

    result = provider.clean(request)

    assert not result.is_success
    assert result.issues[0].code is TranscriptCleaningErrorCode.MISSING_API_KEY
    assert result.issues[0].field == "config.api_key_env_var"


def test_openai_provider_reads_api_key_from_dotenv(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY='from-dotenv'\n", encoding="utf-8")
    created_with: list[str] = []
    client = FakeOpenAIClient(provider_payload())

    def fake_create_client(api_key: str):
        created_with.append(api_key)
        return client

    monkeypatch.setattr(provider_module, "_create_openai_client", fake_create_client)
    provider = OpenAICleaningProvider()
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
        config=TranscriptCleaningConfig(env_path=env_path),
    )

    result = provider.clean(request)

    assert result.is_success
    assert created_with == ["from-dotenv"]


def test_openai_provider_invalid_json_returns_parse_issue() -> None:
    provider = OpenAICleaningProvider(client=FakeOpenAIClient("not json"))
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
    )

    result = provider.clean(request)

    assert not result.is_success
    assert result.issues[0].code is TranscriptCleaningErrorCode.RESPONSE_PARSE_FAILED
    assert result.issues[0].field == "response"


def test_openai_cleaning_output_flows_to_markdown_and_obsidian(tmp_path) -> None:
    cleaner = create_default_transcript_cleaner(
        provider=OpenAICleaningProvider(client=FakeOpenAIClient(provider_payload()))
    )
    clean_result = cleaner.clean(
        TranscriptCleaningRequest(
            transcript=transcript_artifact(),
            prompt=prompt(),
            config=TranscriptCleaningConfig(
                cleaned_transcripts_dir=tmp_path / "cleaned",
                model_name="gpt-5-mini",
            ),
            run_id="run_openai",
        )
    )
    assert clean_result.is_success
    assert clean_result.cleaned_transcript is not None

    markdown_result = create_default_markdown_generator().generate(
        MarkdownGenerationRequest(
            cleaned_transcript=clean_result.cleaned_transcript,
            config=MarkdownGenerationConfig(markdown_dir=tmp_path / "markdown"),
            run_id="run_openai",
        )
    )
    assert markdown_result.is_success
    assert markdown_result.markdown is not None

    vault_path = tmp_path / "vault"
    write_result = create_default_obsidian_writer().write(
        ObsidianWriteRequest(
            markdown=markdown_result.markdown,
            config=ObsidianWriterConfig(
                vault_path=vault_path,
                conflict_strategy=ObsidianConflictStrategy.OVERWRITE,
            ),
            run_id="run_openai",
        )
    )

    assert write_result.is_success
    assert write_result.note is not None
    note_text = write_result.note.path.read_text(encoding="utf-8")
    assert "# AI Knowledge Pipeline Foundations" in note_text
    assert "## Summary" in note_text
    assert "## Key Insights" in note_text
    assert "## Action Items" in note_text
    assert "#rag #obsidian #agent-memory" in note_text
    assert write_result.note.snapshot.lineage.upstream_artifact_ids == (
        markdown_result.markdown.markdown_artifact_id,
    )
