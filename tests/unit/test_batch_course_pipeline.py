from pathlib import Path

from ai_knowledge_pipeline.modules.cleaning import (
    ActionItem,
    CleaningProviderResult,
    KeyInsight,
    KnowledgeProfileName,
    MarkdownBlockKind,
    MarkdownReadyBlock,
    MarkdownReadyChapter,
    MarkdownReadyTranscript,
    TranscriptCleaningErrorCode,
    TranscriptCleaningIssue,
)
from scripts.run_batch_course_pipeline import (
    BatchCoursePipelineRequest,
    BatchItemStatus,
    main,
    run_batch_course_pipeline,
    scan_transcript_files,
)


class BatchMockCleaningProvider:
    name = "batch-mock-deepseek"

    def __init__(self, fail_when: str | None = None) -> None:
        self.fail_when = fail_when
        self.requests = []

    def clean(self, request):
        self.requests.append(request)
        if self.fail_when and self.fail_when in request.transcript.text:
            return CleaningProviderResult(
                issues=(
                    TranscriptCleaningIssue(
                        code=TranscriptCleaningErrorCode.PROVIDER_FAILED,
                        message="mock batch failure",
                        field="provider",
                    ),
                )
            )
        title = request.transcript.snapshot.metadata.title or "Batch Course"
        return CleaningProviderResult(
            markdown_ready=MarkdownReadyTranscript(
                title=str(title),
                summary=f"{title} 的摘要。",
                cleaned_text=f"{title} 的 AI 整理内容。",
                readable_transcript_text=f"## 可读转录\n\n{request.transcript.text}。",
                chapters=(
                    MarkdownReadyChapter(
                        chapter_index=0,
                        title="课程小节",
                        summary="批处理课程小节。",
                        blocks=(
                            MarkdownReadyBlock(
                                block_index=0,
                                kind=MarkdownBlockKind.PARAGRAPH,
                                text="批处理生成 Markdown。",
                            ),
                        ),
                    ),
                ),
                key_insights=(
                    KeyInsight(insight_index=0, text="批处理不会因单个失败中断。"),
                ),
                action_items=(
                    ActionItem(action_index=0, text="检查批量生成的笔记。"),
                ),
                semantic_tags=("batch", "course"),
            ),
            model_name=request.config.model_name,
            prompt_version=request.config.prompt_version,
            language="zh",
            confidence=0.9,
        )


def write_transcripts(input_dir: Path, names: tuple[str, ...]) -> None:
    input_dir.mkdir()
    for name in names:
        (input_dir / name).write_text(f"{name} 内容", encoding="utf-8")


def test_scan_transcript_files_uses_natural_sort_and_supported_suffixes(tmp_path) -> None:
    input_dir = tmp_path / "transcripts"
    write_transcripts(
        input_dir,
        ("output_010.txt", "output_002.txt", "output_001.txt", "course.srt"),
    )
    (input_dir / "ignore.md").write_text("ignored", encoding="utf-8")

    files = scan_transcript_files(input_dir)

    assert [path.name for path in files] == (
        ["course.srt", "output_001.txt", "output_002.txt", "output_010.txt"]
    )


def test_batch_pipeline_generates_multiple_markdown_notes(tmp_path) -> None:
    input_dir = tmp_path / "transcripts"
    write_transcripts(input_dir, ("output_000.txt", "output_001.txt"))
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    provider = BatchMockCleaningProvider()

    result = run_batch_course_pipeline(
        BatchCoursePipelineRequest(
            input_dir=input_dir,
            obsidian_vault_path=vault_path,
            profile=KnowledgeProfileName.FINANCE,
            tags=("有钱有闲", "金融学习", "课程"),
            title_prefix="26.5.10直播",
            model="deepseek-v4-flash",
        ),
        cleaning_provider=provider,
    )

    assert result.total == 2
    assert result.success == 2
    assert result.failed == 0
    assert result.skipped == 0
    assert len(result.generated_note_paths) == 2
    assert result.generated_note_paths[0].exists()
    assert result.generated_note_paths[0].name == "26-5-10直播-001.md"
    assert result.generated_note_paths[1].name == "26-5-10直播-002.md"
    note_text = result.generated_note_paths[0].read_text(encoding="utf-8")
    assert "# AI整理部分" in note_text
    assert "# 可读转录" in note_text
    assert "# 原始逐字稿" in note_text
    assert "#batch #course" in note_text
    assert provider.requests[0].prompt.terminology[-6:] == (
        "美联储沃什",
        "鲍威尔",
        "FOMC",
        "CPI",
        "PPI",
        "M2",
    )
    assert provider.requests[0].transcript.snapshot.metadata.tags == (
        "有钱有闲",
        "金融学习",
        "课程",
    )


