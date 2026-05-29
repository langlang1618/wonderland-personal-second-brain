from pathlib import Path

from ai_knowledge_pipeline.core.source import (
    MediaKind,
    SourceAccess,
    SourceData,
    SourceKind,
    SourceLocation,
    SourceMetadata,
    SourceModelConfig,
    SourceStatus,
)


def test_source_data_can_describe_remote_youtube_source() -> None:
    source = SourceData(
        source_id="src_youtube_example",
        kind=SourceKind.YOUTUBE,
        media_kind=MediaKind.VIDEO,
        location=SourceLocation(
            access=SourceAccess.REMOTE,
            uri="https://www.youtube.com/watch?v=example",
        ),
        metadata=SourceMetadata(
            title="Example lecture",
            origin_platform="youtube",
            tags=("course", "ai"),
        ),
    )

    assert source.status is SourceStatus.DECLARED
    assert source.preferred_track == "audio"
    assert source.metadata.tags == ("course", "ai")


def test_source_model_config_is_path_based_and_configurable() -> None:
    config = SourceModelConfig(
        source_manifest_dir=Path("data/raw/sources"),
        default_language="en",
        default_tags=("course",),
    )

    assert config.source_manifest_dir == Path("data/raw/sources")
    assert config.default_language == "en"
    assert config.default_tags == ("course",)
