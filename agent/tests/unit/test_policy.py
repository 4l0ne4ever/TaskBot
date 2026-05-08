from app.pipeline.policy import get_pipeline_policy


def test_get_pipeline_policy_has_ordered_thresholds() -> None:
    p = get_pipeline_policy()
    assert p.version.startswith("policy_")
    assert 0.0 < p.confidence_abstain_threshold < p.confidence_uncertain_threshold <= 1.0
    assert p.max_conflict_checks_per_task >= 1
    assert isinstance(p.extraction_guidance, str)
    assert isinstance(p.verification_enabled, bool)
    assert isinstance(p.validate_evidence_in_source, bool)


def test_get_pipeline_policy_supports_eval_cost_overrides(monkeypatch) -> None:
    monkeypatch.setenv("EVAL_VERIFY_LLM", "0")
    monkeypatch.setenv("EVAL_ENABLE_CONFLICT_CHECK", "0")
    monkeypatch.setenv("PIPELINE_POLICY_VERSION", "v3")

    from app.pipeline import policy as policy_mod

    policy_mod._load_pipeline_policy.cache_clear()
    p = get_pipeline_policy()

    assert p.verification_enabled is False
    assert p.max_conflict_checks_per_task == 0
    policy_mod._load_pipeline_policy.cache_clear()
