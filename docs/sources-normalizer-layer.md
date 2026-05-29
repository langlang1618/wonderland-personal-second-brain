# Sources Normalizer Layer

This document designs the system boundary that converts arbitrary user input into `SourceData`. It does not implement URL parsing, file probing, media downloading, or manifest writes.

## Responsibility

The sources normalizer layer accepts one raw input string and returns a structured normalization result.

Supported input families:

- YouTube URL
- m3u8 URL
- local video path
- local audio path

Output:

- `SourceData` when normalization succeeds
- structured issues when normalization is unsupported, ambiguous, invalid, or blocked by config
- optional manifest reference when persistence is enabled by a future implementation

## File Organization

```text
ai_knowledge_pipeline/modules/sources/
├── contracts.py
├── errors.py
├── interfaces.py
└── types.py
```

`types.py`
: Data transfer objects for detection, parsing, validation, normalization results, and manifest references.

`interfaces.py`
: Protocol contracts for detector, parser, validator, id factory, serializer, repository, and top-level normalizer.

`errors.py`
: Stable error codes and issue objects used by parsers, validators, repositories, and orchestrators.

`contracts.py`
: Public import surface for the sources module.

## Architecture

```text
RawSourceInput
  -> SourceDetector
  -> SourceParser
  -> SourceValidator
  -> SourceManifestRepository
  -> SourceNormalizationResult
```

The top-level `SourcesNormalizer` should eventually coordinate these components. It should not contain YouTube-specific, m3u8-specific, or filesystem-specific parsing rules directly.

## Normalizer Interface

`SourcesNormalizer` is the orchestration boundary:

```python
class SourcesNormalizer(Protocol):
    def normalize(
        self,
        raw_input: RawSourceInput,
        context: SourceParseContext,
    ) -> SourceNormalizationResult:
        ...
```

The normalizer receives:

- raw input string
- config
- optional user hints
- config profile name

The normalizer returns:

- normalized `SourceData`
- detection result
- optional manifest reference
- issues collected across all stages

## Parser Interface

Each source family should have its own parser implementation:

- `YouTubeSourceParser`
- `M3U8SourceParser`
- `LocalVideoSourceParser`
- `LocalAudioSourceParser`

Parser contract:

```python
class SourceParser(Protocol):
    name: str

    def parse(self, request: SourceParseRequest) -> SourceParseResult:
        ...
```

Parsers are responsible for shaping a `SourceData` candidate. They are not responsible for downloading media, transcribing content, or writing Markdown.

## Source Detection Strategy

Detection should be a separate component because detection is policy-heavy and likely to evolve.

Detection output:

- `SourceKind`
- `MediaKind`
- parser name
- confidence score
- detection signals
- issues

Detection signals:

- URL scheme
- URL host
- URL path
- file extension
- file probe
- user hint

Recommended future strategy:

1. Apply explicit user hints first when provided.
2. Classify remote URLs by scheme and host.
3. Classify m3u8 by URL path or manifest content hints.
4. Classify local paths by extension first.
5. Optionally use a file probe adapter later for ambiguous local files.
6. Return ambiguity as a structured issue instead of guessing silently.

This keeps detection explainable, testable, and suitable for agent workflows.

## Validator Design

Validation is separate from parsing. A parser may understand an input, while policy may still reject it.

Validator responsibilities:

- enforce `allow_remote_sources`
- enforce `allow_local_sources`
- verify kind/media compatibility
- verify required fields for downstream pipeline stages
- verify local path policy when configured
- report unsupported media type
- report missing required metadata when strict mode is introduced

Validator output is `SourceValidationResult`, which contains the source and a tuple of `SourceIssue`.

Validation should not mutate the source. If future validation needs repair, that should become a separate repair/rewrite step.

## Error Model

The error model is issue-first:

```python
SourceIssue(
    code=SourceErrorCode.UNSUPPORTED_INPUT,
    message="...",
    severity=SourceIssueSeverity.ERROR,
    field="raw_input",
)
```

Stable error codes:

- `unsupported_input`
- `ambiguous_input`
- `remote_sources_disabled`
- `local_sources_disabled`
- `invalid_url`
- `invalid_local_path`
- `unsupported_media_type`
- `missing_required_metadata`
- `manifest_write_failed`
- `manifest_read_failed`

This gives future CLI, LangGraph nodes, agent tools, and UI surfaces a predictable way to react to failures.

## Manifest Persistence Strategy

Manifests should preserve the normalized source descriptor before downstream work starts.

Planned manifest location:

```text
data/raw/sources/{source_id}.json
```

The directory is configurable through:

```yaml
sources:
  source_manifest_dir: data/raw/sources
  manifest_format: json
  manifest_version: v1
```

Manifest envelope:

- manifest version
- `SourceData`
- parser name
- persistence metadata

Persistence boundary:

```python
class SourceManifestRepository(Protocol):
    def save(self, envelope: SourceManifestEnvelope) -> SourceManifestRef:
        ...

    def load(self, path: Path) -> SourceManifestEnvelope:
        ...

    def find_by_source_id(self, source_id: SourceId) -> SourceManifestRef | None:
        ...
```

Serialization is also isolated behind `SourceManifestSerializer` so JSON can be used first and YAML can be added later.

## Why This Module Split

Detection, parsing, validation, and persistence change for different reasons.

Detection changes when new source families or heuristics are added. Parsing changes when a specific source family needs richer metadata. Validation changes when project policy changes. Persistence changes when the manifest format or storage location changes.

Keeping these responsibilities separate makes each component small, replaceable, and easy to test with fake implementations.

## Data Flow

```text
raw input string
  -> SourceParseContext(config, profile, hints)
  -> SourceDetector.detect()
  -> SourceParser.parse()
  -> SourceValidator.validate()
  -> SourceIdFactory.create_id()
  -> SourceManifestSerializer.dumps()
  -> SourceManifestRepository.save()
  -> SourceNormalizationResult
```

Downstream modules consume `SourceData`; they do not need to know which parser created it.

## Extension Points

Easy future extensions:

- add `VimeoSourceParser` without changing `SourceData`
- add playlist/course expansion as a batch normalizer
- add file probing through an infra adapter
- add stricter validation profiles
- add YAML manifest support
- add source deduplication using `SourceIdFactory`
- add trust/safety checks for remote URLs
- add human override hints from CLI or UI

## AI Orchestration Nodes

The sources layer can become several AI or LangGraph nodes later:

- source classification node
- ambiguity resolution node
- metadata enrichment node
- manifest persistence node
- validation and repair suggestion node
- batch expansion node for courses and playlists

For RAG and Agent Memory, `SourceData.source_id` should remain the identity anchor. All future media files, chunks, transcripts, cleaned Markdown, embeddings, and memory entries should be traceable back to that id.
