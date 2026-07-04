from io import StringIO

from ai_knowledge_pipeline.infra.runtime_logging import (
    RuntimeMetric,
    RuntimeMetricStatus,
    RuntimeMetricsCollector,
    create_runtime_logger,
    render_pipeline_summary,
)


def test_runtime_logger_emits_levels_stage_and_elapsed() -> None:
    stream = StringIO()
    logger = create_runtime_logger(stream)

    with logger.stage("Audio Chunking") as stage:
        stage.progress("Chunk 1 / 2")

    output = stream.getvalue()
    assert "[INFO] Audio Chunking started" in output
    assert "[PROGRESS] Audio Chunking | Chunk 1 / 2 | elapsed:" in output
    assert "[SUCCESS] Audio Chunking finished | elapsed:" in output
    metrics = logger.recorded_metrics()
    assert len(metrics) == 1
    assert metrics[0].stage_name == "Audio Chunking"
    assert metrics[0].status is RuntimeMetricStatus.SUCCESS
    assert metrics[0].elapsed_seconds >= 0


def test_runtime_logger_records_chunk_metrics() -> None:
    stream = StringIO()
    logger = create_runtime_logger(stream)

    with logger.chunk(
        "Whisper Transcription",
        chunk_index=1,
        total_chunks=3,
        chunk_name="chunk_001.mp3",
    ):
        pass

    output = stream.getvalue()
    assert "[PROGRESS] Whisper Transcription | Chunk 1 / 3: chunk_001.mp3 started" in output
    assert "[SUCCESS] Whisper Transcription | Chunk 1 / 3: chunk_001.mp3 finished" in output
    metrics = logger.recorded_metrics()
    assert len(metrics) == 1
    assert metrics[0].stage_name == "Whisper Transcription"
    assert metrics[0].chunk_index == 1
    assert metrics[0].total_chunks == 3
    assert metrics[0].chunk_name == "chunk_001.mp3"
    assert metrics[0].status is RuntimeMetricStatus.SUCCESS


def test_render_pipeline_summary_uses_collected_metrics() -> None:
    metrics = RuntimeMetricsCollector()
    metrics.record(
        RuntimeMetric(
            stage_name="Profile Loading",
            elapsed_seconds=0.2,
            status=RuntimeMetricStatus.SUCCESS,
        )
    )
    metrics.record(
        RuntimeMetric(
            stage_name="DeepSeek Cleaning",
            elapsed_seconds=231,
            status=RuntimeMetricStatus.SUCCESS,
        )
    )
    metrics.record(
        RuntimeMetric(
            stage_name="Whisper Transcription",
            elapsed_seconds=2112,
            status=RuntimeMetricStatus.SUCCESS,
            chunk_index=1,
            total_chunks=2,
            chunk_name="chunk_001.mp3",
        )
    )
    metrics.record(
        RuntimeMetric(
            stage_name="Whisper Transcription",
            elapsed_seconds=2088,
            status=RuntimeMetricStatus.SUCCESS,
            chunk_index=2,
            total_chunks=2,
            chunk_name="chunk_002.mp3",
        )
    )

    summary = render_pipeline_summary(
        metrics,
        profile="Finance",
        course="Buffett Letters",
        audio_length="Unknown",
    )

    assert "Wonderland Pipeline Summary" in summary
    assert "Profile\nFinance" in summary
    assert "Course\nBuffett Letters" in summary
    assert "Chunks\n2" in summary
    assert "Profile Loading" in summary
    assert "0.2 s" in summary
    assert "DeepSeek Cleaning" in summary
    assert "3m51s" in summary
    assert "Whisper Metrics" in summary
    assert "Chunk 1" in summary
    assert "35m12s" in summary
    assert "Pipeline Runtime" in summary
    assert "TOTAL" in summary
