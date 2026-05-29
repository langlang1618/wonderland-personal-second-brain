# Real Local Whisper Provider

`LocalWhisperProvider` imports transcript files produced by local Whisper tools such as MacWhisper.

It does not run Whisper, call OpenAI, call Groq, access the network, or use a cloud API. It is a local-first adapter that converts existing `.txt` or `.srt` transcript exports into `TranscriptArtifact` through the existing transcription orchestration.

## Supported Inputs

- `.txt`: imported as one transcript segment covering the parent media chunk timeline
- `.srt`: imported as timestamped transcript segments

## Flow

```text
MediaChunkArtifact
  -> TranscriptionRequest(config.local_transcript_path)
  -> LocalWhisperProvider
  -> ProviderTranscriptionResult
  -> TranscriptArtifact
```

The `TranscriptionProvider` protocol is unchanged.

## Demo Usage

```python
from pathlib import Path
from ai_knowledge_pipeline.demo import run_local_whisper_demo_pipeline

result = run_local_whisper_demo_pipeline(
    local_audio_path=Path("课程01.m4a"),
    local_transcript_path=Path("课程01.srt"),
    temp_vault_path=Path("/tmp/demo-vault"),
)

print(result.obsidian_note_path)
```

The local audio path is still treated as a local media reference in the demo. The transcript file provides the real local transcript content.

## Future Providers

The same provider boundary can later support:

- faster-whisper
- WhisperKit
- whisper.cpp

Those implementations should still return `ProviderTranscriptionResult` and let the existing transcriber create `TranscriptArtifact`.