def test_batch_pipeline_limit_processes_first_n_files(tmp_path) -> None:
    input_dir = tmp_path / "transcripts"
    write_transcripts(input_dir, ("output_000.txt", "output_001.txt", "output_002.txt"))
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_batch_course_pipeline(
        BatchCoursePipelineRequest(
            input_dir=input_dir,
            obsidian_vault_path=vault_path,
            title_prefix="Course",
            limit=2,
        ),
        cleaning_provider=BatchMockCleaningProvider(),
    )

    assert result.total == 2
    assert result.success == 2
    assert [item.title for item in result.items] == ["Course 001", "Course 002"]


def test_batch_pipeline_dry_run_does_not_call_provider_or_write_notes(tmp_path) -> None:
    input_dir = tmp_path / "transcripts"
    write_transcripts(input_dir, ("output_000.txt", "output_001.txt"))
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    provider = BatchMockCleaningProvider()

    result = run_batch_course_pipeline(
        BatchCoursePipelineRequest(
            input_dir=input_dir,
            obsidian_vault_path=vault_path,
            title_prefix="Dry Run",
            dry_run=True,
        ),
        cleaning_provider=provider,
    )

    assert result.total == 2
    assert result.success == 0
    assert result.failed == 0
    assert result.skipped == 2
    assert all(item.status is BatchItemStatus.DRY_RUN for item in result.items)
    assert provider.requests == []
    assert not any(path.exists() for path in result.generated_note_paths)


def test_batch_pipeline_skip_existing_uses_expected_note_path(tmp_path) -> None:
    input_dir = tmp_path / "transcripts"
    write_transcripts(input_dir, ("output_000.txt", "output_001.txt"))
    vault_path = tmp_path / "vault"
    existing = vault_path / "AI Knowledge Pipeline" / "有钱有闲"
    existing.mkdir(parents=True)
    (existing / "26-5-10直播-001.md").write_text("existing", encoding="utf-8")
    provider = BatchMockCleaningProvider()

    result = run_batch_course_pipeline(
        BatchCoursePipelineRequest(
            input_dir=input_dir,
            obsidian_vault_path=vault_path,
            tags=("有钱有闲",),
            title_prefix="26.5.10直播",
            skip_existing=True,
        ),
        cleaning_provider=provider,
    )

    assert result.total == 2
    assert result.success == 1
    assert result.skipped == 1
    assert result.items[0].status is BatchItemStatus.SKIPPED
    assert result.items[1].status is BatchItemStatus.SUCCESS
    assert len(provider.requests) == 1


def test_batch_pipeline_continues_after_single_file_failure(tmp_path) -> None:
    input_dir = tmp_path / "transcripts"
    input_dir.mkdir()
    (input_dir / "output_000.txt").write_text("ok one", encoding="utf-8")
    (input_dir / "output_001.txt").write_text("please fail", encoding="utf-8")
    (input_dir / "output_002.txt").write_text("ok two", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = run_batch_course_pipeline(
        BatchCoursePipelineRequest(
            input_dir=input_dir,
            obsidian_vault_path=vault_path,
            title_prefix="Batch",
        ),
        cleaning_provider=BatchMockCleaningProvider(fail_when="please fail"),
    )

    assert result.total == 3
    assert result.success == 2
    assert result.failed == 1
    assert result.skipped == 0
    assert result.items[1].status is BatchItemStatus.FAILED
    assert len(result.generated_note_paths) == 2
    assert all(path.exists() for path in result.generated_note_paths)


def test_batch_cli_prints_summary_without_api_key(monkeypatch, tmp_path, capsys) -> None:
    input_dir = tmp_path / "transcripts"
    input_dir.mkdir()
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    def fake_run(request):
        assert request.input_dir == input_dir
        assert request.obsidian_vault_path == vault_path
        assert request.profile is KnowledgeProfileName.FINANCE
        assert request.tags == ("有钱有闲", "金融学习", "课程")
        return run_batch_course_pipeline(
            BatchCoursePipelineRequest(
                input_dir=input_dir,
                obsidian_vault_path=vault_path,
                dry_run=True,
            ),
            cleaning_provider=BatchMockCleaningProvider(),
        )

    monkeypatch.setattr("scripts.run_batch_course_pipeline.run_batch_course_pipeline", fake_run)

    exit_code = main(
        [
            "--input-dir",
            str(input_dir),
            "--vault",
            str(vault_path),
            "--profile",
            "finance",
            "--tags",
            "有钱有闲,金融学习,课程",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Batch summary:" in captured.out
    assert "DEEPSEEK_API_KEY" not in captured.out
