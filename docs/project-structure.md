# Project Directory Structure

AI Knowledge Pipeline is designed as a local-first, modular Python system for turning internet courses, video, and audio into structured Markdown knowledge bases for Obsidian.

This first step only defines architecture and filesystem boundaries. No business logic is implemented yet.

## Directory Tree

```text
.
├── ai_knowledge_pipeline/
│   ├── core/
│   ├── modules/
│   │   ├── sources/
│   │   ├── download/
│   │   ├── chunking/
│   │   ├── transcription/
│   │   ├── cleaning/
│   │   ├── markdown/
│   │   └── obsidian/
│   ├── ai/
│   │   ├── prompts/
│   │   └── providers/
│   ├── config/
│   ├── infra/
│   └── cli/
├── configs/
├── data/
│   ├── raw/
│   ├── media/
│   ├── chunks/
│   ├── transcripts/
│   │   ├── raw/
│   │   └── cleaned/
│   ├── markdown/
│   ├── obsidian/
│   └── tmp/
├── docs/
├── scripts/
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

## Responsibilities

`ai_knowledge_pipeline/core/`
: Shared domain contracts, pipeline data models, result types, and interfaces. This layer should not depend on yt-dlp, ffmpeg, OpenAI, Whisper, or Obsidian-specific implementation details.

`ai_knowledge_pipeline/modules/`
: Pipeline business modules. Each subdirectory maps to one independently runnable stage with clear input and output contracts.

`ai_knowledge_pipeline/modules/sources/`
: Normalizes user input sources such as m3u8 URLs, YouTube URLs, local video paths, and local audio paths into a standard source descriptor.

`ai_knowledge_pipeline/modules/download/`
: Downloads or prepares media, preferring audio when possible. Future implementation will wrap yt-dlp behind a module boundary.

`ai_knowledge_pipeline/modules/chunking/`
: Splits standardized media into fixed-size chunks, defaulting to 30 minutes. Future implementation will likely use ffmpeg through infrastructure adapters.

`ai_knowledge_pipeline/modules/transcription/`
: Converts media chunks into raw transcripts. It should support local Whisper first and allow OpenAI Whisper API later through a provider interface.

`ai_knowledge_pipeline/modules/cleaning/`
: Uses AI to clean transcripts, fix terms, add punctuation, produce Markdown structure, generate titles, summaries, and knowledge points.

`ai_knowledge_pipeline/modules/markdown/`
: Renders cleaned structured content into Obsidian-compatible Markdown files with YAML metadata and tags.

`ai_knowledge_pipeline/modules/obsidian/`
: Writes generated Markdown into an Obsidian vault or staging directory, including future category routing and backlink/index support.

`ai_knowledge_pipeline/ai/`
: AI-specific assets that should stay separate from pipeline orchestration. This includes prompts, provider adapters, model configuration, and future memory/RAG-specific integrations.

`ai_knowledge_pipeline/config/`
: Configuration loading and validation code. This keeps `.env`, YAML config, and runtime settings separate from module logic.

`ai_knowledge_pipeline/infra/`
: Infrastructure adapters for filesystem access, logging, subprocess execution, ffmpeg, yt-dlp, and external command boundaries.

`ai_knowledge_pipeline/cli/`
: Command-line entrypoints. Each module can eventually expose its own CLI command without coupling directly to internal implementation details.

`configs/`
: Versioned configuration templates such as `default.example.yaml`. Local secrets and machine-specific paths should not be committed.

`data/`
: Local-first working data. Runtime artifacts are ignored by git while directory placeholders are retained.

`data/raw/`
: Original source descriptors, downloaded manifests, or untouched user-provided inputs.

`data/media/`
: Standardized downloaded or normalized media files.

`data/chunks/`
: 30-minute media chunks used as transcription inputs.

`data/transcripts/raw/`
: Raw Whisper output before AI cleanup.

`data/transcripts/cleaned/`
: AI-cleaned structured transcript payloads before final Markdown rendering.

`data/markdown/`
: Generated Obsidian-compatible Markdown files before vault ingestion.

`data/obsidian/`
: Local staging area for Obsidian vault writes, useful for testing before touching the real vault.

`data/tmp/`
: Temporary files, partial downloads, intermediate conversion outputs, and retry artifacts.

`tests/`
: Automated tests. Unit tests validate each module in isolation; integration tests validate cross-module data flow with fixtures.

`docs/`
: Architecture notes and operational documentation.

`scripts/`
: Developer and maintenance scripts. Production logic should live inside the Python package, not here.

## Design Rationale

The structure separates stable domain concepts from replaceable infrastructure. For example, the chunking module should know that media is split into chunks, but ffmpeg invocation details belong in `infra/`. The transcription module should know about transcript inputs and outputs, but whether the engine is local Whisper or an API provider should be hidden behind provider boundaries.

Each pipeline stage has its own directory because the system must grow toward independent execution, testing, and replacement. This makes it easier to run only download, only transcription, or only Markdown rendering during development and recovery.

The `data/` directory is explicit because this is a local-first system. Intermediate artifacts are valuable: they allow retries from the failed stage instead of re-downloading or re-transcribing everything.

The AI layer is separated because future RAG, Agent Memory, vector databases, MCP tools, and LangGraph workflows will add complexity. Keeping prompts and providers outside individual modules prevents AI-specific code from leaking everywhere.

## Pipeline Data Flow

```text
Input source
  -> sources: normalize m3u8 / YouTube / local video / local audio
  -> download: produce standardized media file
  -> chunking: produce 30-minute chunk files
  -> transcription: produce raw transcript files
  -> cleaning: produce structured cleaned transcript
  -> markdown: produce Obsidian Markdown with YAML metadata and tags
  -> obsidian: write Markdown into vault or staging directory
```

## Layer Mapping

Core logic
: `ai_knowledge_pipeline/core/`, `ai_knowledge_pipeline/modules/`

Configuration layer
: `ai_knowledge_pipeline/config/`, `configs/`, `.env.example`

Data layer
: `data/`

AI layer
: `ai_knowledge_pipeline/ai/`, `ai_knowledge_pipeline/modules/cleaning/`, `ai_knowledge_pipeline/modules/transcription/`

Infrastructure layer
: `ai_knowledge_pipeline/infra/`, `scripts/`

Test layer
: `tests/`
