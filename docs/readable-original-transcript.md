# Readable Original Transcript

## Goal

Generated Obsidian Markdown now separates the readable transcript from the
fully raw transcript.

`# 可读转录` is a lightly repaired transcript for reading. `# 原始逐字稿` is the
complete raw transcript for detail tracing and error checks.

## Data Model

`MarkdownReadyTranscript` includes:

```text
readable_transcript_text
```

`CleanedTranscriptArtifact` carries:

```text
raw_transcript
readable_transcript_text
```

The raw transcript remains available for auditability. The readable transcript
never replaces it.

## Provider Contract

The `CleaningProvider` protocol is unchanged. Providers still return
`CleaningProviderResult`.

OpenAI-compatible providers parse `readable_transcript_text` from provider JSON
output. If an older provider response omits the field, the pipeline remains
compatible: Markdown skips `# 可读转录` and still emits `# 原始逐字稿` from
`raw_transcript`.

## Prompt Constraints

The base knowledge profile requires:

- Simplified Chinese output
- Chinese punctuation restoration
- natural paragraphing
- typo and accent-recognition repair
- terminology repair
- lightweight section headings
- removal of greetings, welcome chatter, livestream interaction, and
  content-free small talk

The readable transcript is a light repair pass. It must not:

- become a summary
- compress knowledge details
- reorder the lecture
- rewrite the speaker's argument
- delete knowledge-bearing details
- replace the raw transcript

## Finance Profile

When `--profile finance` is used, finance terminology repair applies both to
the AI-organized section and to `readable_transcript_text`.

The finance terminology dictionary includes:

- 美联储沃什
- 鲍威尔
- FOMC
- CPI
- PPI
- M2

The finance prompt also reinforces terms such as 沃什、十年期美债、标普500、纳斯达克.

## Markdown Rendering

Markdown output is organized as three sections:

```markdown
# AI整理部分

...

# 可读转录

...

# 原始逐字稿

...
```

For `# 可读转录`, the renderer uses this order:

1. `CleanedTranscriptArtifact.readable_transcript_text`
2. `MarkdownReadyTranscript.readable_transcript_text`

For `# 原始逐字稿`, the renderer always uses:

```text
CleanedTranscriptArtifact.raw_transcript
```

This prevents readable transcript over-cleaning from hiding original details.
