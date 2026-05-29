"""Demo pipelines and mock providers."""

from ai_knowledge_pipeline.demo.pipeline import (
    DemoPipelineArtifacts,
    DemoPipelineRequest,
    DemoPipelineResult,
    run_local_audio_demo_pipeline,
    run_local_whisper_demo_pipeline,
)
from ai_knowledge_pipeline.demo.providers import (
    DemoCleaningProvider,
    DemoTranscriptionProvider,
)

__all__ = [
    "DemoCleaningProvider",
    "DemoPipelineArtifacts",
    "DemoPipelineRequest",
    "DemoPipelineResult",
    "DemoTranscriptionProvider",
    "run_local_audio_demo_pipeline",
    "run_local_whisper_demo_pipeline",
]
