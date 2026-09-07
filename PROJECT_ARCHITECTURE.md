# AI Knowledge Pipeline — 项目架构说明书

> **项目代号：Wonderland**  
> 本地优先的 AI 知识管线，将互联网课程、视频、音频转化为结构化的 Obsidian Markdown 知识笔记。

---

## 一、全景概述

```
用户输入 ──→  来源检测  ──→  媒体下载  ──→  音频切片  ──→  语音转录  ──→  文本清洗  ──→  Markdown生成  ──→  Obsidian写入
(URL/本地路径)     │            │             │             │              │               │               │
                  ▼            ▼             ▼             ▼              ▼               ▼               ▼
              SourceData   LocalMedia    Chunks       Transcript    CleanedText     Markdown.md    Obsidian笔记
```

项目是一个 **7 阶段可插拔管线**，每个阶段有清晰的抽象接口（`Protocol`）和默认实现。核心设计思想：

1. **本地优先** — 所有处理在本地完成，无外部 API 依赖（清洗阶段支持可插拔的 AI 提供者）
2. **不可变制品（Artifact）** — 每个阶段的产出是带有校验和、血缘链的不可变快照
3. **分层驱动** — 核心数据模型（`core/`）、模块实现（`modules/`）、执行脚本（`scripts/`）、Web UI（`app.py`）
4. **知识画像（Profile）** — 针对不同领域（金融、AI、玄学等）定制的清洗提示模板

---

## 二、目录职责总览

```
ai-knowledge-pipeline/
├── ai_knowledge_pipeline/         ← 核心 Python 包 (源代码)
│   ├── core/                      ← 领域数据模型 & 管线协议定义
│   ├── modules/                   ← 独立可运行的管线阶段模块
│   │   ├── sources/               ←   来源检测与标准化
│   │   ├── download/              ←   媒体下载（yt-dlp）
│   │   ├── chunking/              ←   音频切片（ffmpeg）
│   │   ├── transcription/         ←   语音转文本（faster-whisper）
│   │   ├── cleaning/              ←   AI 清洗原始转录稿
│   │   ├── markdown/              ←   结构化为 Obsidian Markdown
│   │   ├── obsidian/              ←   写入 Obsidian 仓库
│   │   └── profiles/              ←   知识画像预设定
│   ├── ai/                        ← （预留）AI 层
│   │   ├── prompts/               ←   提示模板
│   │   └── providers/             ←   AI 提供者抽象
│   ├── config/                    ← （预留）配置加载模块
│   ├── infra/                     ← （预留）基础设施适配层
│   ├── cli/                       ← （预留）CLI 入口
│   └── demo/                      ←   端到端演示管线（Mock 提供者）
├── app.py                         ← Wonderland Web UI (FastAPI)
├── configs/                       ← 项目配置文件
├── data/                          ← 运行时数据目录
│   ├── raw/                       ←   原始来源 / 制品 / 管线运行时数据
│   ├── media/                     ←   下载的媒体文件
│   ├── chunks/                    ←   音频切片
│   ├── transcripts/               ←   转录文本（raw → cleaned）
│   ├── markdown/                  ←   生成的 Markdown
│   ├── obsidian/                  ←   准备写入 Obsidian 的暂存笔记
│   ├── media_ingestion/           ←   媒体摄取工作区（按课程分目录）
│   ├── jobs/                      ←   Wonderland 任务日志（history.json + .log）
│   └── tmp/                       ←   临时目录
├── scripts/                       ← 可执行的管线运行脚本
├── static/                        ← Web UI 静态资产 (CSS, JS)
├── templates/                     ← Web UI HTML 模板
├── tests/                         ← 测试套件
├── docs/                          ← 架构文档 & 设计文档
├── pyproject.toml                 ← 项目元数据 & 构建配置
├── .env.example                   ← 环境变量模板
└── .gitignore
```

---

## 三、各目录详细说明

### 3.1 `ai_knowledge_pipeline/core/` — 核心领域模型 & 协议

**不包含任何业务实现**，只有数据类、枚举类型、和 Protocol 抽象接口。是整个管线的"宪法"。

