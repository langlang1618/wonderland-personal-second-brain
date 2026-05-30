# DeepSeek Cleaning Provider

## Scope

`DeepSeekCleaningProvider` is an OpenAI-compatible Chat Completions provider for
the transcript cleaning layer.

It converts:

```text
TranscriptArtifact
-> DeepSeekCleaningProvider
-> CleaningProviderResult
-> DefaultTranscriptCleaner
-> CleanedTranscriptArtifact
```

The provider only returns `CleaningProviderResult`. Artifact materialization,
lineage, metadata, and lifecycle state remain owned by `DefaultTranscriptCleaner`.

## API Boundary

DeepSeek is called through the OpenAI SDK using the Chat Completions interface:

```text
client.chat.completions.create(...)
```

The provider does not call Markdown generation, Obsidian writing, runtime retry,
queue systems, RAG, embedding, or agent memory persistence.

## Environment

Do not commit secrets. Configure credentials in `.env` or the process
environment:

```bash
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

Defaults:

- `DEEPSEEK_BASE_URL`: `https://api.deepseek.com`
- `DEEPSEEK_MODEL`: `deepseek-v4-flash`

`DEEPSEEK_API_KEY` is required. Missing keys are returned as structured
`TranscriptCleaningIssue` values.

Install the shared OpenAI SDK dependency:

```bash
venv/bin/python -m pip install -e ".[openai]"
```

## Usage

```python
from ai_knowledge_pipeline.modules.cleaning.contracts import (
    DeepSeekCleaningProvider,
    TranscriptCleaningConfig,
    TranscriptCleaningRequest,
    create_default_transcript_cleaner,
)

provider = DeepSeekCleaningProvider()
cleaner = create_default_transcript_cleaner(provider=provider)

result = cleaner.clean(
    TranscriptCleaningRequest(
        transcript=transcript_artifact,
        prompt=prompt_schema,
        config=TranscriptCleaningConfig(
            env_path=".env",
            model_name=None,
        ),
    )
)
```

If `model_name` is set in `TranscriptCleaningConfig`, it takes precedence over
`DEEPSEEK_MODEL`.

## Prompt Contract

The provider reuses the existing cleaning prompt template and JSON schema hint
used by the OpenAI provider. This keeps outputs compatible with:

- Markdown generation
- Obsidian writing
- future RAG chunk rebuilds
- future embedding re-indexing
- future agent memory extraction
- future OpenRouter-compatible providers

Expected provider output maps to `MarkdownReadyTranscript`:

- title
- summary
- cleaned text
- chapters
- key insights
- action items
- semantic tags
- agent memory candidates
- confidence

## Error Handling

All provider failures are converted into structured `TranscriptCleaningIssue`
values:

- `missing_api_key`: `DEEPSEEK_API_KEY` is missing.
- `sdk_unavailable`: the optional `openai` package is not installed.
- `provider_failed`: the DeepSeek API call failed.
- `response_parse_failed`: response JSON was invalid or did not match the
  expected schema.

API keys are redacted from provider error messages before they are returned.

## Tests

Unit tests use fake OpenAI-compatible clients. They do not call the network and
do not use real API keys.

Covered behavior:

- mock DeepSeek response parsing
- `.env` configuration loading
- missing API key
- invalid JSON
- API exception mapping
- cleaning -> Markdown -> Obsidian compatibility
