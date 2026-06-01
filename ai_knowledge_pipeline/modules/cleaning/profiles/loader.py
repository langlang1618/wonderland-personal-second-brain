"""Load and compose knowledge-profile prompts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from ai_knowledge_pipeline.modules.cleaning.types import CleaningPromptSchema


class KnowledgeProfileName(StrEnum):
    """Registered knowledge-profile names."""

    FINANCE = "finance"
    AI = "ai"
    STARTUP = "startup"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class KnowledgeProfile:
    """Loaded prompt fragments and terminology for one domain."""

    name: KnowledgeProfileName
    base_prompt: str
    profile_prompt: str
    terminology: tuple[str, ...] = ()
    source_paths: tuple[Path, ...] = ()

    @property
    def composed_prompt(self) -> str:
        """Return the base and domain prompts as one instruction."""

        return "\n\n".join(
            fragment.strip()
            for fragment in (self.base_prompt, self.profile_prompt)
            if fragment.strip()
        )


class KnowledgeProfileLoader:
    """Load prompt registry assets without provider coupling."""

    def __init__(self, registry_dir: Path | None = None) -> None:
        self._registry_dir = registry_dir or Path(__file__).parent

    def load(
        self,
        profile: KnowledgeProfileName | str,
        *,
        custom_profile_path: Path | None = None,
    ) -> KnowledgeProfile:
        """Load a registered profile or a custom Markdown prompt."""

        profile_name = KnowledgeProfileName(profile)
        base_path = self._registry_dir / "base.md"
        if profile_name is KnowledgeProfileName.CUSTOM:
            if custom_profile_path is None:
                raise ValueError("custom_profile_path is required for profile 'custom'.")
            profile_path = custom_profile_path
        else:
            profile_path = self._registry_dir / f"{profile_name.value}.md"

        terminology_paths = (
            (self._registry_dir / "finance_terms.yaml",)
            if profile_name is KnowledgeProfileName.FINANCE
            else ()
        )
        return KnowledgeProfile(
            name=profile_name,
            base_prompt=_read_text(base_path),
            profile_prompt=_read_text(profile_path),
            terminology=_load_terms(terminology_paths),
            source_paths=(base_path, profile_path, *terminology_paths),
        )


def load_knowledge_profile(
    profile: KnowledgeProfileName | str,
    *,
    custom_profile_path: Path | None = None,
    registry_dir: Path | None = None,
) -> KnowledgeProfile:
    """Load one profile from the default or supplied registry."""

    return KnowledgeProfileLoader(registry_dir=registry_dir).load(
        profile,
        custom_profile_path=custom_profile_path,
    )


def compose_cleaning_prompt(
    prompt: CleaningPromptSchema,
    profile: KnowledgeProfile,
) -> CleaningPromptSchema:
    """Compose a profile with an existing provider-portable prompt."""

    terminology = tuple(dict.fromkeys((*prompt.terminology, *profile.terminology)))
    return replace(
        prompt,
        system_instruction="\n\n".join(
            part.strip()
            for part in (profile.composed_prompt, prompt.system_instruction)
            if part.strip()
        ),
        terminology=terminology,
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"Unable to load knowledge profile asset: {path}") from exc


def _load_terms(paths: tuple[Path, ...]) -> tuple[str, ...]:
    terms: list[str] = []
    for path in paths:
        for raw_line in _read_text(path).splitlines():
            line = raw_line.strip()
            if line.startswith("- "):
                terms.append(line[2:].strip().strip('"').strip("'"))
    return tuple(dict.fromkeys(term for term in terms if term))


__all__ = [
    "KnowledgeProfile",
    "KnowledgeProfileLoader",
    "KnowledgeProfileName",
    "compose_cleaning_prompt",
    "load_knowledge_profile",
]
