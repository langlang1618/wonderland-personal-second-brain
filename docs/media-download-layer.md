# Media Download Layer

This layer converts `SourceData` into a unified `LocalMediaArtifact`.

It does not implement chunking, transcription, OpenAI cleaning, queue execution, or concurrent downloads.

## Architecture

```text
SourceData
  -> MediaDownloadRequest
  -> MediaStoragePlanner
  -> MediaDownloadPlan
  -> MediaDownloadAdapter
  -> LocalMediaArtifact
```

The default downloader is an orchestrator. It does not know how yt-dlp works internally, and it does not call runtime APIs directly.

## Contracts

Module files:

- `types.py`: request, config, plan, result, and `LocalMediaArtifact`
- `interfaces.py`: downloader, adapter, storage planner, yt-dlp command builder protocols
- `storage.py`: deterministic path planning without file IO
- `adapters.py`: yt-dlp command builder boundary without subprocess execution
- `downloader.py`: default orchestration
- `errors.py`: structured error model

## LocalMediaArtifact

`LocalMediaArtifact` wraps:

- media artifact id
- source id
- download status
- path / uri
- full `ArtifactSnapshot`
- metadata

The embedded `ArtifactSnapshot` preserves lineage compatibility with the artifact storage layer.

## yt-dlp Boundary

`DefaultYtDlpCommandBuilder` builds command arguments only.

Actual execution must be provided later by a `MediaDownloadAdapter`. This keeps yt-dlp isolated from runtime, retry, queue, and orchestration code.

## Storage Path Strategy

Remote sources plan output under:

```text
data/media/{source_id}.media
```

The extension is a placeholder because yt-dlp may determine the final extension.

Local sources keep their original path by default:

```yaml
download:
  keep_original_local_path: true
```

No directory is created and no file is copied by the planner.

## Download Lifecycle

Statuses:

- planned
- metadata only
- local reference
- downloaded
- failed
- skipped

Dry-run returns a planned artifact. Metadata-only returns a metadata artifact. Local source returns a local reference. Remote materialization requires an injected adapter.

## Error Model

Errors are structured as `MediaDownloadIssue`.

Stable codes:

- unsupported source kind
- adapter required
- adapter failed
- invalid source location
- download skipped
- output path unavailable

## Future Agent / RAG Compatibility

The artifact emitted by this layer includes:

- source id
- run id
- job id
- task id
- stage id
- artifact metadata
- artifact snapshot id

This lets future agents, RAG rebuild jobs, and retry workflows trace media back to the exact source and download task.
