# Real OpenAI Cleaning Provider

## Scope

`OpenAICleaningProvider` is the real API-backed implementation of the transcript
cleaning provider boundary.

It converts:

```text
TranscriptArtifact
-> OpenAICleaningProvider
-> CleaningProviderResult
-> DefaultTranscriptCleaner
-> CleanedTranscriptArtifact
```

The provider only calls OpenAI and returns `CleaningProviderResult`. Artifact
creation, lineage, metadata, and lifecycle state remain owned by
`DefaultTranscriptCleaner`.

## Responsibilities

- Repair transcription typos and terminology.
- Remove spoken filler and redundant phrasing.
- Structure transcript content into Markdown-ready chapters and blocks.
- Produce title, summary, key insights, action items, semantic tags, and future
  agent memory candidates.
- Return structured provider issues instead of raising SDK exceptions through
  the orchestration layer.

## Non-goals

- No Markdown rendering.
- No Obsidian writing.
- No embeddings or RAG indexing.
- No Agent Memory persistence.
- No queue, retry orchestration, concurrency, or batch processing.

## Configuration

Install the optional OpenAI dependency when using the real provider:

```bash
venv/bin/python -m pip install -e ".[openai]"
```

Store the API key in `.env`:

```bash
OPENAI_API_KEY=sk-...
```

The default model is `gpt-5-mini`, and can be overridden through
`TranscriptCleaningConfig`.

```python
from ai_knowledge_pipeline.modules.cleaning.contracts import (
    OpenAICleaningProvider,
    TranscriptCleaningConfig,
    TranscriptCleaningRequest,
    create_default_transcript_cleaner,
)

provider = OpenAICleaningProvider()
cleaner = create_default_transcript_cleaner(provider=provider)

result = cleaner.clean(
    TranscriptCleaningRequest(
        transcript=transcript_artifact,
        prompt=prompt_schema,
        config=TranscriptCleaningConfig(
            model_name="gpt-5-mini",
            env_path=".env",
            api_key_env_var="OPENAI_API_KEY",
        ),
    )
)
```

## Prompt Templates

OpenAI-specific prompt text lives in:

```text
ai_knowledge_pipeline/modules/cleaning/prompt_templates.py
```

The prompt requests strict JSON compatible with `MarkdownReadyTranscript`.
This keeps the provider output portable for Markdown generation, Obsidian,
future RAG chunk rebuilds, and future agent memory extraction.

## Error Model

The provider maps operational failures into structured cleaning issues:

- `missing_api_key`: `.env` or environment variable is missing.
- `sdk_unavailable`: optional `openai` package is not installed.
- `provider_failed`: OpenAI SDK call failed.
- `response_parse_failed`: model output was not valid provider JSON.

These issues remain inside `CleaningProviderResult`, so pipeline runtime and
future retry orchestration can inspect failures without provider-specific
exception handling.

## Testing

Unit tests use a fake OpenAI client and do not call the network. They validate:

- Responses API request construction.
- JSON response parsing into Markdown-ready structures.
- `.env` API key loading.
- structured parse/API-key failures.
- compatibility with Markdown generation and Obsidian writing.
