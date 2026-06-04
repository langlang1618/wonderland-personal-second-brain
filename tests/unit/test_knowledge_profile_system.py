from pathlib import Path

from ai_knowledge_pipeline.modules.cleaning import (
    CleaningPromptSchema,
    KnowledgeProfileName,
    compose_cleaning_prompt,
    load_knowledge_profile,
)


def base_prompt() -> CleaningPromptSchema:
    return CleaningPromptSchema(
        system_instruction="Existing system instruction.",
        task_instruction="Clean the transcript.",
        terminology=("RAG",),
    )


def test_finance_profile_loads_prompt_and_terminology_dictionary() -> None:
    profile = load_knowledge_profile(KnowledgeProfileName.FINANCE)

    assert profile.name is KnowledgeProfileName.FINANCE
    assert "finance and macroeconomics" in profile.profile_prompt
    assert profile.terminology == (
        "美联储沃什",
        "鲍威尔",
        "FOMC",
        "CPI",
        "PPI",
        "M2",
    )


def test_profile_composition_combines_base_profile_and_existing_prompt() -> None:
    profile = load_knowledge_profile("ai")

    composed = compose_cleaning_prompt(base_prompt(), profile)

    assert "durable knowledge base" in composed.system_instruction
    assert "Simplified Chinese" in composed.system_instruction
    assert "readable_transcript_text" in composed.system_instruction
    assert "AI engineering and research" in composed.system_instruction
    assert "Existing system instruction." in composed.system_instruction
    assert composed.terminology == ("RAG",)


def test_custom_profile_loads_external_markdown(tmp_path) -> None:
    custom_path = tmp_path / "custom.md"
    custom_path.write_text("Apply a custom legal-review lens.", encoding="utf-8")

    profile = load_knowledge_profile("custom", custom_profile_path=custom_path)

    assert profile.name is KnowledgeProfileName.CUSTOM
    assert profile.profile_prompt == "Apply a custom legal-review lens."
    assert custom_path in profile.source_paths


def test_custom_profile_requires_path() -> None:
    try:
        load_knowledge_profile("custom")
    except ValueError as exc:
        assert "custom_profile_path is required" in str(exc)
    else:
        raise AssertionError("Expected custom profile path error")


def test_finance_profile_composition_applies_terms_to_readable_transcript_prompt() -> None:
    profile = load_knowledge_profile("finance")

    composed = compose_cleaning_prompt(base_prompt(), profile)

    assert "readable_transcript_text" in composed.system_instruction
    assert "Finance terminology repair applies both" in composed.system_instruction
    assert "美联储沃什" in composed.terminology
    assert "鲍威尔" in composed.terminology
    assert "FOMC" in composed.terminology
    assert "CPI" in composed.terminology
    assert "PPI" in composed.terminology
    assert "M2" in composed.terminology
