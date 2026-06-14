"""Wonderland product profile registry."""

from ai_knowledge_pipeline.modules.profiles.registry import (
    BUILTIN_PROFILES,
    DEFAULT_PROFILE_ID,
    OBSIDIAN_ROOT,
    ProfileRegistry,
    UnknownProfileError,
)
from ai_knowledge_pipeline.modules.profiles.types import KnowledgeProductProfile


__all__ = [
    "BUILTIN_PROFILES",
    "DEFAULT_PROFILE_ID",
    "KnowledgeProductProfile",
    "OBSIDIAN_ROOT",
    "ProfileRegistry",
    "UnknownProfileError",
]
