"""Subprocess runner for yt-dlp.

This module is the only place in the download layer that talks to subprocess.
It returns structured output and maps exceptions into download result objects.
"""

from __future__ import annotations

import subprocess

from ai_knowledge_pipeline.modules.download.parsing import parse_ytdlp_output_path
from ai_knowledge_pipeline.modules.download.types import (
    DownloadCommand,
    DownloadProcessOutput,
    DownloadProcessResult,
    MediaDownloadConfig,
)


class SubprocessYtDlpRunner:
    """Execute yt-dlp commands with captured stdout and stderr."""

    def run(
        self,
        command: DownloadCommand,
        config: MediaDownloadConfig,
    ) -> DownloadProcessResult:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=config.subprocess_timeout_seconds,
            )
        except FileNotFoundError as exc:
            stderr = str(exc)
            return DownloadProcessResult(
                command=command,
                returncode=127,
                output=_output("", stderr),
                metadata={"exception": "FileNotFoundError"},
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _decode_timeout_output(exc.stdout)
            stderr = _decode_timeout_output(exc.stderr)
            return DownloadProcessResult(
                command=command,
                returncode=124,
                output=_output(stdout, stderr),
                metadata={"exception": "TimeoutExpired"},
            )
        except OSError as exc:
            stderr = str(exc)
            return DownloadProcessResult(
                command=command,
                returncode=1,
                output=_output("", stderr),
                metadata={"exception": exc.__class__.__name__},
            )

        combined_output = "\n".join(
            value for value in (completed.stdout, completed.stderr) if value
        )
        return DownloadProcessResult(
            command=command,
            returncode=completed.returncode,
            output=_output(completed.stdout, completed.stderr),
            parsed_output_path=parse_ytdlp_output_path(combined_output),
        )


def _output(stdout: str, stderr: str) -> DownloadProcessOutput:
    return DownloadProcessOutput(
        stdout=stdout,
        stderr=stderr,
        stdout_lines=tuple(stdout.splitlines()),
        stderr_lines=tuple(stderr.splitlines()),
    )


def _decode_timeout_output(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


__all__ = ["SubprocessYtDlpRunner"]