| 文件 | 核心内容 |
|------|----------|
| `source.py` | `SourceData`, `SourceKind`, `SourceMetadata`, `SourceNormalizer` 协议 — 统一的来源数据契约 |
| `runtime.py` | `PipelineStageKind`（7 个阶段枚举）、`PipelineTask`, `PipelineState`, `PipelineRuntime` 协议 — 管线编排模型 |
| `artifact.py` | `ArtifactSnapshot`, `ArtifactLineage`, `ArtifactRegistry` 协议 — 不可变制品的全生命周期（声明 → 物化 → 注册 → 验证 → 废弃） |

### 3.2 `ai_knowledge_pipeline/modules/` — 管线阶段模块

每个模块遵循统一的内部结构：

```
module/
├── __init__.py        ← 公开工厂函数（create_default_xxx）
├── interfaces.py      ← 模块内部 Protocol 接口
├── contracts.py       ← 输入/输出数据契约 (dataclass)
├── types.py           ← 模块私有类型
├── errors.py          ← 错误码 & 错误类型
├── <orchestrator>.py  ← 默认编排器实现
├── adapters.py        ← 外部工具适配器 (yt-dlp, ffmpeg)
└── [sub-packages]     ← 运行时实现（如 transcription/runtime/）
```

#### `modules/sources/` — 来源检测 & 标准化

- **职责**：将用户输入（URL、本地路径）解析为标准化的 `SourceData`
- **核心组件**：
  - `RuleBasedSourceDetector` — 基于规则的来源类型检测（YouTube / m3u8 / 本地音视频）
  - `DefaultSourcesNormalizer` — 标准化管道，返回统一的 `SourceData`（含 `SourceId`、`SourceKind`、`SourceMetadata`）
- **关键能力**：自动区分远程 URL 和本地文件，识别 m3u8 直播流、YouTube 链接、常见音视频扩展名

#### `modules/download/` — 媒体下载

- **职责**：根据 `SourceData` 下载远程媒体或引用本地文件，产出 `LocalMediaArtifact`
- **核心组件**：
  - `DefaultMediaDownloader` — 编排器
  - `DefaultMediaStoragePlanner` — 决定存储位置
  - `DefaultYtDlpCommandBuilder` — 构建 yt-dlp 命令参数
- **关键能力**：支持 yt-dlp 下载、本地文件直引用、下载进度跟踪

#### `modules/chunking/` — 音频切片

- **职责**：将长音频/视频按固定时长切分为小片段
- **核心组件**：
  - `DefaultMediaChunker` — 编排器
  - `DefaultMediaChunkPlanner` — 计算切片计划
  - `DefaultFfmpegCommandBuilder` / `SubprocessFfmpegRunner` — 构建和执行 ffmpeg 命令
- **关键能力**：支持 `DRY_RUN`（只计划不执行）和 `MATERIALIZE`（实际切片）模式

#### `modules/transcription/` — 语音转录

- **职责**：从原生字幕或音频转录中获取统一文本，并将音频片段转写为文本（含时间戳）
- **核心组件**：
  - `TranscriptAcquisitionCoordinator` — 检查并选择 YouTube 手动字幕、自动字幕或 Whisper 回退路径
  - `YouTubeSubtitleInspector` / `YouTubeSubtitleExtractor` — 通过 yt-dlp 获取并规范化原生字幕
  - `DefaultTranscriber` — 编排器，依赖可插拔的 `TranscriptionProvider`
  - `FasterWhisperProvider` — 基于 faster-whisper 的本地转录实现
  - `LocalWhisperProvider` — 从本地预生成的转录文件导入
  - `DemoTranscriptionProvider` — 演示用 Mock 实现
- **子包 `runtime/`**：faster-whisper 运行时与 YouTube 字幕适配，含 `FasterWhisperModelFactory`（模型加载）、`TranscriptMerger`（切片合并）和自动字幕滚动重叠清理

#### `modules/cleaning/` — AI 清洗原始转录

