"""DeepSeek transcript cleaning provider."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

from ai_knowledge_pipeline.modules.cleaning.errors import (
    TranscriptCleaningErrorCode,
    TranscriptCleaningIssue,
)
from ai_knowledge_pipeline.modules.cleaning.interfaces import TranscriptCleaningProvider
from ai_knowledge_pipeline.modules.cleaning.prompt_templates import (
    OPENAI_CLEANING_JSON_SCHEMA_HINT,
    OPENAI_CLEANING_SYSTEM_PROMPT,
    OPENAI_CLEANING_TASK_TEMPLATE,
)
from ai_knowledge_pipeline.modules.cleaning.response_parser import (
    parse_cleaning_response,
)
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


class DeepSeekChatCompletionsEndpoint(Protocol):
    """Minimal chat completions endpoint protocol."""

    def create(self, **kwargs): ...


class DeepSeekChatEndpoint(Protocol):
    """Minimal chat endpoint protocol."""

    completions: DeepSeekChatCompletionsEndpoint


class DeepSeekClient(Protocol):
    """Minimal OpenAI-compatible client protocol used by DeepSeek."""

    chat: DeepSeekChatEndpoint


class DeepSeekCleaningProvider(TranscriptCleaningProvider):
    """Clean transcript artifacts using DeepSeek chat completions."""

    name = "deepseek-cleaning"
    default_base_url = "https://api.deepseek.com"
    default_model = "deepseek-v4-flash"
    api_key_env_var = "DEEPSEEK_API_KEY"
    base_url_env_var = "DEEPSEEK_BASE_URL"
    model_env_var = "DEEPSEEK_MODEL"

    def __init__(
        self,
        client: DeepSeekClient | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        env_path: Path | None = None,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._env_path = env_path

    def clean(self, request: TranscriptCleaningRequest) -> CleaningProviderResult:
        env_path = self._env_path or request.config.env_path
        env_values = _read_env_file(env_path)
        client = self._client
        api_key = self._api_key or _load_value(self.api_key_env_var, env_values)
        base_url = (
            self._base_url
            or _load_value(self.base_url_env_var, env_values)
            or self.default_base_url
        )
        model = (
            request.config.model_name
            or self._model
            or _load_value(self.model_env_var, env_values)
            or self.default_model
        )

        if client is None:
            if not api_key:
                return _issue_result(
                    TranscriptCleaningErrorCode.MISSING_API_KEY,
                    "DeepSeek API key is required for DeepSeekCleaningProvider.",
                    self.api_key_env_var,
                )
            try:
                client = _create_deepseek_client(api_key=api_key, base_url=base_url)
            except ImportError:
                return _issue_result(
                    TranscriptCleaningErrorCode.SDK_UNAVAILABLE,
                    "The openai package is not installed.",
                    "openai",
                )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": OPENAI_CLEANING_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": _build_user_prompt(request),
                    },
                ],
            )
        except Exception as exc:  # pragma: no cover - exact SDK exceptions vary
            return _issue_result(
                TranscriptCleaningErrorCode.PROVIDER_FAILED,
                _safe_error_message(exc, api_key),
                "deepseek.chat.completions.create",
            )

        response_text = _extract_chat_completion_text(response)
        try:
            parsed = parse_cleaning_response(
                response_text,
                default_title=_default_title(request),
            )
        except (TypeError, ValueError, KeyError) as exc:
            return _issue_result(
                TranscriptCleaningErrorCode.RESPONSE_PARSE_FAILED,
                f"DeepSeek response could not be parsed: {exc}",
                "response",
            )

        return CleaningProviderResult(
            markdown_ready=parsed.markdown_ready,
            model_name=model,
            prompt_version=request.config.prompt_version,
            language=request.config.language or request.transcript.language,
            confidence=_optional_float(parsed.payload.get("confidence")),
            metadata={
                "provider": self.name,
                "model": model,
                "base_url": base_url,
                "response_id": str(getattr(response, "id", "")),
            },
        )


def _build_user_prompt(request: TranscriptCleaningRequest) -> str:
    prompt = request.prompt
    language = request.config.language or request.transcript.language or "auto"
    return "\n\n".join(
        (
            prompt.system_instruction,
            prompt.task_instruction,
            OPENAI_CLEANING_TASK_TEMPLATE.format(
                language=language,
                prompt_version=request.config.prompt_version,
                terminology=", ".join(prompt.terminology) or "none",
                output_requirements=", ".join(prompt.output_requirements) or "default",
                style_guide=prompt.style_guide or "clear technical Markdown",
                transcript_text=request.transcript.text,
            ),
            OPENAI_CLEANING_JSON_SCHEMA_HINT,
        )
    )


def _default_title(request: TranscriptCleaningRequest) -> str:
    return (
        request.transcript.snapshot.metadata.title
        or request.transcript.source_id
        or "Untitled Transcript"
    )


def _create_deepseek_client(api_key: str, base_url: str):
    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url)


def _load_value(env_var: str, env_values: dict[str, str]) -> str | None:
    return os.environ.get(env_var) or env_values.get(env_var)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _extract_chat_completion_text(response) -> str:
    if isinstance(response, dict):
        choices = response.get("choices") or ()
        if choices:
            message = choices[0].get("message", {})
            return str(message.get("content", ""))
        if response.get("content"):
            return str(response["content"])

    choices = getattr(response, "choices", ())
    if choices:
        message = getattr(choices[0], "message", None)
        if message is not None and getattr(message, "content", None) is not None:
            return str(message.content)
    if getattr(response, "content", None):
        return str(response.content)
    return str(response)


def _parse_markdown_ready(payload: dict[str, Any]) -> MarkdownReadyTranscript:
    return MarkdownReadyTranscript(
        title=str(payload["title"]),
        summary=str(payload["summary"]),
        cleaned_text=str(payload["cleaned_text"]),
        readable_transcript_text=str(payload.get("readable_transcript_text", "")),
        chapters=tuple(
            _parse_chapter(item, index)
            for index, item in enumerate(payload.get("chapters", ()))
        ),
        key_insights=tuple(
            _parse_key_insight(item, index)
            for index, item in enumerate(payload.get("key_insights", ()))
        ),
        action_items=tuple(
            _parse_action_item(item, index)
            for index, item in enumerate(payload.get("action_items", ()))
        ),
        semantic_tags=tuple(str(tag) for tag in payload.get("semantic_tags", ())),
        agent_memory_candidates=tuple(
            _parse_memory_candidate(item, index)
            for index, item in enumerate(payload.get("agent_memory_candidates", ()))
        ),
    )


def _parse_chapter(item: dict[str, Any], index: int) -> MarkdownReadyChapter:
    return MarkdownReadyChapter(
        chapter_index=index,
        title=str(item["title"]),
        summary=_optional_str(item.get("summary")),
        start_time=_optional_float(item.get("start_time")),
        end_time=_optional_float(item.get("end_time")),
        semantic_tags=tuple(str(tag) for tag in item.get("semantic_tags", ())),
        blocks=tuple(
            _parse_block(block, block_index)
            for block_index, block in enumerate(item.get("blocks", ()))
        ),
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


def _parse_key_insight(item: dict[str, Any], index: int) -> KeyInsight:
    return KeyInsight(
        insight_index=index,
        text=str(item["text"]),
        confidence=_optional_float(item.get("confidence")),
        tags=tuple(str(tag) for tag in item.get("tags", ())),
    )


def _parse_action_item(item: dict[str, Any], index: int) -> ActionItem:
    return ActionItem(
        action_index=index,
        text=str(item["text"]),
        owner=_optional_str(item.get("owner")),
        due=_optional_str(item.get("due")),
    )


def _parse_memory_candidate(item: dict[str, Any], index: int) -> AgentMemoryCandidate:
    return AgentMemoryCandidate(
        memory_index=index,
        text=str(item["text"]),
        memory_type=_optional_str(item.get("memory_type")),
        importance=_optional_float(item.get("importance")),
        tags=tuple(str(tag) for tag in item.get("tags", ())),
    )


def _optional_str(value) -> str | None:
    return None if value is None else str(value)


def _optional_float(value) -> float | None:
    return None if value is None else float(value)


def _optional_int(value) -> int | None:
    return None if value is None else int(value)


def _safe_error_message(exc: Exception, api_key: str | None) -> str:
    message = str(exc)
    return message.replace(api_key, "[redacted]") if api_key else message


def _issue_result(
    code: TranscriptCleaningErrorCode,
    message: str,
    field: str,
) -> CleaningProviderResult:
    return CleaningProviderResult(
        markdown_ready=None,
        issues=(
            TranscriptCleaningIssue(
                code=code,
                message=message,
                field=field,
            ),
        ),
    )


__all__ = ["DeepSeekCleaningProvider"]
