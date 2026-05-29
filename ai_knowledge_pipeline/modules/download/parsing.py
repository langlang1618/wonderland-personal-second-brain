"""Parsing helpers for yt-dlp structured output."""

from __future__ import annotations

from pathlib import Path


def parse_ytdlp_output_path(output: str) -> Path | None:
    """Parse a likely materialized output path from yt-dlp output."""

    prefixes = (
        "[ExtractAudio] Destination:",
        "[Merger] Merging formats into",
        "[download] Destination:",
        "Destination:",
    )
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        for prefix in prefixes:
            if stripped.startswith(prefix):
                value = stripped.removeprefix(prefix).strip().strip('"')
                if value:
                    return Path(value)
    return None


__all__ = ["parse_ytdlp_output_path"]