- **职责**：使用 AI 模型将原始 ASR 转录稿清洗为结构化的知识文本
- **核心组件**：
  - `DefaultTranscriptCleaner` — 编排器
  - `DeepSeekCleaningProvider` — 通过 DeepSeek API 清洗
  - `OpenAICleaningProvider` — 通过 OpenAI API 清洗
  - `DirectTranscriptCleaningProvider` — AI / Tech 模式的确定性转录直通，不调用 LLM
  - `DemoCleaningProvider` — 演示用 Mock
- **子包 `profiles/`**：清洗提示模板系统
  - `base.md` — 基础清洗指令（语言、格式、质量控制）
  - `finance.md` / `ai.md` / `startup.md` — 领域特定提示
  - `finance_terms.yaml` — 金融术语词典
  - `loader.py` — `KnowledgeProfileLoader` 加载并组合提示模板

#### `modules/markdown/` — Markdown 生成

- **职责**：将清洗后的结构化文本渲染为 Obsidian 兼容的 Markdown
- **核心组件**：
  - `DefaultMarkdownGenerator` — 编排器
  - `ObsidianMarkdownRenderer` — 渲染为含 YAML frontmatter 的 Markdown

#### `modules/obsidian/` — Obsidian 写入

- **职责**：将生成的 Markdown 文件写入 Obsidian 仓库
- **核心组件**：
  - `DefaultObsidianWriter` — 编排器
  - `DefaultObsidianPathPlanner` — 根据知识画像确定 Obsidian 路径
  - `ObsidianConflictStrategy` — 冲突处理策略（`OVERWRITE` / `VERSIONED` / `SKIP`）

#### `modules/profiles/` — 知识画像注册中心

- **职责**：管理 Wonderland Web UI 的知识画像选择
- **核心组件**：
  - `ProfileRegistry` — 内置画像注册表
  - `KnowledgeProductProfile` — 画像数据模型（ID、名称、提示模板、输出路径、标签）
- **内置画像**：Finance（默认）、Metaphysics/Ziwei Bazi、AI/Tech、General

### 3.3 `ai_knowledge_pipeline/demo/` — 端到端演示管线

- `pipeline.py` — `run_local_audio_demo_pipeline()`：从本地音频 → Obsidian 笔记的完整流程
- `providers.py` — `DemoTranscriptionProvider` + `DemoCleaningProvider`：确定性 Mock 实现
- 不依赖外部 API 或网络，适合本地开发测试

### 3.4 预留模块

| 目录 | 用途 |
|------|------|
| `ai/` | AI 提供者抽象和提示模板管理（预留，当前仅含 `.gitkeep`） |
| `config/` | 配置加载和校验逻辑（预留） |
| `infra/` | 基础设施适配：文件系统、日志、外部工具（预留） |
| `cli/` | 命令行入口（预留，`__init__.py` 仅含 docstring） |

### 3.5 `app.py` — Wonderland Web UI

基于 **FastAPI** 的本地 Web 应用，提供可视化界面：

| 端点 | 功能 |
|------|------|
| `GET /` | 返回 Wonderland 首页（`templates/index.html`） |
| `POST /api/jobs` | 创建并启动处理任务 |
| `GET /api/jobs` | 列出历史任务 |
| `GET /api/jobs/{id}` | 查询任务状态 |
| `POST /api/jobs/{id}/cancel` | 取消运行中的任务 |
| `GET /api/jobs/{id}/log` | 获取任务日志 |

- 异步执行管线，日志实时流式写入
- 任务持久化到 `data/jobs/history.json`
- 通过 `.env` 配置 OpenAI API Key 和 Obsidian 仓库路径

### 3.6 `scripts/` — 可执行管线脚本

| 脚本 | 用途 |
|------|------|
| `run_full_course_pipeline.py` | **主要入口** — 从单一来源（URL/本地文件）完成：媒体摄取 → Whisper 转录 → 清洗 → Obsidian |
| `run_media_ingestion.py` | 媒体摄取子流程：下载/复制音视频 → 切片 |
| `run_local_whisper_transcription.py` | 本地 Whisper 转录子流程：音频切片 → 转写 → 合并 |
| `run_real_course_pipeline.py` | 清洗+Obsidian 子流程：转录稿 → AI 清洗 → Markdown → Obsidian |
| `run_batch_course_pipeline.py` | 批处理模式：同时处理多个来源 |

