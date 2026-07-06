from okapi import okf_schema
from okapi.prompts import DEPTH_PRESETS, build_system_prompt, build_task_prompt

FUNCTIONAL_TYPES = ("Feature", "User Journey", "Business Rule", "Domain Term")


def test_functional_types_are_in_the_vocabulary():
    for t in FUNCTIONAL_TYPES:
        assert t in okf_schema.CONCEPT_TYPES


def test_system_prompt_covers_both_lenses():
    prompt = build_system_prompt()
    assert "technical" in prompt and "functional" in prompt
    for t in FUNCTIONAL_TYPES:
        assert t in prompt


def test_every_depth_mentions_functional_coverage():
    for name, preset in DEPTH_PRESETS.items():
        guidance = preset["guidance"].lower()
        assert any(
            word in guidance
            for word in ("feature", "user journey", "functional")
        ), f"depth {name!r} guidance has no functional coverage"


def test_task_prompt_states_target_and_output():
    prompt = build_task_prompt("src/billing/", "billing-okf")
    assert "src/billing/" in prompt
    assert "billing-okf/" in prompt
