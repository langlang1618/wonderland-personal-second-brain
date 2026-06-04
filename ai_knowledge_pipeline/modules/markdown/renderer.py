"""Obsidian-ready Markdown renderer."""

from __future__ import annotations

from ai_knowledge_pipeline.modules.cleaning.types import (
    MarkdownBlockKind,
    MarkdownReadyBlock,
)
from ai_knowledge_pipeline.modules.markdown.errors import (
    MarkdownGenerationErrorCode,
    MarkdownGenerationIssue,
)
from ai_knowledge_pipeline.modules.markdown.interfaces import MarkdownRenderer
from ai_knowledge_pipeline.modules.markdown.types import (
    MarkdownGenerationRequest,
    MarkdownRenderResult,
    YamlFrontmatter,
)


class ObsidianMarkdownRenderer(MarkdownRenderer):
    """Render Markdown-ready transcript content into Obsidian-style Markdown."""

    def render(self, request: MarkdownGenerationRequest) -> MarkdownRenderResult:
        ready = request.cleaned_transcript.markdown_ready
        if not ready.title.strip():
            return MarkdownRenderResult(
                markdown_text="",
                issues=(
                    MarkdownGenerationIssue(
                        code=MarkdownGenerationErrorCode.MISSING_TITLE,
                        message="Markdown generation requires a title.",
                        field="markdown_ready.title",
                    ),
                ),
            )
        if not ready.cleaned_text.strip():
            return MarkdownRenderResult(
                markdown_text="",
                issues=(
                    MarkdownGenerationIssue(
                        code=MarkdownGenerationErrorCode.MISSING_CLEANED_TEXT,
                        message="Markdown generation requires cleaned transcript text.",
                        field="markdown_ready.cleaned_text",
                    ),
                ),
            )

        frontmatter = _frontmatter(request)
        body = _body(request)
        markdown_text = (
            f"{_format_frontmatter(frontmatter)}\n{body}"
            if request.config.include_frontmatter
            else body
        )
        return MarkdownRenderResult(
            markdown_text=markdown_text.rstrip() + "\n",
            frontmatter=frontmatter,
        )


def _frontmatter(request: MarkdownGenerationRequest) -> YamlFrontmatter:
    cleaned = request.cleaned_transcript
    ready = cleaned.markdown_ready
    tags = tuple(dict.fromkeys((*cleaned.snapshot.metadata.tags, *ready.semantic_tags)))
    return {
        "title": ready.title,
        "source_id": cleaned.source_id,
        "chunk_index": cleaned.chunk_index,
        "language": cleaned.language,
        "tags": tags,
        "summary": ready.summary,
        "parent_cleaned_transcript_artifact_id": (
            cleaned.cleaned_transcript_artifact_id
        ),
        "parent_snapshot_id": cleaned.snapshot.snapshot_id,
    }


def _body(request: MarkdownGenerationRequest) -> str:
    ready = request.cleaned_transcript.markdown_ready
    lines: list[str] = ["# AI整理部分", "", f"## {ready.title}", ""]

    if request.config.include_summary:
        lines.extend(("## Summary", "", ready.summary, ""))

    if ready.chapters:
        lines.extend(("## Chapters", ""))
        for chapter in ready.chapters:
            lines.extend((f"### {chapter.title}", ""))
            if chapter.summary:
                lines.extend((chapter.summary, ""))
            if chapter.start_time is not None and chapter.end_time is not None:
                lines.extend(
                    (
                        f"_Time: {_format_time(chapter.start_time)} - "
                        f"{_format_time(chapter.end_time)}_",
                        "",
                    )
                )
            for block in chapter.blocks:
                lines.extend(_render_block(block))
                lines.append("")

    if request.config.include_key_insights and ready.key_insights:
        lines.extend(("## Key Insights", ""))
        for insight in ready.key_insights:
            lines.append(f"- {insight.text}")
        lines.append("")

    if request.config.include_action_items and ready.action_items:
        lines.extend(("## Action Items", ""))
        for action in ready.action_items:
            suffix = ""
            if action.owner:
                suffix += f" @{action.owner}"
            if action.due:
                suffix += f" due {action.due}"
            lines.append(f"- [ ] {action.text}{suffix}")
        lines.append("")

    if request.config.include_tags_section and ready.semantic_tags:
        lines.extend(("## Tags", ""))
        lines.append(" ".join(f"#{tag}" for tag in ready.semantic_tags))
        lines.append("")

    lines.extend(("## Clean Transcript", "", ready.cleaned_text, ""))
    original_transcript = (
        request.cleaned_transcript.readable_transcript_text
        or ready.readable_transcript_text
        or request.cleaned_transcript.raw_transcript
    )
    if original_transcript.strip():
        lines.extend(
            (
                "# 原始转录",
                "",
                original_transcript,
                "",
            )
        )
    return "\n".join(lines)


def _render_block(block: MarkdownReadyBlock) -> list[str]:
    if block.kind is MarkdownBlockKind.HEADING:
        level = block.heading_level or 4
        return [f"{'#' * level} {block.text}"]
    if block.kind is MarkdownBlockKind.BULLET_LIST:
        return [f"- {line.strip()}" for line in block.text.splitlines() if line.strip()]
    if block.kind is MarkdownBlockKind.QUOTE:
        return [f"> {line}" for line in block.text.splitlines()]
    if block.kind is MarkdownBlockKind.CODE:
        return ["```", block.text, "```"]
    return [block.text]


def _format_frontmatter(frontmatter: YamlFrontmatter) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {_yaml_value(value)}")
    lines.append("---")
    return "\n".join(lines)


def _yaml_value(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, tuple):
        if not value:
            return "[]"
        return "[" + ", ".join(_quote_yaml(str(item)) for item in value) + "]"
    return _quote_yaml(str(value))


def _quote_yaml(value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def _format_time(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


__all__ = ["ObsidianMarkdownRenderer"]
