# Wonderland v1.8.0

## Transcript Acquisition Capability

Status: **RELEASED**

## Overview

Wonderland v1.8.0 adds deterministic transcript acquisition before downstream knowledge processing. The release prefers usable native YouTube subtitles and falls back to the established local Whisper path when necessary.

## Highlights

- Acquires manual and automatic English YouTube subtitles.
- Preserves the existing `merged_transcript.txt` handoff.
- Keeps Finance behavior on its established transcription and knowledge-cleaning path.
- Supports direct English transcript notes for the AI / Tech profile without semantic rewriting.

## Transcript Acquisition Strategy

For English-learning acquisition, Wonderland uses this order:

1. Manual English YouTube subtitles.
2. Automatic English YouTube captions.
3. Local faster-whisper transcription in English.

Subtitle language preference, Whisper language, and expected transcript language are represented independently. Acquired transcripts receive deterministic validation before downstream processing.

## AI / Tech Direct Transcript

The AI / Tech profile can bypass DeepSeek and render an accepted transcript directly to Markdown and Obsidian. The direct provider performs only deterministic formatting cleanup; it does not summarize, translate, or semantically rewrite transcript content.

## Reliability Improvements

- Resolves yt-dlp beside the active Python executable before searching the system path.
- Records subtitle category, language, yt-dlp executable, and yt-dlp version in acquisition metadata.
- Falls back to Whisper when subtitle inspection, extraction, or validation cannot produce a usable transcript.
- Maintains cache compatibility through an acquisition manifest.

## Automatic Caption Hotfix

YouTube automatic captions can repeat rolling text across adjacent VTT cues. Wonderland now finds the longest confident word-level overlap between neighboring automatic-caption cues and appends only new text. Manual subtitle normalization remains unchanged.

## Validation

- Manual English YouTube subtitles: real acceptance passed.
- Automatic English YouTube subtitles: real acceptance passed.
- Automatic-caption rolling duplicate cleanup: real acceptance passed.
- AI / Tech direct transcript output: real acceptance passed.
- Finance regression path: automated coverage passed.
- Automated test suite: **225 passed, 1 non-blocking dependency warning**.
- Python compilation and `git diff --check`: passed.

The automatic-caption acceptance run confirmed that native subtitles bypassed media download and Whisper, produced no Whisper metrics, and generated a clean English transcript in Obsidian.

## Known Limitations

- Native YouTube subtitle timestamps are not yet preserved.
- Minor punctuation and line-formatting artifacts may remain.
- English language validation is heuristic.
- Very short transcripts may be rejected conservatively.

These limitations are intentionally deferred and do not block v1.8.0.
