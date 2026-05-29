# Media Chunking Layer

The media chunking layer converts one `LocalMediaArtifact` into many `MediaChunkArtifact` records.

It does not implement transcription, Whisper, OpenAI cleaning, queue execution, retry orchestration, concurrent execution, or real media probing.

## Architecture

```text
LocalMediaArtifact
  -> MediaChunkingRequest
  -> TimelineSegmenter
  -> MediaChunkPlanner
  -> FfmpegCommandBuilder
  -> MediaChunkingAdapter
  -> MediaChunkArtifact[]
```

`ffmpeg` appears only in the adapter/runtime layer. The chunker orchestration does not call subprocess directly.

## Runtime Boundary

- `DefaultMediaChunker`: orchestration and artifact generation
- `DefaultMediaChunkPlanner`: path and timeline planning
- `FixedDurationTimelineSegmenter`: deterministic 30-minute segmentation
- `DefaultFfmpegCommandBuilder`: command construction
- `FfmpegRuntimeAdapter`: adapter implementing chunk materialization
- `SubprocessFfmpegRunner`: only class that calls `subprocess.run`

## Metadata

Every chunk artifact includes:

- `chunk_index`
- `start_time`
- `end_time`
- `duration`
- `chunk_count`
- parent media artifact id
- parent media snapshot id

## Lineage

Each chunk snapshot has:

- `source_id`
- run/job/task/stage ids when provided
- `input_snapshot_ids` containing the parent media snapshot id
- `upstream_artifact_ids` containing the parent media artifact id

This keeps chunks compatible with future transcript, RAG, embedding, and agent memory rebuilds.

## Future Segmentation

`SegmentationStrategyKind` reserves strategy names for:

- fixed duration
- silence detection
- VAD
- semantic chunking
- speaker-aware chunking

Only fixed-duration segmentation is implemented now.
