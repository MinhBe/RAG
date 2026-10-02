from __future__ import annotations

from scripts.build_seqgan_vaccine_cases import build_cases


def test_build_cases_requires_waf_and_oracle() -> None:
    postgres = [{"sample_id": "s1", "truth_oracle_status": "matched", "module_id": "Y1_basic_boolean", "root_grammar_id": "basic_boolean", "y_level": "Y1"}]
    waf = [{"sample_id": "s1", "waf_access_logged": True, "waf_audit_logged": True, "http_status": 200, "waf_mode": "lab"}]
    cases = build_cases(postgres, waf, [], {"generator_kind": "test"}, 50)
    assert len(cases) == 1
    assert cases[0]["evidence_contract"]["modsecurity_first_gate"] is True
    assert cases[0]["threat_signal"]["verified_threat_signal"] is True
    assert cases[0]["source"]["payload_redacted"] is True


def test_build_cases_rejects_incomplete_evidence() -> None:
    postgres = [{"sample_id": "s1", "truth_oracle_status": "failed"}]
    waf = [{"sample_id": "s1", "waf_access_logged": True, "waf_audit_logged": True, "http_status": 200}]
    assert build_cases(postgres, waf, [], {}, 50) == []
