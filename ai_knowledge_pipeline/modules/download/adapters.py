"""yt-dlp adapter boundaries and runtime implementation."""

from __future__ import annotations

from ai_knowledge_pipeline.core.source import SourceData
from ai_knowledge_pipeline.modules.download.errors import (
    MediaDownloadErrorCode,
    MediaDownloadIssue,
)
from ai_knowledge_pipeline.modules.download.interfaces import (
    DownloadProcessRunner,
    MediaDownloadAdapter,
    YtDlpCommandBuilder,
)
from ai_knowledge_pipeline.modules.download.runner import SubprocessYtDlpRunner
from ai_knowledge_pipeline.modules.download.parsing import parse_ytdlp_output_path
from ai_knowledge_pipeline.modules.download.types import (
    DownloadCommand,
    DownloadProcessResult,
    MediaDownloadAdapterResult,
    MediaDownloadConfig,
    MediaDownloadPlan,
    MediaDownloadRequest,
)


class DefaultYtDlpCommandBuilder(YtDlpCommandBuilder):
    """Build yt-dlp arguments for future remote media materialization."""

    def build(
        self,
        source: SourceData,
        plan: MediaDownloadPlan,
        config: MediaDownloadConfig,
    ) -> DownloadCommand:
        args = [
            config.ytdlp_binary,
            "--no-playlist",
            "--paths",
            str(plan.target_path.parent),
            "--output",
            plan.target_path.name,
        ]
        if source.preferred_track == "audio":
            args.extend(["--extract-audio", "--audio-format", "m4a"])
        args.append(source.location.uri)
        return tuple(args)


class YtDlpRuntimeAdapter(MediaDownloadAdapter):
    """Materialize remote media by executing yt-dlp through a runner."""

    name = "yt-dlp"

    def __init__(
        self,
        runner: DownloadProcessRunner | None = None,
        command_builder: YtDlpCommandBuilder | None = None,
    ) -> None:
        self._runner = runner or SubprocessYtDlpRunner()
        self._command_builder = command_builder or DefaultYtDlpCommandBuilder()

    def download(
        self,
        request: MediaDownloadRequest,
        plan: MediaDownloadPlan,
    ) -> MediaDownloadAdapterResult:
        command = plan.command or self._command_builder.build(
            request.source,
            plan,
            request.config,
        )
        process_result = self._runner.run(command, request.config)
        if process_result.returncode != 0:
            return MediaDownloadAdapterResult(
                path=None,
                metadata=self._metadata(process_result),
                issues=(
                    MediaDownloadIssue(
                        code=self._error_code(process_result),
                        message="yt-dlp subprocess failed.",
                        field="returncode",
                        details={
                            "returncode": str(process_result.returncode),
                            "stderr": _excerpt(process_result.output.stderr),
                        },
                    ),
                ),
            )

        output_path = process_result.parsed_output_path or plan.target_path
        return MediaDownloadAdapterResult(
            path=output_path,
            metadata={
                **self._metadata(process_result),
                "materialized_path": str(output_path),
            },
        )

    def _metadata(self, process_result: DownloadProcessResult):
        return {
            "adapter": self.name,
            "command": list(process_result.command),
            "returncode": process_result.returncode,
            "stdout": process_result.output.stdout,
            "stderr": process_result.output.stderr,
        }

    def _error_code(
        self,
        process_result: DownloadProcessResult,
    ) -> MediaDownloadErrorCode:
        exception = process_result.metadata.get("exception")
        if exception == "FileNotFoundError":
            return MediaDownloadErrorCode.EXECUTABLE_NOT_FOUND
        if exception == "TimeoutExpired":
            return MediaDownloadErrorCode.SUBPROCESS_TIMEOUT
        return MediaDownloadErrorCode.SUBPROCESS_FAILED


def _excerpt(text: str, limit: int = 500) -> str:
    return text[-limit:] if len(text) > limit else text


__all__ = [
    "DefaultYtDlpCommandBuilder",
    "YtDlpRuntimeAdapter",
    "parse_ytdlp_output_path",
]
