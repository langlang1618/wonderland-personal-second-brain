from pathlib import Path

from ai_knowledge_pipeline.modules.cleaning import (
    ActionItem,
    AgentMemoryCandidate,
    CleaningProviderResult,
    KnowledgeProfileName,
    KeyInsight,
    MarkdownBlockKind,
    MarkdownReadyBlock,
    MarkdownReadyChapter,
    MarkdownReadyTranscript,
    TranscriptCleaningErrorCode,
    TranscriptCleaningIssue,
)
from scripts.run_real_course_pipeline import (
    RealCoursePipelineError,
    RealCoursePipelineRequest,
    main,
    run_real_course_pipeline,
)


class MockDeepSeekProvider:
    name = "mock-deepseek"

    def clean(self, request):
        return CleaningProviderResult(
            markdown_ready=MarkdownReadyTranscript(
                title="第一节真实课程",
                summary="这是第一节课程的结构化摘要。",
                cleaned_text="课程介绍了 AI Knowledge Pipeline 的本地优先处理链路。",
                readable_transcript_text=(
                    "## 本地优先链路\n\n"
                    "今天我们讲 AI Knowledge Pipeline 和 Obsidian。这里修复了标点。"
                ),
                chapters=(
                    MarkdownReadyChapter(
                        chapter_index=0,
                        title="系统目标",
                        summary="把本地转录变成 Obsidian 笔记。",
                        blocks=(
                            MarkdownReadyBlock(
                                block_index=0,
                                kind=MarkdownBlockKind.PARAGRAPH,
                                text="LocalWhisperProvider 导入转录，DeepSeek 清洗内容。",
                            ),
                        ),
                        semantic_tags=("pipeline",),
                    ),
                ),
                key_insights=(
                    KeyInsight(
                        insight_index=0,
                        text="Runner 只负责编排已有模块。",
                        tags=("architecture",),
                    ),
                ),
                action_items=(
                    ActionItem(
                        action_index=0,
                        text="检查生成的 Obsidian 笔记。",
                    ),
                ),
                semantic_tags=("course", "deepseek", "obsidian"),
                agent_memory_candidates=(
                    AgentMemoryCandidate(
                        memory_index=0,
                        text="用户正在处理第一节真实课程。",
                        memory_type="project_context",
                        importance=0.8,
                    ),
                ),
            ),
            model_name=request.config.model_name,
            prompt_version=request.config.prompt_version,
            language="zh",
            confidence=0.9,
            metadata={"provider": "mock-deepseek"},
        )


class FailingCleaningProvider:
    name = "failing-deepseek"

    def clean(self, request):
        return CleaningProviderResult(
            issues=(
                TranscriptCleaningIssue(
                    code=TranscriptCleaningErrorCode.PROVIDER_FAILED,
                    message="mock provider failed",
                    field="provider",
                ),
            )
        )


class UnexpectedCleaningProvider:
    name = "must-not-run"

    def clean(self, request):
        raise AssertionError("AI / Tech direct transcript mode must bypass DeepSeek")


def test_real_course_pipeline_generates_obsidian_note(tmp_path) -> None:
    transcript_path = tmp_path / "course01.txt"
    transcript_path.write_text(
        "歡迎大家今天我们讲 AI Knowledge Pipeline 和 Obsidian 还有一个原始细节",
        encoding="utf-8",
    )
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_real_course_pipeline(
        RealCoursePipelineRequest(
            local_transcript_path=transcript_path,
            obsidian_vault_path=vault_path,
            title="第一节真实课程",
            tags=("ai", "course"),
            model="deepseek-v4-flash",
            profile=KnowledgeProfileName.FINANCE,
        ),
        cleaning_provider=MockDeepSeekProvider(),
    )

    assert result.obsidian_note_path.exists()
    note_text = result.obsidian_note_path.read_text(encoding="utf-8")
    assert "# AI整理部分" in note_text
    assert "## 第一节真实课程" in note_text
    assert note_text.index("## Action Items") < note_text.index("## Summary")
    assert "## Summary" in note_text
    assert "这是第一节课程的结构化摘要。" in note_text
    assert "## Chapters" in note_text
    assert "### 系统目标" in note_text
    assert "## Tags" not in note_text
    assert "#course #deepseek #obsidian" not in note_text
    assert "## Clean Transcript" not in note_text
    assert "# 可读转录" in note_text
    assert "这里修复了标点。" in note_text
    assert "# 原始逐字稿" in note_text
    assert "歡迎大家今天我们讲 AI Knowledge Pipeline 和 Obsidian 还有一个原始细节" in note_text
    assert result.artifacts.transcript.text.startswith("歡迎大家")
    assert result.artifacts.obsidian_note.snapshot.lineage.upstream_artifact_ids == (
        result.artifacts.markdown.markdown_artifact_id,
    )


def test_real_course_pipeline_supports_srt_transcript(tmp_path) -> None:
    transcript_path = tmp_path / "course01.srt"
    transcript_path.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\n第一段课程内容。\n",
        encoding="utf-8",
    )
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_real_course_pipeline(
        RealCoursePipelineRequest(
            local_transcript_path=transcript_path,
            obsidian_vault_path=vault_path,
        ),
        cleaning_provider=MockDeepSeekProvider(),
    )

    assert result.obsidian_note_path.exists()
    assert result.artifacts.transcript.segments[0].timestamp.end_time == 2


