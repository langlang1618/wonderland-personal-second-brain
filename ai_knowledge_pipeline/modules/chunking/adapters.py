"""ffmpeg command builder and runtime adapter."""

from __future__ import annotations

from ai_knowledge_pipeline.modules.chunking.errors import (
    MediaChunkingErrorCode,
    MediaChunkingIssue,
)
from ai_knowledge_pipeline.modules.chunking.interfaces import (
    ChunkProcessRunner,
    FfmpegCommandBuilder,
    MediaChunkingAdapter,
)
from ai_knowledge_pipeline.modules.chunking.planner import chunk_output_path
from ai_knowledge_pipeline.modules.chunking.runner import SubprocessFfmpegRunner
from ai_knowledge_pipeline.modules.chunking.types import (
    ChunkCommand,
    ChunkProcessResult,
    MediaChunkAdapterResult,
    MediaChunkPlan,
    MediaChunkingRequest,
)


class DefaultFfmpegCommandBuilder(FfmpegCommandBuilder):
    """Build one ffmpeg command per planned timeline segment."""

    def build(
        self,
        request: MediaChunkingRequest,
        plan: MediaChunkPlan,
    ) -> tuple[ChunkCommand, ...]:
        commands: list[ChunkCommand] = []
        for segment in plan.segments:
            output_path = chunk_output_path(
                plan.chunks_dir,
                plan.source_id,
                segment.chunk_index,
                request.config.output_extension,
            )
            commands.append(
                (
                    request.config.ffmpeg_binary,
                    "-y",
                    "-ss",
                    _format_seconds(segment.start_time),
                    "-i",
                    str(plan.input_path),
                    "-t",
                    _format_seconds(segment.duration),
                    "-c",
                    "copy",
                    str(output_path),
                )
            )
        return tuple(commands)


class FfmpegRuntimeAdapter(MediaChunkingAdapter):
    """Materialize chunk files by executing ffmpeg through a runner."""

    name = "ffmpeg"

    def __init__(
        self,
        runner: ChunkProcessRunner | None = None,
        command_builder: FfmpegCommandBuilder | None = None,
    ) -> None:
        self._runner = runner or SubprocessFfmpegRunner()
        self._command_builder = command_builder or DefaultFfmpegCommandBuilder()

    def chunk(
        self,
        request: MediaChunkingRequest,
        plan: MediaChunkPlan,
    ) -> MediaChunkAdapterResult:
        commands = plan.commands or self._command_builder.build(request, plan)
        output_paths = []
        metadata = {"adapter": self.name, "command_count": len(commands)}

        for command in commands:
            process_result = self._runner.run(command, request.config)
            if process_result.returncode != 0:
                return MediaChunkAdapterResult(
                    output_paths=tuple(output_paths),
                    metadata={**metadata, **_process_metadata(process_result)},
                    issues=(
                        MediaChunkingIssue(
                            code=_error_code(process_result),
                            message="ffmpeg subprocess failed.",
                            field="returncode",
                            details={
                                "returncode": str(process_result.returncode),
                                "stderr": _excerpt(process_result.output.stderr),
                            },
                        ),
                    ),
                )
            if process_result.output_path is not None:
                output_paths.append(process_result.output_path)
            else:
                output_paths.append(_command_output_path(command))

        return MediaChunkAdapterResult(
            output_paths=tuple(output_paths),
            metadata=metadata,
        )


def _command_output_path(command: ChunkCommand):
    from pathlib import Path

    return Path(command[-1])


def _format_seconds(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _process_metadata(process_result: ChunkProcessResult):
    return {
        "returncode": process_result.returncode,
        "stdout": process_result.output.stdout,
        "stderr": process_result.output.stderr,
    }


def _error_code(process_result: ChunkProcessResult) -> MediaChunkingErrorCode:
    exception = process_result.metadata.get("exception")
    if exception == "FileNotFoundError":
        return MediaChunkingErrorCode.EXECUTABLE_NOT_FOUND
    if exception == "TimeoutExpired":
        return MediaChunkingErrorCode.SUBPROCESS_TIMEOUT
    return MediaChunkingErrorCode.SUBPROCESS_FAILED


def _excerpt(text: str, limit: int = 500) -> str:
    return text[-limit:] if len(text) > limit else text


__all__ = ["DefaultFfmpegCommandBuilder", "FfmpegRuntimeAdapter"]
