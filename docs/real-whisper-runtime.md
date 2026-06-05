# Real Whisper Runtime

## Scope

`v1.1 Real Whisper Runtime` transcribes local audio chunks with
`faster-whisper`.

```text
chunk_001.mp3
-> FasterWhisperProvider
-> chunk_001.txt

chunk_002.mp3
-> FasterWhisperProvider
-> chunk_002.txt
-> merged_transcript.txt
```

This layer does not use OpenAI Whisper API, Groq, DeepSeek cleaning, Markdown,
Obsidian, RAG, embeddings, queues, or concurrency.

## Install

Install `faster-whisper` in the project virtual environment:

```bash
venv/bin/python -m pip install faster-whisper
```

## Provider

`FasterWhisperProvider` implements the existing `TranscriptionProvider`
protocol. The protocol is unchanged.

Supported model sizes:

- `tiny`
- `base`
- `small`
- `medium`

Default:

```text
small
```

Default language:

```text
zh
```

The provider returns `ProviderTranscriptionResult` with plain text and
timestamped segments. `DefaultTranscriber` continues to materialize
`TranscriptArtifact` and preserve lineage to the parent chunk artifact.

## Script

```bash
venv/bin/python scripts/run_local_whisper_transcription.py \
  --chunks-dir data/media_ingestion/测试课程/chunks \
  --output-dir data/transcripts \
  --model-size small \
  --language zh \
  --merge
```

Output:

```text
data/transcripts/
  chunk_001.txt
  chunk_002.txt
  merged_transcript.txt
  manifest.json
```

## Manifest

`manifest.json` records:

- model
- language
- chunk count
- transcript files
- merged transcript path
- created_at
- errors

## Error Handling

Structured transcription issues are returned for:

- missing audio chunk path
- missing `faster-whisper` package
- model load or download failure
- damaged audio or transcription failure
- empty provider result

The script records chunk-level errors in the manifest.

## Tests

Unit tests mock the faster-whisper model factory. They do not load real models
and do not process real media.
