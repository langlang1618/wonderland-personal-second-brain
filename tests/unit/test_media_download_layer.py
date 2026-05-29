from pathlib import Path

from ai_knowledge_pipeline.core.artifact import ArtifactStatus
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.core.source import (
    MediaKind,
    SourceAccess,
    SourceData,
    SourceKind,
    SourceLocation,
    SourceMetadata,
)
from ai_knowledge_pipeline.modules.download.contracts import (
    MediaDownloadAdapterResult,
    MediaDownloadConfig,
    MediaDownloadErrorCode,
    MediaDownloadMode,
    MediaDownloadRequest,
    MediaDownloadStatus,
    create_default_media_downloader,
)


class FakeRemoteAdapter:
    name = "fake-yt-dlp"

    def download(self, request, plan):
        return MediaDownloadAdapterResult(
            path=Path("data/media/downloaded.m4a"),
            metadata={"adapter": self.name},
        )


def youtube_source() -> SourceData:
    return SourceData(
        source_id="src_youtube_1",
        kind=SourceKind.YOUTUBE,
        media_kind=MediaKind.VIDEO,
        location=SourceLocation(
            access=SourceAccess.REMOTE,
            uri="https://www.youtube.com/watch?v=abc",
        ),
        metadata=SourceMetadata(title="Lecture", language="en", tags=("ai",)),
    )


def local_audio_source() -> SourceData:
    return SourceData(
        source_id="src_audio_1",
        kind=SourceKind.LOCAL_AUDIO,
        media_kind=MediaKind.AUDIO,
        location=SourceLocation(
            access=SourceAccess.LOCAL,
            uri="audio/session.mp3",
            path=Path("audio/session.mp3"),
        ),
    )


def test_local_audio_returns_local_reference_artifact_without_file_io() -> None:
    downloader = create_default_media_downloader()
    result = downloader.download(MediaDownloadRequest(source=local_audio_source()))

    assert result.is_success
    assert result.status is MediaDownloadStatus.LOCAL_REFERENCE
    assert result.artifact is not None
    assert result.artifact.path == Path("audio/session.mp3")
    assert result.artifact.snapshot.kind is ArtifactKind.MEDIA
    assert result.artifact.snapshot.status is ArtifactStatus.REGISTERED
    assert result.artifact.snapshot.lineage.source_id == "src_audio_1"


def test_remote_dry_run_builds_plan_and_command_without_adapter() -> None:
    downloader = create_default_media_downloader()
    request = MediaDownloadRequest(
        source=youtube_source(),
        config=MediaDownloadConfig(mode=MediaDownloadMode.DRY_RUN),
    )

    result = downloader.download(request)

    assert result.is_success
    assert result.status is MediaDownloadStatus.PLANNED
    assert result.plan.adapter_name == "yt-dlp"
    assert result.plan.command[0] == "yt-dlp"
    assert "https://www.youtube.com/watch?v=abc" in result.plan.command
    assert result.artifact is not None
    assert result.artifact.snapshot.status is ArtifactStatus.DECLARED


def test_remote_metadata_only_does_not_require_adapter() -> None:
    downloader = create_default_media_downloader()
    request = MediaDownloadRequest(
        source=youtube_source(),
        config=MediaDownloadConfig(mode=MediaDownloadMode.METADATA_ONLY),
    )

    result = downloader.download(request)

    assert result.is_success
    assert result.status is MediaDownloadStatus.METADATA_ONLY
    assert result.artifact is not None
    assert result.artifact.metadata["mode"] == "metadata_only"


def test_remote_materialize_requires_adapter() -> None:
    downloader = create_default_media_downloader()
    result = downloader.download(MediaDownloadRequest(source=youtube_source()))

    assert not result.is_success
    assert result.status is MediaDownloadStatus.FAILED
    assert result.issues[0].code is MediaDownloadErrorCode.ADAPTER_REQUIRED


def test_remote_materialize_uses_injected_adapter() -> None:
    downloader = create_default_media_downloader(remote_adapter=FakeRemoteAdapter())
    result = downloader.download(MediaDownloadRequest(source=youtube_source()))

    assert result.is_success
    assert result.status is MediaDownloadStatus.DOWNLOADED
    assert result.artifact is not None
    assert result.artifact.path == Path("data/media/downloaded.m4a")
    assert result.artifact.snapshot.status is ArtifactStatus.MATERIALIZED
    assert result.artifact.snapshot.metadata.extra["adapter"] == "fake-yt-dlp"


def test_remote_path_strategy_is_configurable() -> None:
    downloader = create_default_media_downloader()
    request = MediaDownloadRequest(
        source=youtube_source(),
        config=MediaDownloadConfig(
            mode=MediaDownloadMode.DRY_RUN,
            media_dir=Path("custom-media"),
            output_template="{source_id}.download",
        ),
    )

    result = downloader.download(request)

    assert result.plan.target_path == Path("custom-media/src_youtube_1.download")
