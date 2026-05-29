from pathlib import Path

from ai_knowledge_pipeline.core.source import (
    MediaKind,
    SourceAccess,
    SourceData,
    SourceKind,
    SourceLocation,
    SourceModelConfig,
)
from ai_knowledge_pipeline.modules.sources.contracts import (
    DetectionSignal,
    ManifestFormat,
    SourceDetection,
    SourceErrorCode,
    SourceIssue,
    SourceIssueSeverity,
    SourceManifestEnvelope,
    SourceManifestRef,
    SourceNormalizationResult,
    SourceParseContext,
    SourceValidationResult,
)


def test_detection_contract_can_describe_parser_selection() -> None:
    detection = SourceDetection(
        raw_input="https://www.youtube.com/watch?v=example",
        kind=SourceKind.YOUTUBE,
        media_kind=MediaKind.VIDEO,
        parser_name="youtube",
        confidence=0.95,
        signals=(DetectionSignal.URL_HOST,),
    )

    assert detection.parser_name == "youtube"
    assert detection.kind is SourceKind.YOUTUBE
    assert detection.confidence == 0.95


def test_normalization_result_keeps_structured_errors() -> None:
    issue = SourceIssue(
        code=SourceErrorCode.UNSUPPORTED_INPUT,
        message="Input is not supported.",
        severity=SourceIssueSeverity.ERROR,
        field="raw_input",
    )

    result = SourceNormalizationResult(source=None, issues=(issue,))

    assert not result.is_success
    assert result.issues[0].code is SourceErrorCode.UNSUPPORTED_INPUT


def test_manifest_contract_references_persisted_source_data() -> None:
    source = SourceData(
        source_id="src_example",
        kind=SourceKind.LOCAL_AUDIO,
        media_kind=MediaKind.AUDIO,
        location=SourceLocation(
            access=SourceAccess.LOCAL,
            uri="/tmp/example.mp3",
            path=Path("/tmp/example.mp3"),
        ),
    )
    envelope = SourceManifestEnvelope(
        manifest_version="v1",
        source=source,
        parser_name="local_audio",
    )
    ref = SourceManifestRef(
        source_id=source.source_id,
        path=Path("data/raw/sources/src_example.json"),
        format=ManifestFormat.JSON,
    )

    assert envelope.source.source_id == ref.source_id
    assert ref.path.name == "src_example.json"


def test_validation_result_can_represent_policy_warnings() -> None:
    source = SourceData(
        source_id="src_m3u8",
        kind=SourceKind.M3U8,
        media_kind=MediaKind.VIDEO,
        location=SourceLocation(
            access=SourceAccess.REMOTE,
            uri="https://example.com/playlist.m3u8",
        ),
    )
    warning = SourceIssue(
        code=SourceErrorCode.MISSING_REQUIRED_METADATA,
        message="Title is not available yet.",
        severity=SourceIssueSeverity.WARNING,
        field="metadata.title",
    )

    result = SourceValidationResult(source=source, issues=(warning,))

    assert result.is_valid
    assert result.issues[0].severity is SourceIssueSeverity.WARNING


def test_parse_context_carries_config_without_runtime_side_effects() -> None:
    context = SourceParseContext(
        config=SourceModelConfig(source_manifest_dir=Path("data/raw/sources")),
        config_profile="local",
    )

    assert context.config.source_manifest_dir == Path("data/raw/sources")
    assert context.config_profile == "local"