### 3.7 `configs/` — 项目配置

- `default.example.yaml` — 完整配置模板，覆盖所有管线阶段的默认参数（路径、超时、提供者选择、重试策略等）

### 3.8 `data/` — 运行时数据

| 子目录 | 内容 | 生成阶段 |
|--------|------|----------|
| `raw/` | 原始来源清单、制品注册表、管线运行时快照 | 各阶段 |
| `media/` | 下载的媒体文件 | download |
| `chunks/` | 音频切片 | chunking |
| `transcripts/raw/` | 原始 ASR 转录文本 | transcription |
| `transcripts/cleaned/` | 清洗后文本 | cleaning |
| `markdown/` | 生成的 Markdown 文件 | markdown |
| `obsidian/` | 暂存的 Obsidian 笔记 | obsidian |
| `media_ingestion/` | 媒体摄取工作区（按课程名分目录） | download + chunking |
| `jobs/` | Wonderland 任务日志 (`history.json` + `{uuid}.log`) | Web UI |
| `tmp/` | 临时文件 | 各阶段 |

### 3.9 `tests/` — 测试套件

按阶段分组的单元测试：

```
tests/
├── unit/
│   ├── test_source_model_contracts.py
│   ├── test_sources_detector_layer.py
│   ├── test_sources_normalizer_contracts.py
│   ├── test_media_download_layer.py
│   ├── test_media_chunking_layer.py
│   ├── test_transcription_layer.py
│   ├── test_local_whisper_provider.py
│   ├── test_faster_whisper_provider.py
│   ├── test_transcript_merger.py
│   ├── test_transcript_cleaning_layer.py
│   ├── test_deepseek_cleaning_provider.py
│   ├── test_openai_cleaning_provider.py
│   ├── test_markdown_generation_layer.py
│   ├── test_obsidian_writer_layer.py
│   ├── test_runtime_contracts.py
│   ├── test_artifact_contracts.py
│   ├── test_profile_registry.py
│   ├── test_knowledge_profile_system.py
│   ├── test_end_to_end_demo_pipeline.py
│   ├── test_media_ingestion_pipeline.py
│   ├── test_real_whisper_runtime.py
│   ├── test_batch_course_pipeline.py
│   ├── test_full_course_pipeline_runner.py
│   ├── test_real_course_pipeline_runner.py
│   ├── test_ytdlp_runtime_adapter.py
│   └── test_wonderland_app.py
├── integration/     (预留)
└── fixtures/        (预留)
```

### 3.10 `docs/` — 架构文档

19 份设计文档覆盖所有管线层：

| 文档 | 内容 |
|------|------|
| `project-structure.md` | 目录结构和管线数据流 |
| `source-data-model.md` | 来源数据契约 |
| `sources-normalizer-layer.md` | 来源标准化层 |
| `media-download-layer.md` | 媒体下载层 |
| `media-chunking-layer.md` | 媒体切片层 |
| `transcription-layer.md` | 转录层 |
| `real-local-whisper-provider.md` | faster-whisper 本地转录 |
| `real-whisper-runtime.md` | Whisper 运行时 |
| `transcript-cleaning-layer.md` | 转录稿清洗 |
| `deepseek-cleaning-provider.md` | DeepSeek 清洗提供者 |
| `openai-cleaning-provider.md` | OpenAI 清洗提供者 |
| `markdown-generation-layer.md` | Markdown 生成 |
| `obsidian-writer-layer.md` | Obsidian 写入器 |
| `artifact-storage-layer.md` | 制品存储层 |
| `pipeline-runtime-layer.md` | 管线运行时编排 |
| `knowledge-profile-system.md` | 知识画像系统 |
| `end-to-end-demo-pipeline.md` | 端到端演示管线 |
| `media-ingestion-pipeline.md` | 媒体摄取管线 |
| `real-course-pipeline-runner.md` | 真实课程管线运行器 |
| `batch-course-pipeline.md` | 批处理管线 |
| `readable-original-transcript.md` | 可读原始转录格式 |

