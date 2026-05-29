import subprocess
from pathlib import Path

from ai_knowledge_pipeline.core.artifact import (
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.modules.chunking.contracts import (
    DefaultFfmpegCommandBuilder,
    FfmpegRuntimeAdapter,
    FixedDurationTimelineSegmenter,
    MediaChunkingConfig,
    MediaChunkingErrorCode,
    MediaChunkingMode,
    MediaChunkingRequest,
    MediaChunkingStatus,
    SubprocessFfmpegRunner,
    create_default_media_chunker,
)
from ai_knowledge_pipeline.modules.chunking.types import (
    ChunkProcessOutput,
    ChunkProcessResult,
)
from ai_knowledge_pipeline.modules.download.types import (
    LocalMediaArtifact,
    MediaDownloadStatus,
)


def media_artifact() -> LocalMediaArtifact:
    snapshot = ArtifactSnapshot(
        artifact_id="media_src_1",
        snapshot_id="media_src_1_v1",
        kind=ArtifactKind.MEDIA,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/media/src_1.m4a",
            path=Path("data/media/src_1.m4a"),
            media_type="audio/*",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(source_id="src_1"),
        metadata=ArtifactMetadata(title="Lecture", language="en", tags=("ai",)),
    )
    return LocalMediaArtifact(
        media_artifact_id="media_src_1",
        source_id="src_1",
        status=MediaDownloadStatus.DOWNLOADED,
        path=Path("data/media/src_1.m4a"),
        uri="file://data/media/src_1.m4a",
        snapshot=snapshot,
    )


class FakeFfmpegRunner:
    def run(self, command, config):
        return ChunkProcessResult(
            command=command,
            returncode=0,
            output=ChunkProcessOutput(stdout="ok\n", stdout_lines=("ok",)),
            output_path=Path(command[-1]),
        )


class FakeFailedFfmpegRunner:
    def run(self, command, config):
        return ChunkProcessResult(
            command=command,
            returncode=1,
            output=ChunkProcessOutput(stderr="ffmpeg failed"),
            output_path=Path(command[-1]),
        )


def test_fixed_duration_segmenter_creates_tail_segment() -> None:
    segments = FixedDurationTimelineSegmenter().segment(
        duration_seconds=3700,
        config=MediaChunkingConfig(chunk_duration_seconds=1800),
    )

    assert len(segments) == 3
    assert segments[0].start_time == 0
    assert segments[0].end_time == 1800
    assert segments[2].start_time == 3600
    assert segments[2].end_time == 3700
    assert segments[2].duration == 100


def test_dry_run_generates_chunk_artifacts_with_lineage() -> None:
    chunker = create_default_media_chunker()
    request = MediaChunkingRequest(
        media=media_artifact(),
        media_duration_seconds=3700,
        config=MediaChunkingConfig(
            mode=MediaChunkingMode.DRY_RUN,
            chunk_duration_seconds=1800,
        ),
        run_id="run_1",
        job_id="job_1",
        task_id="task_chunk_1",
    )

    result = chunker.chunk(request)

    assert result.is_success
    assert result.status is MediaChunkingStatus.PLANNED
    assert len(result.chunks) == 3
    first = result.chunks[0]
    assert first.chunk_index == 0
    assert first.start_time == 0
    assert first.end_time == 1800
    assert first.duration == 1800
    assert first.snapshot.kind is ArtifactKind.CHUNK
    assert first.snapshot.lineage.input_snapshot_ids == ("media_src_1_v1",)
    assert first.snapshot.lineage.upstream_artifact_ids == ("media_src_1",)
    assert first.snapshot.metadata.chunk_count == 3


def test_missing_duration_returns_structured_error() -> None:
    chunker = create_default_media_chunker()
    result = chunker.chunk(MediaChunkingRequest(media=media_artifact()))

    assert not result.is_success
    assert result.status is MediaChunkingStatus.FAILED
    assert result.issues[0].code is MediaChunkingErrorCode.MISSING_MEDIA_DURATION


def test_ffmpeg_command_builder_uses_configured_binary_and_paths() -> None:
    chunker = create_default_media_chunker()
    request = MediaChunkingRequest(
        media=media_artifact(),
        media_duration_seconds=1800,
        config=MediaChunkingConfig(
            mode=MediaChunkingMode.DRY_RUN,
            ffmpeg_binary="/opt/bin/ffmpeg",
            chunks_dir=Path("custom-chunks"),
            output_extension=".wav",
        ),
    )
    result = chunker.chunk(request)
    assert result.plan is not None

    commands = DefaultFfmpegCommandBuilder().build(request, result.plan)

    assert commands[0][0] == "/opt/bin/ffmpeg"
    assert "-ss" in commands[0]
    assert "-t" in commands[0]
    assert commands[0][-1] == "custom-chunks/src_1/chunk_0000.wav"


def test_ffmpeg_runtime_adapter_uses_runner_outputs() -> None:
    adapter = FfmpegRuntimeAdapter(runner=FakeFfmpegRunner())
    chunker = create_default_media_chunker(adapter=adapter)
    request = MediaChunkingRequest(
        media=media_artifact(),
        media_duration_seconds=3600,
        config=MediaChunkingConfig(chunk_duration_seconds=1800),
    )

    result = chunker.chunk(request)

    assert result.is_success
    assert result.status is MediaChunkingStatus.MATERIALIZED
    assert len(result.chunks) == 2
    assert result.chunks[0].path == Path("data/chunks/src_1/chunk_0000.m4a")
    assert result.chunks[0].snapshot.status is ArtifactStatus.MATERIALIZED


def test_ffmpeg_runtime_adapter_maps_failure_to_structured_issue() -> None:
    adapter = FfmpegRuntimeAdapter(runner=FakeFailedFfmpegRunner())
    chunker = create_default_media_chunker(adapter=adapter)
    request = MediaChunkingRequest(
        media=media_artifact(),
        media_duration_seconds=1800,
    )

    result = chunker.chunk(request)

    assert not result.is_success
    assert result.status is MediaChunkingStatus.FAILED
    assert result.issues[0].code is MediaChunkingErrorCode.SUBPROCESS_FAILED


def test_materialize_requires_adapter() -> None:
    chunker = create_default_media_chunker()
    result = chunker.chunk(
        MediaChunkingRequest(
            media=media_artifact(),
            media_duration_seconds=1800,
        )
    )

    assert not result.is_success
    assert result.issues[0].code is MediaChunkingErrorCode.ADAPTER_REQUIRED


def test_subprocess_ffmpeg_runner_captures_structured_output(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="",
            stderr="ffmpeg progress\n",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SubprocessFfmpegRunner().run(
        ("ffmpeg", "-i", "in.m4a", "out.m4a"),
        MediaChunkingConfig(),
    )

    assert result.returncode == 0
    assert result.output.stderr_lines == ("ffmpeg progress",)
    assert result.output_path == Path("out.m4a")


def test_subprocess_ffmpeg_runner_maps_missing_executable(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SubprocessFfmpegRunner().run(("ffmpeg", "x"), MediaChunkingConfig())

    assert result.returncode == 127
    assert result.metadata["exception"] == "FileNotFoundError"
