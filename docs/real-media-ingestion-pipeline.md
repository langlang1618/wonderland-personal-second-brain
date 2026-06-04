# Real Media Ingestion Pipeline

## Scope

`scripts/run_media_ingestion.py` handles upstream media ingestion only:

```text
m3u8
-> yt-dlp audio download
-> ffmpeg audio chunking
-> manifest.json
```

It does not run Whisper, DeepSeek cleaning, Markdown generation, Obsidian
writing, RAG, embeddings, queues, concurrency, or Agent Memory.

## Inputs

Single m3u8:

```bash
venv/bin/python scripts/run_media_ingestion.py \
  --m3u8 "https://example.com/course/index.m3u8" \
  --output-dir data/media_ingestion \
  --title "课程名" \
  --audio-format mp3 \
  --chunk-minutes 30
```

Multiple URLs:

```bash
venv/bin/python scripts/run_media_ingestion.py \
  --url-file /path/to/m3u8-urls.txt \
  --output-dir data/media_ingestion \
  --title "课程名" \
  --audio-format mp3 \
  --chunk-minutes 30
```

The URL file should contain one URL per line. Blank lines and lines starting
with `#` are ignored.

## Output Layout

```text
data/media_ingestion/
  课程名/
    raw_audio/
      course.mp3
    chunks/
      chunk_001.mp3
      chunk_002.mp3
      chunk_003.mp3
    manifest.json
```

For multiple URLs with `--title "课程名"`, output directories are numbered:

```text
课程名-001/
课程名-002/
课程名-003/
```

## Manifest

Each course directory contains `manifest.json`:

```json
{
  "source_url": "...",
  "title": "课程名",
  "downloaded_audio_path": ".../raw_audio/course.mp3",
  "chunk_paths": [".../chunks/chunk_001.mp3"],
  "chunk_minutes": 30,
  "audio_format": "mp3",
  "created_at": "2026-06-05T00:00:00+00:00",
  "status": "materialized",
  "errors": []
}
```

## Dry Run

```bash
venv/bin/python scripts/run_media_ingestion.py \
  --m3u8 "https://example.com/course/index.m3u8" \
  --title "课程名" \
  --dry-run
```

Dry run writes a planned manifest, but does not call yt-dlp or ffmpeg.

## Skip Existing

`--skip-existing` skips an item when both the raw audio file and at least one
chunk already exist.

```bash
venv/bin/python scripts/run_media_ingestion.py \
  --m3u8 "https://example.com/course/index.m3u8" \
  --title "课程名" \
  --skip-existing
```

## Error Handling

If yt-dlp or ffmpeg fails, the item is marked failed and the error is recorded
in that item's manifest. For `--url-file`, one failed URL does not stop the next
URL from being processed.

The terminal display strips query parameters from URLs and truncates long URLs.
Full source URLs are still recorded in `manifest.json` for traceability.
