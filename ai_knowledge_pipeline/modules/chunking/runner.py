"""Subprocess runner for ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ai_knowledge_pipeline.modules.chunking.types import (
    ChunkCommand,
    ChunkProcessOutput,
    ChunkProcessResult,
    MediaChunkingConfig,
)


class SubprocessFfmpegRunner:
    """Execute ffmpeg commands with captured stdout and stderr."""

    def run(
        self,
        command: ChunkCommand,
        config: MediaChunkingConfig,
    ) -> ChunkProcessResult:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=config.subprocess_timeout_seconds,
            )
        except FileNotFoundError as exc:
            return ChunkProcessResult(
                command=command,
                returncode=127,
                output=_output("", str(exc)),
                output_path=_output_path(command),
                metadata={"exception": "FileNotFoundError"},
            )
        except subprocess.TimeoutExpired as exc:
            return ChunkProcessResult(
                command=command,
                returncode=124,
                output=_output(
                    _decode_timeout_output(exc.stdout),
                    _decode_timeout_output(exc.stderr),
                ),
                output_path=_output_path(command),
                metadata={"exception": "TimeoutExpired"},
            )
        except OSError as exc:
            return ChunkProcessResult(
                command=command,
                returncode=1,
                output=_output("", str(exc)),
                output_path=_output_path(command),
                metadata={"exception": exc.__class__.__name__},
            )

        return ChunkProcessResult(
            command=command,
            returncode=completed.returncode,
            output=_output(completed.stdout, completed.stderr),
            output_path=_output_path(command),
        )


def _output(stdout: str, stderr: str) -> ChunkProcessOutput:
    return ChunkProcessOutput(
        stdout=stdout,
        stderr=stderr,
        stdout_lines=tuple(stdout.splitlines()),
        stderr_lines=tuple(stderr.splitlines()),
    )


def _output_path(command: ChunkCommand) -> Path | None:
    if not command:
        return None
    return Path(command[-1])


def _decode_timeout_output(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


__all__ = ["SubprocessFfmpegRunner"]
