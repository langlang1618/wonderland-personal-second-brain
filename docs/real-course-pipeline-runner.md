# Real Course Pipeline Runner

## Scope

`scripts/run_real_course_pipeline.py` runs one real local course transcript
through the existing pipeline modules.

```text
local_transcript_path
-> LocalWhisperProvider
-> TranscriptArtifact
-> DeepSeekCleaningProvider
-> CleanedTranscriptArtifact
-> MarkdownGenerator
-> MarkdownArtifact
-> ObsidianWriter
-> ObsidianNoteArtifact
```

It is intentionally a single-course runner. It does not implement batch
processing, RAG, embeddings, yt-dlp, ffmpeg, queueing, or parallel execution.

## Inputs

Required:

- `--transcript`: local `.txt` or `.srt` transcript export.
- `--vault`: Obsidian vault path, or `OBSIDIAN_VAULT_PATH` in `.env`.

Optional:

- `--audio`: local audio path used as the chunk reference.
- `--title`: title hint for the cleaning prompt.
- `--tags`: comma-separated note tags.
- `--model`: DeepSeek model override.
- `--profile`: cleaning profile: `finance`, `ai`, `startup`, or `custom`.
- `--profile-path`: custom Markdown prompt path for `--profile custom`.

## Environment

The runner reads `.env` without printing secret values.

```bash
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
OBSIDIAN_VAULT_PATH=
```

Defaults:

- `DEEPSEEK_BASE_URL`: `https://api.deepseek.com`
- `DEEPSEEK_MODEL`: `deepseek-v4-flash`

`DEEPSEEK_API_KEY` is required when using the real provider.

## Usage

With vault path from `.env`:

```bash
venv/bin/python scripts/run_real_course_pipeline.py \
  --transcript /path/to/course01.srt \
  --title "Course 01" \
  --tags ai,course,obsidian \
  --profile ai
```

With explicit vault:

```bash
venv/bin/python scripts/run_real_course_pipeline.py \
  --transcript /path/to/course01.txt \
  --vault /path/to/ObsidianVault \
  --audio /path/to/course01.mp3 \
  --title "Course 01" \
  --tags ai,course \
  --profile finance \
  --model deepseek-v4-flash
```

On success, the script prints only the generated Obsidian note path.

## Error Handling

The runner exits with a clear error when:

- transcript file is missing
- transcript suffix is not `.txt` or `.srt`
- optional audio path is provided but missing
- Obsidian vault path does not exist
- `DEEPSEEK_API_KEY` is missing
- transcript import, cleaning, Markdown generation, or Obsidian writing fails

API keys are never printed.

## Testing

Unit tests mock the DeepSeek provider and use `tmp_path` as a fake vault. They
do not call the network and do not use real API keys.
