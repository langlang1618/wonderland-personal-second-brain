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
from ai_knowledge_pipeline.modules.cleaning import deepseek_provider as provider_module
from ai_knowledge_pipeline.modules.cleaning.contracts import (
    CleaningPromptSchema,
    DeepSeekCleaningProvider,
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


def transcript_artifact(text: str = "这个课程讲 rag agent memory 和 obsidian") -> TranscriptArtifact:
    snapshot = ArtifactSnapshot(
        artifact_id="transcript_chunk_src_deepseek_0000",
        snapshot_id="transcript_chunk_src_deepseek_0000_v1",
        kind=ArtifactKind.RAW_TRANSCRIPT,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/transcripts/raw/src_deepseek/chunk_0000.json",
            path=Path("data/transcripts/raw/src_deepseek/chunk_0000.json"),
            media_type="application/json",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(
            source_id="src_deepseek",
            input_snapshot_ids=("chunk_src_deepseek_0000_v1",),
            upstream_artifact_ids=("chunk_src_deepseek_0000",),
        ),
        metadata=ArtifactMetadata(
            title="Raw DeepSeek Lecture",
            language="zh",
            tags=("ai",),
            duration_seconds=240,
            chunk_index=0,
            chunk_count=1,
        ),
    )
    return TranscriptArtifact(
        transcript_artifact_id="transcript_chunk_src_deepseek_0000",
        source_id="src_deepseek",
        parent_chunk_artifact_id="chunk_src_deepseek_0000",
        chunk_index=0,
        status=TranscriptionStatus.TRANSCRIBED,
        text=text,
        segments=(
            TranscriptSegment(
                segment_index=0,
                timestamp=TranscriptTimestamp(start_time=0, end_time=12),
                text=text,
            ),
        ),
        language="zh",
        confidence=0.82,
        path=Path("data/transcripts/raw/src_deepseek/chunk_0000.json"),
        uri="file://data/transcripts/raw/src_deepseek/chunk_0000.json",
        snapshot=snapshot,
    )


def prompt() -> CleaningPromptSchema:
    return CleaningPromptSchema(
        system_instruction="你是知识流水线的转录清洗器。",
        task_instruction="修复术语并输出结构化内容。",
        terminology=("RAG", "Agent Memory", "Obsidian"),
        output_requirements=("只返回 JSON",),
        style_guide="适合 Obsidian 的中文技术笔记。",
        prompt_version="cleaning-v2",
    )


def provider_payload() -> dict:
    return {
        "title": "AI Knowledge Pipeline DeepSeek Notes",
        "summary": "本节说明如何把清洗后的转录接入 Markdown 和 Obsidian。",
        "cleaned_text": "课程介绍了 RAG、Agent Memory 与 Obsidian 知识库流水线。",
        "readable_transcript_text": (
            "## 知识流水线背景\n\n"
            "这个课程讲 RAG、Agent Memory 和 Obsidian。清洗后的转录会进入 Markdown。"
        ),
        "chapters": [
            {
                "title": "知识流水线",
                "summary": "转录清洗结果会成为后续 Markdown 与 RAG 的输入。",
                "start_time": 0,
                "end_time": 240,
                "semantic_tags": ["rag", "obsidian"],
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": "清洗层负责把原始转录转换为结构化知识。",
                    }
                ],
            }
        ],
        "key_insights": [
            {
                "text": "CleaningProviderResult 是 AI provider 与 artifact materialization 的边界。",
                "confidence": 0.94,
                "tags": ["provider-boundary"],
            }
        ],
        "action_items": [
            {
                "text": "验证 DeepSeek 输出可以进入 Markdown 生成器。",
                "owner": None,
                "due": None,
            }
        ],
        "semantic_tags": ["deepseek", "rag", "obsidian"],
        "agent_memory_candidates": [
            {
                "text": "项目支持 OpenAI-compatible provider 扩展。",
                "memory_type": "architecture",
                "importance": 0.88,
                "tags": ["provider"],
            }
        ],
        "confidence": 0.91,
    }


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeDeepSeekResponse:
    id = "deepseek_resp_1"

    def __init__(self, payload: dict | str) -> None:
        content = payload if isinstance(payload, str) else json.dumps(payload)
        self.choices = (FakeChoice(content),)


class FakeChatCompletions:
    def __init__(self, payload: dict | str, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeDeepSeekResponse(self.payload)


class FakeChat:
    def __init__(self, completions: FakeChatCompletions) -> None:
        self.completions = completions


class FakeDeepSeekClient:
    def __init__(self, payload: dict | str, error: Exception | None = None) -> None:
        self.chat = FakeChat(FakeChatCompletions(payload=payload, error=error))


def test_deepseek_provider_parses_mock_chat_completion() -> None:
    client = FakeDeepSeekClient(provider_payload())
    provider = DeepSeekCleaningProvider(client=client)
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
        config=TranscriptCleaningConfig(prompt_version="cleaning-v2", language="zh"),
    )

    result = provider.clean(request)

    assert result.is_success
    assert result.markdown_ready is not None
    assert result.markdown_ready.title == "AI Knowledge Pipeline DeepSeek Notes"
    assert result.markdown_ready.chapters[0].title == "知识流水线"
    assert result.markdown_ready.readable_transcript_text.startswith("## 知识流水线背景")
    assert result.markdown_ready.key_insights[0].tags == ("provider-boundary",)
    assert result.markdown_ready.action_items[0].text.startswith("验证 DeepSeek")
    assert result.markdown_ready.semantic_tags == ("deepseek", "rag", "obsidian")
    assert result.model_name == "deepseek-v4-flash"
    assert result.prompt_version == "cleaning-v2"
    assert result.confidence == 0.91
    assert result.metadata["provider"] == "deepseek-cleaning"
    assert result.metadata["base_url"] == "https://api.deepseek.com"
    assert result.metadata["response_id"] == "deepseek_resp_1"
    call = client.chat.completions.calls[0]
    assert call["model"] == "deepseek-v4-flash"
    assert call["response_format"] == {"type": "json_object"}
    assert "这个课程讲 rag" in call["messages"][1]["content"]


