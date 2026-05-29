# Transcription Layer

The transcription layer converts one `MediaChunkArtifact` into one `TranscriptArtifact`.

It does not implement OpenAI cleaning, Markdown formatting, Obsidian writing, queue execution, retry orchestration, concurrent execution, semantic post-processing, or real Whisper API calls.

## Architecture

```text
MediaChunkArtifact
  -> TranscriptionRequest
  -> TranscriptionProvider protocol
  -> ProviderTranscriptionResult
  -> TranscriptArtifact
```

The transcriber orchestration never calls an AI SDK directly. Concrete providers must implement `TranscriptionProvider`.

## Provider Boundary

Future providers:

- OpenAI Whisper API
- faster-whisper
- whisper.cpp
- WhisperKit
- Groq Whisper

The current default provider is `UnavailableTranscriptionProvider`, which returns a structured error until a real or mock provider is injected.

## Transcript Schema

Transcript output supports:

- raw transcript text
- timestamped segments
- language
- confidence
- future speaker metadata

`TranscriptSegment` contains:

- segment index
- timestamp range
- text
- confidence
- speaker metadata

## Artifact Lineage

Each transcript artifact includes an `ArtifactSnapshot` with:

- source id
- run/job/task/stage ids when provided
- `input_snapshot_ids` containing the parent chunk snapshot id
- `upstream_artifact_ids` containing the parent chunk artifact id

This keeps transcripts ready for AI cleaning, RAG indexing, embedding rebuilds, and agent memory workflows.
