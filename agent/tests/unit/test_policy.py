from app.pipeline.policy import get_pipeline_policy


def test_get_pipeline_policy_has_ordered_thresholds() -> None:
    p = get_pipeline_policy()
    assert p.version.startswith("policy_")
    assert 0.0 < p.confidence_abstain_threshold < p.confidence_uncertain_threshold <= 1.0
    assert p.max_conflict_checks_per_task >= 1
    assert isinstance(p.extraction_guidance, str)
    assert isinstance(p.validate_evidence_in_source, bool)


def test_get_pipeline_policy_supports_eval_cost_overrides(monkeypatch) -> None:
    monkeypatch.setenv("EVAL_ENABLE_CONFLICT_CHECK", "0")
    monkeypatch.setenv("PIPELINE_POLICY_VERSION", "v1")

    from app.pipeline import policy as policy_mod

    policy_mod._load_pipeline_policy.cache_clear()
    p = get_pipeline_policy()

    # The eval override forces conflict checks off regardless of the YAML
    # default, so eval runs can keep quota/latency low.
    assert p.max_conflict_checks_per_task == 0
    policy_mod._load_pipeline_policy.cache_clear()


def test_extraction_guidance_does_not_contradict_final_state_instruction(monkeypatch) -> None:
    """Regression guard: extraction_guidance is appended to the main prompt,
    so it must not contradict the new "emit a single task reflecting the
    final resolved state" instruction in EXTRACTION_USER_V1. Prior to the
    2026-05-13 fix, v1 told the model to emit both earlier and later
    assignments, which produced hallucinated_task errors against eval GT
    (eval expects one resolved task per deliverable).
    """
    monkeypatch.setenv("PIPELINE_POLICY_VERSION", "v1")
    from app.pipeline import policy as policy_mod

    policy_mod._load_pipeline_policy.cache_clear()
    p = get_pipeline_policy()
    guidance = p.extraction_guidance.lower()
    assert "emit the earlier and later" not in guidance
    assert "final resolved state" in guidance
    policy_mod._load_pipeline_policy.cache_clear()
