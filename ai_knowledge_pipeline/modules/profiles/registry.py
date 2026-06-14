"""Built-in Wonderland knowledge profile registry."""

from __future__ import annotations

from pathlib import Path

from ai_knowledge_pipeline.modules.profiles.types import KnowledgeProductProfile


class UnknownProfileError(ValueError):
    """Raised when a requested Wonderland profile is not registered."""


class ProfileRegistry:
    """Resolve user-facing profile IDs into runner-safe profile configuration."""

    def __init__(
        self,
        profiles: tuple[KnowledgeProductProfile, ...] | None = None,
    ) -> None:
        self._profiles = {
            profile.id: profile for profile in (profiles or BUILTIN_PROFILES)
        }

    def get(self, profile_id: str | None) -> KnowledgeProductProfile:
        """Return a profile by ID, defaulting to finance."""

        requested_id = (profile_id or DEFAULT_PROFILE_ID).strip() or DEFAULT_PROFILE_ID
        try:
            return self._profiles[requested_id]
        except KeyError as exc:
            known = ", ".join(sorted(self._profiles))
            raise UnknownProfileError(
                f"Unknown knowledge profile '{requested_id}'. Available profiles: {known}."
            ) from exc

    def list(self) -> tuple[KnowledgeProductProfile, ...]:
        """Return all built-in profiles in stable UI order."""

        return tuple(self._profiles[profile.id] for profile in BUILTIN_PROFILES)


DEFAULT_PROFILE_ID = "finance"
OBSIDIAN_ROOT = Path("AI Knowledge Pipeline")

BUILTIN_PROFILES = (
    KnowledgeProductProfile(
        id="finance",
        display_name="Finance",
        prompt_profile="finance",
        output_folder=OBSIDIAN_ROOT / "finance",
        tags=("finance", "course", "whisper-small", "wonderland"),
    ),
    KnowledgeProductProfile(
        id="metaphysics",
        display_name="Metaphysics / Ziwei Bazi",
        prompt_profile="metaphysics",
        runner_prompt_profile="ai",
        output_folder=OBSIDIAN_ROOT / "metaphysics",
        tags=("metaphysics", "ziwei", "bazi", "course", "wonderland"),
    ),
    KnowledgeProductProfile(
        id="ai",
        display_name="AI / Tech",
        prompt_profile="ai",
        output_folder=OBSIDIAN_ROOT / "ai",
        tags=("ai", "tech", "course", "wonderland"),
    ),
    KnowledgeProductProfile(
        id="general",
        display_name="General",
        prompt_profile="general",
        runner_prompt_profile="ai",
        output_folder=OBSIDIAN_ROOT / "general",
        tags=("general", "course", "wonderland"),
    ),
)


__all__ = [
    "BUILTIN_PROFILES",
    "DEFAULT_PROFILE_ID",
    "OBSIDIAN_ROOT",
    "ProfileRegistry",
    "UnknownProfileError",
]
