from pathlib import Path
from types import ModuleType

from ai_knowledge_pipeline.core.artifact import (
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.modules.chunking import MediaChunkArtifact, MediaChunkingStatus
from ai_knowledge_pipeline.modules.transcription import (
    FasterWhisperConfig,
    FasterWhisperModelSize,
    FasterWhisperProvider,
    TranscriptionConfig,
    TranscriptionErrorCode,
    TranscriptionRequest,
)
from ai_knowledge_pipeline.modules.transcription.runtime.faster_whisper_provider import (
    _default_model_factory,
)


class Segment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class Info:
    language = "zh"
    language_probability = 0.93


class FakeModel:
    def __init__(self, segments=None, error=None):
        self.segments = segments or (
            Segment(0.0, 1.5, "第一段。"),
            Segment(1.5, 3.0, "第二段。"),
        )
        self.error = error
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))
        if self.error:
            raise self.error
        return self.segments, Info()


def chunk_artifact(path: Path) -> MediaChunkArtifact:
    snapshot = ArtifactSnapshot(
        artifact_id="chunk_course_0000",
        snapshot_id="chunk_course_0000_v1",
        kind=ArtifactKind.CHUNK,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri=path.as_uri(),
            path=path,
            media_type="audio/*",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(
            source_id="course",
            input_snapshot_ids=("media_course_v1",),
            upstream_artifact_ids=("media_course",),
        ),
        metadata=ArtifactMetadata(title="Course", chunk_index=0, chunk_count=1),
    )
    return MediaChunkArtifact(
        chunk_artifact_id="chunk_course_0000",
        source_id="course",
        parent_media_artifact_id="media_course",
        chunk_index=0,
        start_time=0,
        end_time=3,
        duration=3,
        status=MediaChunkingStatus.MATERIALIZED,
        path=path,
        uri=path.as_uri(),
        snapshot=snapshot,
    )


def test_faster_whisper_provider_transcribes_segments(tmp_path) -> None:
    audio_path = tmp_path / "chunk_001.mp3"
    audio_path.write_text("audio", encoding="utf-8")
    model = FakeModel()
    provider = FasterWhisperProvider(
        FasterWhisperConfig(model_size=FasterWhisperModelSize.SMALL, language="zh"),
        model_factory=lambda model_size, **kwargs: model,
    )

    result = provider.transcribe(
        TranscriptionRequest(
            chunk=chunk_artifact(audio_path),
            config=TranscriptionConfig(model_name="small", language="zh"),
        )
    )

    assert result.is_success
    assert result.text == "第一段。\n第二段。"
    assert result.language == "zh"
    assert result.confidence == 0.93
    assert result.model_name == "small"
    assert result.segments[0].timestamp.start_time == 0
    assert result.segments[1].timestamp.end_time == 3
    assert model.calls[0][0] == str(audio_path)
    assert model.calls[0][1]["language"] == "zh"


def test_faster_whisper_provider_missing_audio_is_structured(tmp_path) -> None:
    provider = FasterWhisperProvider(model_factory=lambda model_size, **kwargs: FakeModel())

    result = provider.transcribe(
        TranscriptionRequest(chunk=chunk_artifact(tmp_path / "missing.mp3"))
    )

    assert not result.is_success
    assert result.issues[0].code is TranscriptionErrorCode.MISSING_CHUNK_PATH


def test_faster_whisper_provider_transcription_failure_is_structured(tmp_path) -> None:
    audio_path = tmp_path / "chunk_001.mp3"
    audio_path.write_text("audio", encoding="utf-8")
    provider = FasterWhisperProvider(
        model_factory=lambda model_size, **kwargs: FakeModel(error=RuntimeError("bad audio"))
    )

    result = provider.transcribe(
        TranscriptionRequest(chunk=chunk_artifact(audio_path))
    )

    assert not result.is_success
    assert result.issues[0].code is TranscriptionErrorCode.AUDIO_TRANSCRIPTION_FAILED


def test_faster_whisper_provider_model_load_failure_is_structured(tmp_path) -> None:
    audio_path = tmp_path / "chunk_001.mp3"
    audio_path.write_text("audio", encoding="utf-8")

    def failing_factory(model_size, **kwargs):
        raise RuntimeError("model download failed")

    provider = FasterWhisperProvider(
        FasterWhisperConfig(model_load_retry_delay_seconds=0),
        model_factory=failing_factory,
    )

    result = provider.transcribe(
        TranscriptionRequest(chunk=chunk_artifact(audio_path))
    )

    assert not result.is_success
    assert result.issues[0].code is TranscriptionErrorCode.MODEL_LOAD_FAILED
    assert "after 3 attempt" in result.issues[0].message
    assert result.issues[0].details["attempts"] == "3"


def test_faster_whisper_provider_retries_model_load_then_transcribes(tmp_path) -> None:
    audio_path = tmp_path / "chunk_001.mp3"
    audio_path.write_text("audio", encoding="utf-8")
    attempts = {"count": 0}
    model = FakeModel()

    def flaky_factory(model_size, **kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("503 Service Unavailable")
        return model

    provider = FasterWhisperProvider(
        FasterWhisperConfig(
            model_size=FasterWhisperModelSize.SMALL,
            language="zh",
            model_load_retry_delay_seconds=0,
        ),
        model_factory=flaky_factory,
    )

    result = provider.transcribe(
        TranscriptionRequest(
            chunk=chunk_artifact(audio_path),
            config=TranscriptionConfig(model_name="small", language="zh"),
        )
    )

    assert result.is_success
    assert attempts["count"] == 3
    assert result.text == "第一段。\n第二段。"


def test_default_model_factory_uses_local_cache_first(monkeypatch) -> None:
    calls = []
    fake_module = ModuleType("faster_whisper")

    class FakeWhisperModel:
        def __init__(self, model_size, **kwargs):
            calls.append((model_size, kwargs))

    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(__import__("sys").modules, "faster_whisper", fake_module)

    _default_model_factory("small", device="cpu", compute_type="int8")

    assert calls[0][0] == "small"
    assert calls[0][1]["local_files_only"] is True
    assert calls[0][1]["device"] == "cpu"
    assert calls[0][1]["compute_type"] == "int8"


def test_default_model_factory_falls_back_when_local_cache_fails(monkeypatch) -> None:
    calls = []
    fake_module = ModuleType("faster_whisper")

    class FakeWhisperModel:
        def __init__(self, model_size, **kwargs):
            calls.append((model_size, kwargs))
            if kwargs.get("local_files_only") is True:
                raise RuntimeError("local cache missing")

    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(__import__("sys").modules, "faster_whisper", fake_module)

    _default_model_factory("small", device="cpu", compute_type="int8")

    assert calls[0][1]["local_files_only"] is True
    assert calls[1][1]["local_files_only"] is False
