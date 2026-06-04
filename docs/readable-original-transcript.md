# Readable Original Transcript

## Goal

The `# 原始转录` section in generated Obsidian Markdown is now a readable source
transcript, not a summary and not a rewritten article.

It keeps the original teaching order and knowledge details while improving
readability.

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
is the preferred display text for Markdown.

## Provider Contract

The `CleaningProvider` protocol is unchanged. Providers still return
`CleaningProviderResult`.

OpenAI-compatible providers now parse `readable_transcript_text` from provider
JSON output. If an older provider response omits the field, the pipeline remains
compatible and Markdown falls back to `raw_transcript`.

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

The readable transcript must not:

- become a summary
- compress knowledge details
- reorder the lecture
- rewrite the speaker's argument
- delete knowledge-bearing details

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

Markdown output is organized as:

```markdown
# AI整理部分

...

# 原始转录

...
```

For `# 原始转录`, the renderer uses this order:

1. `CleanedTranscriptArtifact.readable_transcript_text`
2. `MarkdownReadyTranscript.readable_transcript_text`
3. `CleanedTranscriptArtifact.raw_transcript`

This preserves backward compatibility while preferring the readable transcript
whenever the cleaning provider supplies it.
