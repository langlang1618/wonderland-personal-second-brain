# End-to-End Demo Pipeline

The demo pipeline wires the existing local-first modules together without calling external services.

## Flow

```text
Local audio path
  -> SourceData
  -> LocalMediaArtifact
  -> MediaChunkArtifact
  -> TranscriptArtifact
  -> CleanedTranscriptArtifact
  -> MarkdownArtifact
  -> ObsidianNoteArtifact
  -> .md file in temporary vault
```

## What Is Mocked

- Chunking uses dry-run chunk artifact generation, so ffmpeg is not called.
- Transcription uses `DemoTranscriptionProvider`.
- Cleaning uses `DemoCleaningProvider`.

The demo does not call network, yt-dlp, ffmpeg, Whisper, OpenAI, embeddings, RAG, queues, or agent memory.

## Usage

```python
from pathlib import Path
from ai_knowledge_pipeline.demo import DemoPipelineRequest, run_local_audio_demo_pipeline

result = run_local_audio_demo_pipeline(
    DemoPipelineRequest(
        local_audio_path=Path("sample.mp3"),
        temp_vault_path=Path("/tmp/demo-vault"),
    )
)

print(result.obsidian_note_path)
```

The input audio path is treated as a local media reference. It does not need to be read by the demo pipeline.

## Lineage

The result includes a lineage chain:

```text
ObsidianNoteArtifact
  -> MarkdownArtifact
  -> CleanedTranscriptArtifact
  -> TranscriptArtifact
  -> MediaChunkArtifact
  -> LocalMediaArtifact
  -> SourceData
```

This validates that artifact snapshots remain connected across the demo pipeline.
