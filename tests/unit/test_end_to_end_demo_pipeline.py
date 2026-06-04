from pathlib import Path

from ai_knowledge_pipeline.demo import (
    DemoPipelineRequest,
    run_local_audio_demo_pipeline,
)
from ai_knowledge_pipeline.modules.obsidian import ObsidianWriteStatus


def test_local_audio_demo_pipeline_writes_obsidian_note(tmp_path) -> None:
    request = DemoPipelineRequest(
        local_audio_path=Path("fixtures/local-demo-audio.mp3"),
        temp_vault_path=tmp_path,
        media_duration_seconds=120,
        chunk_duration_seconds=120,
    )

    result = run_local_audio_demo_pipeline(request)

    assert result.obsidian_note_path.exists()
    assert result.obsidian_note_path.suffix == ".md"
    assert result.artifacts.obsidian_note.status is ObsidianWriteStatus.WRITTEN

    markdown = result.obsidian_note_path.read_text(encoding="utf-8")
    assert "# AI整理部分" in markdown
    assert "## AI Knowledge Pipeline Demo" in markdown
    assert "## Summary" in markdown
    assert "A local demo showing how audio flows" in markdown
    assert "## Chapters" in markdown
    assert "### Pipeline Flow" in markdown
    assert "## Key Insights" in markdown
    assert "- Artifact lineage makes the generated note auditable." in markdown
    assert "- Mock providers allow local demos without network or AI APIs." in markdown
    assert "## Action Items" in markdown
    assert "- [ ] Replace demo providers with real providers when ready." in markdown
    assert "## Tags" in markdown
    assert "#ai-pipeline #obsidian #demo" in markdown

    artifacts = result.artifacts
    assert artifacts.obsidian_note.snapshot.lineage.input_snapshot_ids == (
        artifacts.markdown.snapshot.snapshot_id,
    )
    assert artifacts.markdown.snapshot.lineage.input_snapshot_ids == (
        artifacts.cleaned_transcript.snapshot.snapshot_id,
    )
    assert artifacts.cleaned_transcript.snapshot.lineage.input_snapshot_ids == (
        artifacts.transcript.snapshot.snapshot_id,
    )
    assert artifacts.transcript.snapshot.lineage.input_snapshot_ids == (
        artifacts.chunk.snapshot.snapshot_id,
    )
    assert artifacts.chunk.snapshot.lineage.input_snapshot_ids == (
        artifacts.media.snapshot.snapshot_id,
    )
    assert artifacts.media.snapshot.lineage.source_id == artifacts.source.source_id

    assert result.lineage_chain == (
        artifacts.obsidian_note.snapshot.snapshot_id,
        artifacts.markdown.snapshot.snapshot_id,
        artifacts.cleaned_transcript.snapshot.snapshot_id,
        artifacts.transcript.snapshot.snapshot_id,
        artifacts.chunk.snapshot.snapshot_id,
        artifacts.media.snapshot.snapshot_id,
        artifacts.source.source_id,
    )