def test_deepseek_provider_reads_env_defaults_from_dotenv(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            (
                "DEEPSEEK_API_KEY='from-dotenv'",
                "DEEPSEEK_BASE_URL='https://api.deepseek.com'",
                "DEEPSEEK_MODEL='deepseek-v4-flash'",
            )
        ),
        encoding="utf-8",
    )
    created_with: list[tuple[str, str]] = []
    client = FakeDeepSeekClient(provider_payload())

    def fake_create_client(api_key: str, base_url: str):
        created_with.append((api_key, base_url))
        return client

    monkeypatch.setattr(provider_module, "_create_deepseek_client", fake_create_client)
    provider = DeepSeekCleaningProvider()
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
        config=TranscriptCleaningConfig(env_path=env_path),
    )

    result = provider.clean(request)

    assert result.is_success
    assert created_with == [("from-dotenv", "https://api.deepseek.com")]
    assert client.chat.completions.calls[0]["model"] == "deepseek-v4-flash"


def test_deepseek_provider_missing_api_key_returns_structured_issue(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    provider = DeepSeekCleaningProvider()
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
        config=TranscriptCleaningConfig(env_path=tmp_path / ".env"),
    )

    result = provider.clean(request)

    assert not result.is_success
    assert result.issues[0].code is TranscriptCleaningErrorCode.MISSING_API_KEY
    assert result.issues[0].field == "DEEPSEEK_API_KEY"


def test_deepseek_provider_invalid_json_returns_parse_issue() -> None:
    provider = DeepSeekCleaningProvider(client=FakeDeepSeekClient("not json"))
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
    )

    result = provider.clean(request)

    assert not result.is_success
    assert result.issues[0].code is TranscriptCleaningErrorCode.RESPONSE_PARSE_FAILED
    assert result.issues[0].field == "response"


def test_deepseek_provider_api_error_returns_structured_issue(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-test-key")
    provider = DeepSeekCleaningProvider(
        client=FakeDeepSeekClient(
            provider_payload(),
            error=RuntimeError("request failed for secret-test-key"),
        )
    )
    request = TranscriptCleaningRequest(
        transcript=transcript_artifact(),
        prompt=prompt(),
    )

    result = provider.clean(request)

    assert not result.is_success
    assert result.issues[0].code is TranscriptCleaningErrorCode.PROVIDER_FAILED
    assert result.issues[0].field == "deepseek.chat.completions.create"
    assert "secret-test-key" not in result.issues[0].message
    assert "[redacted]" in result.issues[0].message


def test_deepseek_cleaning_output_flows_to_markdown_and_obsidian(tmp_path) -> None:
    cleaner = create_default_transcript_cleaner(
        provider=DeepSeekCleaningProvider(client=FakeDeepSeekClient(provider_payload()))
    )
    clean_result = cleaner.clean(
        TranscriptCleaningRequest(
            transcript=transcript_artifact(),
            prompt=prompt(),
            config=TranscriptCleaningConfig(
                cleaned_transcripts_dir=tmp_path / "cleaned",
                model_name="deepseek-v4-flash",
            ),
            run_id="run_deepseek",
        )
    )
    assert clean_result.is_success
    assert clean_result.cleaned_transcript is not None

    markdown_result = create_default_markdown_generator().generate(
        MarkdownGenerationRequest(
            cleaned_transcript=clean_result.cleaned_transcript,
            config=MarkdownGenerationConfig(markdown_dir=tmp_path / "markdown"),
            run_id="run_deepseek",
        )
    )
    assert markdown_result.is_success
    assert markdown_result.markdown is not None

    write_result = create_default_obsidian_writer().write(
        ObsidianWriteRequest(
            markdown=markdown_result.markdown,
            config=ObsidianWriterConfig(
                vault_path=tmp_path / "vault",
                conflict_strategy=ObsidianConflictStrategy.OVERWRITE,
            ),
            run_id="run_deepseek",
        )
    )

    assert write_result.is_success
    assert write_result.note is not None
    note_text = write_result.note.path.read_text(encoding="utf-8")
    assert "# AI Knowledge Pipeline DeepSeek Notes" in note_text
    assert "# AI整理部分" in note_text
    assert "## Summary" in note_text
    assert "## Key Insights" in note_text
    assert "## Action Items" in note_text
    assert "#deepseek #rag #obsidian" in note_text
    assert "# 可读转录" in note_text
    assert "这个课程讲 RAG、Agent Memory 和 Obsidian。" in note_text
    assert "# 原始逐字稿" in note_text
    assert "这个课程讲 rag agent memory 和 obsidian" in note_text
    assert write_result.note.snapshot.lineage.upstream_artifact_ids == (
        markdown_result.markdown.markdown_artifact_id,
    )
