"""Parse provider responses into Markdown-ready cleaning results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ai_knowledge_pipeline.modules.cleaning.types import (
    ActionItem,
    AgentMemoryCandidate,
    KeyInsight,
    MarkdownBlockKind,
    MarkdownReadyBlock,
    MarkdownReadyChapter,
    MarkdownReadyTranscript,
)


STRUCTURED_JSON_MARKER = "===STRUCTURED_JSON==="
READABLE_TRANSCRIPT_MARKER = "===READABLE_TRANSCRIPT==="


@dataclass(frozen=True, slots=True)
class ParsedCleaningResponse:
    """Parsed structured JSON plus separately parsed readable transcript."""

    markdown_ready: MarkdownReadyTranscript
    payload: dict[str, Any]


def parse_cleaning_response(
    response_text: str,
    *,
    default_title: str,
) -> ParsedCleaningResponse:
    """Parse two-section provider output, falling back to legacy JSON."""

    payload_text, readable_transcript_text = _split_two_section_response(response_text)
    payload = json.loads(_strip_code_fence(payload_text))
    markdown_ready = _parse_markdown_ready(
        payload,
        default_title=default_title,
        readable_transcript_text=readable_transcript_text,
    )
    return ParsedCleaningResponse(markdown_ready=markdown_ready, payload=payload)


def _split_two_section_response(response_text: str) -> tuple[str, str]:
    if (
        STRUCTURED_JSON_MARKER not in response_text
        or READABLE_TRANSCRIPT_MARKER not in response_text
    ):
        return response_text.strip(), ""

    _, after_structured = response_text.split(STRUCTURED_JSON_MARKER, maxsplit=1)
    structured_text, readable_text = after_structured.split(
        READABLE_TRANSCRIPT_MARKER,
        maxsplit=1,
    )
    return structured_text.strip(), readable_text.strip()


def _strip_code_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _parse_markdown_ready(
    payload: dict[str, Any],
    *,
    default_title: str,
    readable_transcript_text: str,
) -> MarkdownReadyTranscript:
    chapters = tuple(
        _parse_chapter(item, index)
        for index, item in enumerate(
            payload.get("chapters") or payload.get("sections") or ()
        )
    )
    summary = str(payload.get("summary") or "")
    cleaned_text = str(payload.get("cleaned_text") or _fallback_cleaned_text(summary, chapters))
    return MarkdownReadyTranscript(
        title=str(payload.get("title") or default_title),
        summary=summary or cleaned_text,
        cleaned_text=cleaned_text,
        readable_transcript_text=readable_transcript_text
        or str(payload.get("readable_transcript_text", "")),
        chapters=chapters,
        key_insights=tuple(
            _parse_key_insight(item, index)
            for index, item in enumerate(payload.get("key_insights", ()))
        ),
        action_items=tuple(
            _parse_action_item(item, index)
            for index, item in enumerate(payload.get("action_items", ()))
        ),
        semantic_tags=tuple(
            str(tag) for tag in (payload.get("semantic_tags") or payload.get("tags") or ())
        ),
        agent_memory_candidates=tuple(
            _parse_memory_candidate(item, index)
            for index, item in enumerate(payload.get("agent_memory_candidates", ()))
        ),
    )


def _parse_chapter(item: dict[str, Any], index: int) -> MarkdownReadyChapter:
    title = str(item.get("title") or item.get("heading") or item.get("name") or f"Section {index + 1}")
    summary = _optional_str(item.get("summary"))
    blocks_payload = item.get("blocks")
    if blocks_payload:
        blocks = tuple(
            _parse_block(block, block_index)
            for block_index, block in enumerate(blocks_payload)
        )
    else:
        block_text = _optional_str(item.get("content") or item.get("text") or summary)
        blocks = (
            (
                MarkdownReadyBlock(
                    block_index=0,
                    kind=MarkdownBlockKind.PARAGRAPH,
                    text=block_text,
                ),
            )
            if block_text
            else ()
        )
    return MarkdownReadyChapter(
        chapter_index=index,
        title=title,
        summary=summary,
        start_time=_optional_float(item.get("start_time")),
        end_time=_optional_float(item.get("end_time")),
        semantic_tags=tuple(str(tag) for tag in item.get("semantic_tags", ())),
        blocks=blocks,
    )


def _parse_block(item: dict[str, Any], index: int) -> MarkdownReadyBlock:
    kind_value = str(item.get("kind", "paragraph"))
    try:
        kind = MarkdownBlockKind(kind_value)
    except ValueError:
        kind = MarkdownBlockKind.PARAGRAPH
    return MarkdownReadyBlock(
        block_index=index,
        kind=kind,
        text=str(item.get("text", "")),
        heading_level=_optional_int(item.get("heading_level")),
    )


def _parse_key_insight(item, index: int) -> KeyInsight:
    if isinstance(item, str):
        return KeyInsight(insight_index=index, text=item)
    return KeyInsight(
        insight_index=index,
        text=str(item["text"]),
        confidence=_optional_float(item.get("confidence")),
        tags=tuple(str(tag) for tag in item.get("tags", ())),
    )


def _parse_action_item(item, index: int) -> ActionItem:
    if isinstance(item, str):
        return ActionItem(action_index=index, text=item)
    return ActionItem(
        action_index=index,
        text=str(item["text"]),
        owner=_optional_str(item.get("owner")),
        due=_optional_str(item.get("due")),
    )


def _parse_memory_candidate(item, index: int) -> AgentMemoryCandidate:
    if isinstance(item, str):
        return AgentMemoryCandidate(memory_index=index, text=item)
    return AgentMemoryCandidate(
        memory_index=index,
        text=str(item["text"]),
        memory_type=_optional_str(item.get("memory_type")),
        importance=_optional_float(item.get("importance")),
        tags=tuple(str(tag) for tag in item.get("tags", ())),
    )


def _fallback_cleaned_text(
    summary: str,
    chapters: tuple[MarkdownReadyChapter, ...],
) -> str:
    parts: list[str] = []
    if summary:
        parts.append(summary)
    for chapter in chapters:
        parts.append(chapter.title)
        if chapter.summary:
            parts.append(chapter.summary)
        parts.extend(block.text for block in chapter.blocks if block.text)
    return "\n\n".join(parts).strip() or "No cleaned transcript was returned."


def _optional_str(value) -> str | None:
    return None if value is None else str(value)


def _optional_float(value) -> float | None:
    return None if value is None else float(value)


def _optional_int(value) -> int | None:
    return None if value is None else int(value)


__all__ = [
    "ParsedCleaningResponse",
    "READABLE_TRANSCRIPT_MARKER",
    "STRUCTURED_JSON_MARKER",
    "parse_cleaning_response",
]
