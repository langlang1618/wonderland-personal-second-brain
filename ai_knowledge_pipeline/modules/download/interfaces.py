"""Protocol boundaries for the media download layer."""

from __future__ import annotations

from typing import Protocol

from ai_knowledge_pipeline.core.source import SourceData
from ai_knowledge_pipeline.modules.download.types import (
    DownloadCommand,
    MediaDownloadAdapterResult,
    DownloadProcessResult,
    MediaDownloadConfig,
    MediaDownloadPlan,
    MediaDownloadRequest,
    MediaDownloadResult,
)


class MediaStoragePlanner(Protocol):
    """Plan local paths for downloaded or referenced media."""

    def plan(self, request: MediaDownloadRequest) -> MediaDownloadPlan:
        """Return a pure storage plan without creating files."""


class MediaDownloadAdapter(Protocol):
    """Boundary for concrete remote download adapters."""

    name: str

    def download(
        self,
        request: MediaDownloadRequest,
        plan: MediaDownloadPlan,
    ) -> MediaDownloadAdapterResult:
        """Materialize remote media according to a plan."""


class YtDlpCommandBuilder(Protocol):
    """Build yt-dlp command arguments without executing them."""

    def build(
        self,
        source: SourceData,
        plan: MediaDownloadPlan,
        config: MediaDownloadConfig,
    ) -> DownloadCommand:
        """Return command arguments for a future yt-dlp subprocess adapter."""


class DownloadProcessRunner(Protocol):
    """Execute a prepared download command."""

    def run(
        self,
        command: DownloadCommand,
        config: MediaDownloadConfig,
    ) -> DownloadProcessResult:
        """Run a command and return structured subprocess output."""


class MediaDownloader(Protocol):
    """Top-level media download boundary."""

    def download(self, request: MediaDownloadRequest) -> MediaDownloadResult:
        """Convert SourceData into a LocalMediaArtifact."""


__all__ = [
    "MediaDownloadAdapter",
    "MediaDownloader",
    "MediaStoragePlanner",
    "DownloadProcessRunner",
    "YtDlpCommandBuilder",
]
