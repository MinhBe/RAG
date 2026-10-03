from app.core.boolean_vaccine import (
    compute_reward,
    extract_grammar_features,
    generate_expr_for_family,
)


def test_extract_grammar_features_redacts_payload() -> None:
    features = extract_grammar_features("20 BETWEEN 19 AND 21", seed_id="S1", family="between_range")
    assert features["grammar_valid"] is True
    assert features["operator_family"] == "range"
    assert features["payload_redacted"] is True
    assert features["payload_exported"] is False
    assert "20 BETWEEN" not in str(features)


def test_compute_reward_accepts_only_full_evidence() -> None:
    candidate = {"expected_truth": "TRUE", "grammar_valid": True}
    observation = {
        "http_status": 200,
        "waf_access_logged": True,
        "waf_audit_logged": True,
        "backend_reached": True,
        "observed_truth": "TRUE",
    }
    reward = compute_reward(candidate, observation, family_count=0, target_per_family=10, duplicate=False)
    assert reward["accepted"] is True
    assert "oracle_matched" in reward["reward_reasons"]


def test_generate_expr_for_family_has_expected_truth_label() -> None:
    import random

    expr, truth = generate_expr_for_family("numeric_equality", 2, random.Random(1))
    assert truth == "TRUE"
    assert "=" in expr
