# Batch Course Pipeline

## Scope

`scripts/run_batch_course_pipeline.py` processes a directory of local transcript
exports. Each `.txt` or `.srt` file becomes one Obsidian Markdown note.

```text
transcript directory
-> scan .txt/.srt files
-> natural sort
-> run real course pipeline for each file
-> write Obsidian notes
-> print batch summary
```

The batch runner does not implement RAG, embeddings, Agent Memory persistence,
yt-dlp, ffmpeg, queues, concurrency, or Whisper execution.

## Usage

```bash
venv/bin/python scripts/run_batch_course_pipeline.py \
  --input-dir /Users/langlang/Documents/course_transcripts \
  --vault /path/to/ObsidianVault \
  --profile finance \
  --tags "有钱有闲,金融学习,课程" \
  --title-prefix "26.5.10直播" \
  --model deepseek-v4-flash
```

With `--title-prefix "26.5.10直播"`:

```text
output_000.txt -> 26.5.10直播 001
output_001.txt -> 26.5.10直播 002
output_002.txt -> 26.5.10直播 003
```

The Obsidian writer slugifies note filenames, so these become paths such as:

```text
26-5-10直播-001.md
26-5-10直播-002.md
26-5-10直播-003.md
```

## Options

- `--input-dir`: directory containing transcript files.
- `--vault`: Obsidian vault path. Falls back to `OBSIDIAN_VAULT_PATH`.
- `--profile`: `finance`, `ai`, `startup`, or `custom`.
- `--tags`: comma-separated tags for generated notes.
- `--title-prefix`: prefix used to generate numbered titles.
- `--model`: DeepSeek model. Falls back to `DEEPSEEK_MODEL`.
- `--limit`: process only the first N naturally sorted files.
- `--dry-run`: print planned files without calling DeepSeek or writing notes.
- `--skip-existing`: skip files whose expected note path already exists.

## Sorting

Files are sorted by natural filename order:

```text
output_000.txt
output_001.txt
output_002.txt
output_010.txt
```

Supported suffixes:

- `.txt`
- `.srt`

## Dry Run

```bash
venv/bin/python scripts/run_batch_course_pipeline.py \
  --input-dir /Users/langlang/Documents/course_transcripts \
  --vault /path/to/ObsidianVault \
  --title-prefix "26.5.10直播" \
  --limit 3 \
  --dry-run
```

Dry run does not call DeepSeek and does not write to Obsidian.

## Skip Existing

`--skip-existing` checks the expected note path before running the single-file
pipeline. If the note already exists, that item is marked skipped and the batch
continues.

## Summary

Each item prints:

- current index
- transcript path
- generated or expected note path
- status
- message

At the end, the runner prints:

- total
- success
- failed
- skipped
- generated note paths

Per-file failures do not stop the batch. Failed items are recorded in the
summary and the next transcript continues.

## Secrets

The batch runner reads the same environment as the single-file runner. It does
not print API keys and does not modify `.env`.
