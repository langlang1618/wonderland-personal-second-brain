"""Pure local rules for source detection.

These rules do not access the network, inspect file contents, or check whether
local paths exist. They are intentionally small so new source families can be
added without changing the normalizer orchestration.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import ParseResult


YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }
)

AUDIO_EXTENSIONS = frozenset(
    {
        ".aac",
        ".aiff",
        ".flac",
        ".m4a",
        ".mp3",
        ".ogg",
        ".opus",
        ".wav",
        ".wma",
    }
)

VIDEO_EXTENSIONS = frozenset(
    {
        ".avi",
        ".flv",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp4",
        ".webm",
        ".wmv",
    }
)

REMOTE_URL_SCHEMES = frozenset({"http", "https"})


def normalized_host(parsed_url: ParseResult) -> str:
    """Return a normalized URL hostname."""

    return (parsed_url.hostname or "").lower()


def is_remote_url(parsed_url: ParseResult) -> bool:
    """Return whether a parsed URL uses a supported remote scheme."""

    return parsed_url.scheme.lower() in REMOTE_URL_SCHEMES and bool(
        parsed_url.netloc
    )


def is_file_url(parsed_url: ParseResult) -> bool:
    """Return whether a parsed URL is a local file URL."""

    return parsed_url.scheme.lower() == "file"


def is_youtube_host(host: str) -> bool:
    """Return whether host belongs to a supported YouTube URL family."""

    return host in YOUTUBE_HOSTS


def is_m3u8_path(path: str) -> bool:
    """Return whether a URL path looks like an m3u8 manifest."""

    return ".m3u8" in path.lower()


def local_suffix(raw_input: str) -> str:
    """Return a lowercase suffix for a local path-like input."""

    return Path(raw_input).suffix.lower()


def is_audio_suffix(suffix: str) -> bool:
    """Return whether a suffix is a known audio extension."""

    return suffix in AUDIO_EXTENSIONS


def is_video_suffix(suffix: str) -> bool:
    """Return whether a suffix is a known video extension."""

    return suffix in VIDEO_EXTENSIONS


__all__ = [
    "AUDIO_EXTENSIONS",
    "REMOTE_URL_SCHEMES",
    "VIDEO_EXTENSIONS",
    "YOUTUBE_HOSTS",
    "is_audio_suffix",
    "is_file_url",
    "is_m3u8_path",
    "is_remote_url",
    "is_video_suffix",
    "is_youtube_host",
    "local_suffix",
    "normalized_host",
]
