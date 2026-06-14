import pytest

from ai_knowledge_pipeline.modules.profiles import ProfileRegistry, UnknownProfileError


def test_profile_registry_returns_builtin_profiles() -> None:
    registry = ProfileRegistry()

    finance = registry.get("finance")
    metaphysics = registry.get("metaphysics")
    ai = registry.get("ai")
    general = registry.get("general")

    assert finance.display_name == "Finance"
    assert finance.prompt_profile == "finance"
    assert finance.output_folder.as_posix() == "AI Knowledge Pipeline/finance"
    assert finance.tags == ("finance", "course", "whisper-small", "wonderland")
    assert metaphysics.display_name == "Metaphysics / Ziwei Bazi"
    assert metaphysics.prompt_profile == "metaphysics"
    assert metaphysics.effective_prompt_profile == "ai"
    assert metaphysics.output_folder.as_posix() == "AI Knowledge Pipeline/metaphysics"
    assert metaphysics.tags == ("metaphysics", "ziwei", "bazi", "course", "wonderland")
    assert ai.display_name == "AI / Tech"
    assert ai.effective_prompt_profile == "ai"
    assert ai.tags == ("ai", "tech", "course", "wonderland")
    assert general.display_name == "General"
    assert general.prompt_profile == "general"
    assert general.effective_prompt_profile == "ai"
    assert general.tags == ("general", "course", "wonderland")


def test_profile_registry_defaults_to_finance() -> None:
    profile = ProfileRegistry().get(None)

    assert profile.id == "finance"
    assert profile.display_name == "Finance"


def test_profile_registry_unknown_profile_reports_clear_error() -> None:
    with pytest.raises(UnknownProfileError) as exc:
        ProfileRegistry().get("unknown")

    assert "Unknown knowledge profile 'unknown'" in str(exc.value)
    assert "finance" in str(exc.value)
