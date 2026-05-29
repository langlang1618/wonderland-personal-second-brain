# Transcript Cleaning Layer

The transcript cleaning layer converts one `TranscriptArtifact` into one `CleanedTranscriptArtifact`.

It does not implement real OpenAI API calls, Markdown exporting, Obsidian writing, queue execution, retry orchestration, concurrency, embeddings, or RAG indexing.

## Architecture

```text
TranscriptArtifact
  -> TranscriptCleaningRequest
  -> TranscriptCleaningProvider protocol
  -> CleaningProviderResult
  -> CleanedTranscriptArtifact
```

The cleaner orchestration never calls an AI SDK directly. Concrete providers must implement `TranscriptCleaningProvider`.

## Provider Boundary

Future providers:

- OpenAI
- Claude
- Gemini
- Local LLM

The current default provider is `UnavailableCleaningProvider`, which returns a structured error until a real or mock provider is injected.

## Prompt Schema

`CleaningPromptSchema` contains:

- system instruction
- task instruction
- terminology
- output requirements
- style guide
- prompt version

This keeps prompts versioned and portable across providers.

## Markdown-Ready Schema

`MarkdownReadyTranscript` contains:

- title
- summary
- cleaned text
- chapters
- key insights
- action items
- semantic tags
- agent memory candidates

This structure is suitable for Markdown generation, Obsidian frontmatter, vector database payloads, RAG chunking, and agent memory extraction.

## Artifact Lineage

Each cleaned transcript snapshot includes:

- source id
- run/job/task/stage ids when provided
- `input_snapshot_ids` containing the parent transcript snapshot id
- `upstream_artifact_ids` containing the parent transcript artifact id

This makes AI cleaning re-runs auditable and rebuildable without overwriting raw transcripts.