### 3.11 顶层文件

| 文件 | 用途 |
|------|------|
| `app.py` | Wonderland Web UI (FastAPI 应用) |
| `pyproject.toml` | 项目元数据、依赖管理、构建配置、pytest 配置 |
| `.env.example` | 环境变量模板（`OPENAI_API_KEY`、`OBSIDIAN_VAULT_PATH`） |

---

## 四、管线数据流详解

### 4.1 主流程 (`run_full_course_pipeline.py`)

```
用户输入 (source URL/path)
  │
  ├─ auto-detect source type ─────────────────────────────────────┐
  │  ├─ m3u8 / webpage → run_media_ingestion.py                   │
  │  │                     (yt-dlp 下载 + ffmpeg 切片)            │
  │  └─ local-audio/video → 本地复制/ffmpeg 提取音频 + 切片       │
  │                                                                │
  ├─ 音频切片目录 ──→ run_local_whisper_transcription.py           │
  │                    (faster-whisper 逐片段转录 → 合并全文)      │
  │                                                                │
  ├─ 合并转录稿 ──→ run_real_course_pipeline.py                    │
  │                   (AI 清洗 → Markdown 生成 → Obsidian 写入)     │
  │                                                                │
  └─ 可选清理 (cleanup=raw,chunks) → 移除中间产物                  │
```

### 4.2 制品血缘链

每个阶段的输出是**不可变制品（Artifact Snapshot）**，追踪完整血缘：

```
ObsidianNote.snapshot
  ← Markdown.snapshot
    ← CleanedTranscript.snapshot
      ← Transcript.snapshot
        ← MediaChunk.snapshot
          ← LocalMedia.snapshot
            ← SourceData (source_id)
```

### 4.3 知识画像 (Knowledge Profile) 影响

知识画像影响两个层面：

1. **清洗提示** — `profiles/finance.md` 加入金融视角的术语修复指令
2. **Obsidian 路径** — `ProfileRegistry` 决定笔记写入 `AI Knowledge Pipeline/finance/` 等子目录

---

## 五、扩展指南

### 添加新的 AI 清洗提供者

1. 在 `modules/cleaning/` 中实现 `TranscriptCleaningProvider` 协议（参考 `deepseek_provider.py` / `openai_provider.py`）
2. 在 `modules/cleaning/providers.py` 中注册
3. 添加对应的单元测试

### 添加新的知识画像

1. 在 `modules/cleaning/profiles/` 中添加 `{name}.md`（清洗提示模板）
2. （可选）添加 `{name}_terms.yaml`（领域术语词典）
3. 在 `modules/cleaning/profiles/loader.py` 的 `KnowledgeProfileName` 枚举中注册
4. 在 `modules/profiles/registry.py` 的 `BUILTIN_PROFILES` 中注册

### 添加新的来源类型

1. 在 `modules/sources/rules.py` 中添加检测规则
2. 在 `modules/sources/detector.py` 的 `RuleBasedSourceDetector` 中添加处理分支
3. 在 `core/source.py` 的 `SourceKind` 枚举中注册

---

## 六、运行方式

```bash
# 开发模式：启动 Web UI
uv run uvicorn app:app --reload

# 命令行：处理单个来源
python scripts/run_full_course_pipeline.py \
  --source "https://example.com/course.m3u8" \
  --title "课程标题" \
  --profile finance \
  --model-size small \
  --language zh \
  --chunk-minutes 30

# 测试
uv run pytest
```

---

## 七、依赖关系

| 依赖 | 用途 |
|------|------|
| `fastapi>=0.115` | Web UI 框架（核心依赖） |
| `uvicorn>=0.30` | ASGI 服务器（核心依赖） |
| `openai>=1.0` | OpenAI / DeepSeek API 客户端（可选：`[openai]`） |
| `pytest>=8` | 测试（可选：`[dev]`） |
| `faster-whisper` | 本地语音识别 |
| `ffmpeg` | 音视频处理（系统级） |
| `yt-dlp` | 媒体下载（系统级） |
