"""Path planning for Obsidian notes."""

from __future__ import annotations

import re
from pathlib import Path

from ai_knowledge_pipeline.modules.obsidian.interfaces import ObsidianPathPlanner
from ai_knowledge_pipeline.modules.obsidian.types import ObsidianWriteRequest


class DefaultObsidianPathPlanner(ObsidianPathPlanner):
    """Plan categorized Obsidian note paths."""

    def plan_path(self, request: ObsidianWriteRequest) -> Path:
        config = request.config
        if config.vault_path is None:
            raise ValueError("vault_path is required")

        category = _category(request)
        title = str(
            request.markdown.frontmatter.get("title")
            or request.markdown.snapshot.metadata.title
            or request.markdown.markdown_artifact_id
        )
        extension = (
            config.file_extension
            if config.file_extension.startswith(".")
            else f".{config.file_extension}"
        )
        return (
            config.vault_path
            / config.root_dir
            / _slugify(category)
            / f"{_slugify(title)}{extension}"
        )


def _category(request: ObsidianWriteRequest) -> str:
    tags = request.markdown.frontmatter.get("tags")
    if isinstance(tags, tuple) and tags:
        return str(tags[0])
    return request.config.uncategorized_dir


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return slug.lower() or "untitled"


__all__ = ["DefaultObsidianPathPlanner"]
