"""Typed product profile definitions for Wonderland."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class KnowledgeProductProfile:
    """User-facing knowledge profile configuration.

    ``prompt_profile`` is the future domain-specific prompt target. Some MVP
    profiles use ``runner_prompt_profile`` as a temporary fallback until their
    domain prompts are added.
    """

    id: str
    display_name: str
    prompt_profile: str
    output_folder: Path
    tags: tuple[str, ...]
    runner_prompt_profile: str | None = None
    note_template: str | None = None

    @property
    def effective_prompt_profile(self) -> str:
        """Return the prompt profile currently safe to pass to the runner."""

        return self.runner_prompt_profile or self.prompt_profile


__all__ = ["KnowledgeProductProfile"]
