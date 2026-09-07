# Wonderland

## Personal Second Brain System

Wonderland is a local-first personal knowledge system that transforms long-form content such as online courses, videos, and audio into structured Markdown knowledge assets and stores them in Obsidian.

The goal is simple:

> Turn fragmented information consumption into a reusable personal knowledge infrastructure.

Instead of manually watching, summarizing, and organizing long-form content, Wonderland builds an automated workflow that absorbs, processes, structures, and stores knowledge continuously.

---

# Overview

Wonderland is an end-to-end knowledge processing system designed around a modular pipeline architecture.

```text
Input Sources
(Video / Audio / YouTube / m3u8)
|
v
Source Detection
|
v
Media Ingestion
(download / extract audio)
|
v
Audio Chunking
|
v
Local Speech Recognition
(faster-whisper)
|
v
Knowledge Cleaning
(LLM-powered)
|
v
Markdown Generation
|
v
Obsidian Knowledge Base
```

The system focuses on:

- Local-first processing
- Modular pipeline design
- Long-running workflow reliability
- Observable execution
- Reusable knowledge generation

---

# Current Status

## Wonderland v1.8.0 — Transcript Acquisition Capability

Wonderland has evolved from a simple content processing script into a complete local knowledge application system.

Current capabilities:

- ✅ Multi-source media ingestion
- ✅ YouTube manual and automatic English subtitle acquisition
- ✅ Deterministic transcript acquisition with Whisper fallback
- ✅ Local Whisper transcription pipeline
- ✅ LLM-powered knowledge cleaning
- ✅ AI / Tech direct transcript output without LLM rewriting
- ✅ Knowledge Profile System
- ✅ Markdown generation
- ✅ Obsidian integration
- ✅ Local Web UI
- ✅ Job history management
- ✅ Runtime observability
- ✅ Performance metrics
- ✅ Pipeline execution summary
- ✅ Error handling and recovery

Validation:

- 16 real courses processed
- Approximately 40 hours of content transformed
- 225 automated tests passed

---

# Key Features

## 1. Multi-source Content Ingestion

Wonderland supports different knowledge input sources:

- Local video files
- Local audio files
- Online course resources
- YouTube sources
- m3u8 streaming content

The pipeline automatically handles:

- Source detection
- Media downloading
- Audio extraction
- Chunk generation

---

## 2. Local Speech Recognition

Wonderland integrates local speech recognition through faster-whisper.

Capabilities:

- Long-duration audio processing
- Chunk-based transcription
- Transcript merging
- Silent chunk handling
- Runtime progress tracking

This allows large courses and long-form content to be processed locally.

---

## 3. Transcript Acquisition

For AI / Tech content, Wonderland can acquire an English transcript before media processing:

1. Prefer manual English YouTube subtitles.
2. Fall back to automatic English captions.
3. Fall back to local Whisper transcription when native subtitles are unavailable or unusable.

Automatic captions receive deterministic rolling-overlap cleanup. Accepted transcripts continue through the existing `merged_transcript.txt` handoff, and AI / Tech notes can preserve the transcript directly without DeepSeek rewriting.

---

## 4. Knowledge Cleaning & Domain Profiles

Wonderland separates raw transcription from structured knowledge generation.

The cleaning layer supports different knowledge profiles.

Examples:

- Finance
- Technology / AI
- General knowledge

Profiles allow the same pipeline to adapt to different knowledge domains.

---

## 5. Runtime Observability

Wonderland v1.6.1 introduced an engineering observability layer.

It provides visibility into:

- Current pipeline stage
- Chunk progress
- Execution time
- Runtime metrics
- Pipeline summary

Example:

```text
==========================

Wonderland Pipeline Summary

==========================

Audio Extract : 13.2 s

Chunking : 21.8 s

Whisper

Chunk1 : 35m12s
Chunk2 : 34m48s
Chunk3 : 36m02s

Cleaning : 3m51s

Markdown : 1.2s

TOTAL : 2h25m

==========================
```

---

# Engineering Architecture

Wonderland follows a modular architecture:

```text
wonderland/

├── core/
│ Runtime contracts and artifacts
│
├── modules/
│ ├── sources
│ ├── download
│ ├── chunking
│ ├── transcription
│ ├── cleaning
│ ├── markdown
│ └── obsidian
│
├── infra/
│ Runtime logging and infrastructure
│
├── scripts/
│ Pipeline execution entrypoints
│
├── templates/
│ Web interface
│
└── tests/
Automated validation
```

The architecture separates:

- Core contracts
- Pipeline modules
- Infrastructure services
- Runtime execution
- Validation

---

# Engineering Evolution

| Version | Focus |
|---|---|
| v1.0.0 | Initial knowledge processing pipeline |
| v1.1.0 | Local Whisper transcription runtime |
| v1.4.0 | Web UI and Job Management |
| v1.5.0 | Markdown template refinement |
| v1.5.2 | Job history and execution control |
| v1.6.0 | Knowledge Profile System |
| v1.6.1 | Observability, Metrics and Robustness |
| v1.8.0 | Transcript Acquisition Capability |

---

# Tech Stack

## Language

- Python

## Backend

- FastAPI
- Uvicorn

## Media Processing

- ffmpeg
- yt-dlp

## AI Components

- faster-whisper
- DeepSeek API
- OpenAI-compatible providers

## Knowledge Management

- Markdown
- Obsidian

## Engineering

- pytest
- modular architecture
- runtime logging
- automated testing

---

# Roadmap

## Knowledge Retrieval

Future exploration:

- RAG-based retrieval
- Semantic search
- Knowledge graph
- Personal knowledge querying

---

## Intelligent Workflow

Future exploration:

- Dynamic routing
- Evaluation framework
- Adaptive processing
- More agentic workflow patterns

---

## Productization

Future exploration:

- Easier deployment
- Reproducible setup
- Richer user experience
- Personal knowledge assistant

---

# Project Philosophy

Wonderland is not built as a one-time automation script.

It is an evolving personal knowledge infrastructure.

The long-term vision:

> Build a personal second brain that continuously absorbs, organizes, and compounds knowledge over time.
