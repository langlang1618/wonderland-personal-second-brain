"""Public contracts for the media download module."""

from ai_knowledge_pipeline.modules.download.adapters import (
    DefaultYtDlpCommandBuilder,
    YtDlpRuntimeAdapter,
    parse_ytdlp_output_path,
)
from ai_knowledge_pipeline.modules.download.downloader import (
    DefaultMediaDownloader,
    create_default_media_downloader,
)
from ai_knowledge_pipeline.modules.download.errors import (
    MediaDownloadErrorCode,
    MediaDownloadIssue,
    MediaDownloadIssueSeverity,
)
from ai_knowledge_pipeline.modules.download.interfaces import (
    MediaDownloadAdapter,
    MediaDownloader,
    MediaStoragePlanner,
    YtDlpCommandBuilder,
)
from ai_knowledge_pipeline.modules.download.storage import DefaultMediaStoragePlanner
from ai_knowledge_pipeline.modules.download.types import (
    DownloadAdapterName,
    DownloadCommand,
    LocalMediaArtifact,
    MediaArtifactId,
    MediaDownloadAdapterResult,
    MediaDownloadConfig,
    MediaDownloadMode,
    MediaDownloadPlan,
    MediaDownloadRequest,
    MediaDownloadResult,
    MediaDownloadStatus,
    DownloadProcessOutput,
    DownloadProcessResult,
)
from ai_knowledge_pipeline.modules.download.runner import SubprocessYtDlpRunner

__all__ = [
    "DefaultMediaDownloader",
    "DefaultMediaStoragePlanner",
    "DefaultYtDlpCommandBuilder",
    "DownloadProcessOutput",
    "DownloadProcessResult",
    "DownloadAdapterName",
    "DownloadCommand",
    "LocalMediaArtifact",
    "MediaArtifactId",
    "MediaDownloadAdapter",
    "MediaDownloadAdapterResult",
    "MediaDownloadConfig",
    "MediaDownloadErrorCode",
    "MediaDownloadIssue",
    "MediaDownloadIssueSeverity",
    "MediaDownloadMode",
    "MediaDownloadPlan",
    "MediaDownloadRequest",
    "MediaDownloadResult",
    "MediaDownloadStatus",
    "MediaDownloader",
    "MediaStoragePlanner",
    "YtDlpCommandBuilder",
    "YtDlpRuntimeAdapter",
    "create_default_media_downloader",
    "parse_ytdlp_output_path",
    "SubprocessYtDlpRunner",
]