def test_ai_profile_writes_direct_english_transcript_without_knowledge_sections(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    transcript_path = tmp_path / "robotics.txt"
    transcript_path.write_text(
        "[00:00:05] Create a yellow circle there.\n\n"
        "[00:00:18] Can you draw me a small yellow circle?",
        encoding="utf-8",
    )
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_real_course_pipeline(
        RealCoursePipelineRequest(
            local_transcript_path=transcript_path,
            obsidian_vault_path=vault_path,
            title="Gemini Robotics 2",
            tags=("ai", "tech", "course"),
            profile=KnowledgeProfileName.AI,
            env_path=tmp_path / "missing.env",
        ),
    )

    note_text = result.obsidian_note_path.read_text(encoding="utf-8")
    logs = capsys.readouterr().out
    assert "# Gemini Robotics 2" in note_text
    assert 'profile: "AI / Tech"' in note_text
    assert "## Transcript" in note_text
    assert "[00:00:05] Create a yellow circle there." in note_text
    assert "[00:00:18] Can you draw me a small yellow circle?" in note_text
    assert "## Summary" not in note_text
    assert "## Chapters" not in note_text
    assert "## Key Insights" not in note_text
    assert "## Action Items" not in note_text
    assert "# AI整理部分" not in note_text
    assert result.obsidian_note_path.parent.name == "ai"
    assert "DeepSeek Cleaning skipped for AI / Tech transcript output" in logs


def test_ai_profile_preserves_srt_segment_timestamps_without_llm(tmp_path) -> None:
    transcript_path = tmp_path / "robotics.srt"
    transcript_path.write_text(
        "1\n00:00:05,000 --> 00:00:08,000\nCreate a yellow circle there.\n\n"
        "2\n00:00:18,000 --> 00:00:21,000\nMake it a rocket ship.\n",
        encoding="utf-8",
    )
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_real_course_pipeline(
        RealCoursePipelineRequest(
            local_transcript_path=transcript_path,
            obsidian_vault_path=vault_path,
            title="Robotics Listening Practice",
            tags=("ai", "tech"),
            profile=KnowledgeProfileName.AI,
        ),
        cleaning_provider=UnexpectedCleaningProvider(),
    )

    note_text = result.obsidian_note_path.read_text(encoding="utf-8")
    assert "[00:00:05] Create a yellow circle there." in note_text
    assert "[00:00:18] Make it a rocket ship." in note_text
    assert "00:00:05,000 --> 00:00:08,000" not in note_text


def test_ai_profile_preserves_single_srt_segment_timestamp(tmp_path) -> None:
    transcript_path = tmp_path / "single-caption.srt"
    transcript_path.write_text(
        "1\n00:00:05,000 --> 00:00:08,000\nCreate a yellow circle there.\n",
        encoding="utf-8",
    )
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_real_course_pipeline(
        RealCoursePipelineRequest(
            local_transcript_path=transcript_path,
            obsidian_vault_path=vault_path,
            title="Single Caption",
            tags=("ai", "tech"),
            profile=KnowledgeProfileName.AI,
        )
    )

    note_text = result.obsidian_note_path.read_text(encoding="utf-8")
    assert "[00:00:05] Create a yellow circle there." in note_text


def test_ai_profile_preserves_technical_angle_bracket_text(tmp_path) -> None:
    transcript_path = tmp_path / "technical.txt"
    transcript_path.write_text(
        "Use <div> for the container and List<T> for the generic type.",
        encoding="utf-8",
    )
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_real_course_pipeline(
        RealCoursePipelineRequest(
            local_transcript_path=transcript_path,
            obsidian_vault_path=vault_path,
            title="Technical Syntax",
            tags=("ai", "tech"),
            profile=KnowledgeProfileName.AI,
        )
    )

    note_text = result.obsidian_note_path.read_text(encoding="utf-8")
    assert "<div>" in note_text
    assert "List<T>" in note_text


def test_ai_profile_preserves_arrow_syntax_but_removes_subtitle_timing(tmp_path) -> None:
    transcript_path = tmp_path / "arrows.txt"
    transcript_path.write_text(
        "WEBVTT\n\n1\n00:00:05.000 --> 00:00:08.000\nA --> B\n",
        encoding="utf-8",
    )
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_real_course_pipeline(
        RealCoursePipelineRequest(
            local_transcript_path=transcript_path,
            obsidian_vault_path=vault_path,
            title="Arrow Syntax",
            tags=("ai", "tech"),
            profile=KnowledgeProfileName.AI,
        )
    )

    note_text = result.obsidian_note_path.read_text(encoding="utf-8")
    assert "A --> B" in note_text
    assert "00:00:05.000 --> 00:00:08.000" not in note_text


def test_ai_profile_removes_only_obvious_subtitle_noise_and_duplicates(tmp_path) -> None:
    transcript_path = tmp_path / "captions.txt"
    transcript_path.write_text(
        "WEBVTT\n\n1\n00:00:05.000 --> 00:00:08.000\n"
        "<c>Create a yellow circle.</c>\n\n"
        "2\n00:00:08.000 --> 00:00:10.000\nCreate a yellow circle.\n",
        encoding="utf-8",
    )
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_real_course_pipeline(
        RealCoursePipelineRequest(
            local_transcript_path=transcript_path,
            obsidian_vault_path=vault_path,
            title="Caption Cleanup",
            tags=("ai", "tech"),
            profile=KnowledgeProfileName.AI,
        )
    )

    note_text = result.obsidian_note_path.read_text(encoding="utf-8")
    assert "WEBVTT" not in note_text
    assert "-->" not in note_text
    assert "<c>" not in note_text
    assert note_text.count("Create a yellow circle.") == 1


def test_non_ai_profile_still_uses_structured_cleaning_provider(tmp_path) -> None:
    transcript_path = tmp_path / "startup.txt"
    transcript_path.write_text("A startup course transcript.", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_real_course_pipeline(
        RealCoursePipelineRequest(
            local_transcript_path=transcript_path,
            obsidian_vault_path=vault_path,
            title="Startup Course",
            tags=("startup", "course"),
            profile=KnowledgeProfileName.STARTUP,
        ),
        cleaning_provider=MockDeepSeekProvider(),
    )

    note_text = result.obsidian_note_path.read_text(encoding="utf-8")
    assert "# AI整理部分" in note_text
    assert "## Summary" in note_text
    assert "## Chapters" in note_text


def test_real_course_pipeline_requires_existing_vault(tmp_path) -> None:
    transcript_path = tmp_path / "course01.txt"
    transcript_path.write_text("hello", encoding="utf-8")

    try:
        run_real_course_pipeline(
            RealCoursePipelineRequest(
                local_transcript_path=transcript_path,
                obsidian_vault_path=tmp_path / "missing-vault",
            ),
            cleaning_provider=MockDeepSeekProvider(),
        )
    except RealCoursePipelineError as exc:
        assert "Obsidian vault path does not exist" in str(exc)
    else:
        raise AssertionError("Expected missing vault error")


def test_real_course_pipeline_requires_api_key_for_real_provider(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    transcript_path = tmp_path / "course01.txt"
    transcript_path.write_text("hello", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    try:
        run_real_course_pipeline(
            RealCoursePipelineRequest(
                local_transcript_path=transcript_path,
                obsidian_vault_path=vault_path,
                env_path=tmp_path / ".env",
                profile=KnowledgeProfileName.FINANCE,
            )
        )
    except RealCoursePipelineError as exc:
        assert "Missing DEEPSEEK_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing API key error")


def test_real_course_pipeline_surfaces_cleaning_error(tmp_path) -> None:
    transcript_path = tmp_path / "course01.txt"
    transcript_path.write_text("hello", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    try:
        run_real_course_pipeline(
            RealCoursePipelineRequest(
                local_transcript_path=transcript_path,
                obsidian_vault_path=vault_path,
                profile=KnowledgeProfileName.FINANCE,
            ),
            cleaning_provider=FailingCleaningProvider(),
        )
    except RealCoursePipelineError as exc:
        assert "Transcript cleaning failed" in str(exc)
    else:
        raise AssertionError("Expected cleaning error")


def test_real_course_pipeline_requires_custom_profile_path(tmp_path) -> None:
    transcript_path = tmp_path / "course01.txt"
    transcript_path.write_text("hello", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    try:
        run_real_course_pipeline(
            RealCoursePipelineRequest(
                local_transcript_path=transcript_path,
                obsidian_vault_path=vault_path,
                profile="custom",
            ),
            cleaning_provider=MockDeepSeekProvider(),
        )
    except RealCoursePipelineError as exc:
        assert "custom_profile_path is required" in str(exc)
    else:
        raise AssertionError("Expected custom profile path error")


def test_real_course_pipeline_cli_uses_env_vault_and_prints_note_path(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    transcript_path = tmp_path / "course01.txt"
    transcript_path.write_text("hello", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    env_path = Path(".env")

    def fake_run(request, cleaning_provider=None):
        class FakeResult:
            obsidian_note_path = vault_path / "note.md"

        assert request.obsidian_vault_path == vault_path
        assert request.local_transcript_path == transcript_path
        assert request.tags == ("ai", "course")
        return FakeResult()

    monkeypatch.setattr(
        "scripts.run_real_course_pipeline.run_real_course_pipeline",
        fake_run,
    )
    monkeypatch.setattr(
        "scripts.run_real_course_pipeline._read_env_file",
        lambda path: {
            "OBSIDIAN_VAULT_PATH": str(vault_path),
            "DEEPSEEK_MODEL": "deepseek-v4-flash",
        }
        if path == env_path
        else {},
    )

    exit_code = main(
        [
            "--transcript",
            str(transcript_path),
            "--title",
            "Course 01",
            "--tags",
            "ai,course",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(vault_path / "note.md") in captured.out
    assert "DEEPSEEK_API_KEY" not in captured.out
