# Knowledge Profile System

## Scope

The Knowledge Profile System composes domain-specific cleaning instructions
without changing the `TranscriptCleaningProvider` protocol.

```text
base.md
+ profile.md
+ terminology dictionary
-> CleaningPromptSchema
-> CleaningProvider
```

Profiles are provider-independent. OpenAI, DeepSeek, and future
OpenRouter-compatible providers receive the same composed prompt contract.

## Registry

Profile assets live in:

```text
ai_knowledge_pipeline/modules/cleaning/profiles/
  base.md
  finance.md
  ai.md
  startup.md
  finance_terms.yaml
```

Built-in profiles:

- `finance`
- `ai`
- `startup`
- `custom`

## Finance Terminology

The finance profile automatically loads:

- 美联储沃什
- 鲍威尔
- FOMC
- CPI
- PPI
- M2

These terms are appended to existing prompt terminology with stable
deduplication.

## Custom Profile

Use `custom` with an external Markdown prompt:

```bash
venv/bin/python scripts/run_real_course_pipeline.py \
  --transcript /path/to/course01.txt \
  --vault /path/to/ObsidianVault \
  --profile custom \
  --profile-path /path/to/my-profile.md
```

## Original Transcript Preservation

`CleanedTranscriptArtifact` preserves the complete raw transcript as
`raw_transcript`. Markdown rendering appends:

```markdown
# 原始转录
```

This retains the source transcript for auditability and later regeneration.
