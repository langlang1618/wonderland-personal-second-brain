"""Storage path planning for media downloads."""

from __future__ import annotations

from pathlib import Path

from ai_knowledge_pipeline.core.source import SourceAccess, SourceKind
from ai_knowledge_pipeline.modules.download.interfaces import MediaStoragePlanner
from ai_knowledge_pipeline.modules.download.types import (
    MediaDownloadPlan,
    MediaDownloadRequest,
)


class DefaultMediaStoragePlanner(MediaStoragePlanner):
    """Plan deterministic media output paths without touching the filesystem."""

    def plan(self, request: MediaDownloadRequest) -> MediaDownloadPlan:
        source = request.source
        adapter_name = self._adapter_name(source.kind)
        target_path = self._target_path(request)
        temp_path = request.config.temp_dir / source.source_id

        return MediaDownloadPlan(
            source_id=source.source_id,
            adapter_name=adapter_name,
            target_path=target_path,
            temp_path=temp_path,
            mode=request.config.mode,
            metadata={
                "source_kind": source.kind.value,
                "source_access": source.location.access.value,
            },
        )

    def _target_path(self, request: MediaDownloadRequest) -> Path:
        source = request.source
        if (
            source.location.access is SourceAccess.LOCAL
            and request.config.keep_original_local_path
            and source.location.path is not None
        ):
            return source.location.path

        template = request.config.output_template.format(source_id=source.source_id)
        if "%(ext)s" in template:
            return request.config.media_dir / template.replace("%(ext)s", "media")

        return request.config.media_dir / template

    def _adapter_name(self, kind: SourceKind) -> str:
        if kind in {SourceKind.YOUTUBE, SourceKind.M3U8}:
            return "yt-dlp"
        if kind in {SourceKind.LOCAL_AUDIO, SourceKind.LOCAL_VIDEO}:
            return "local"
        return "unsupported"


__all__ = ["DefaultMediaStoragePlanner"]
