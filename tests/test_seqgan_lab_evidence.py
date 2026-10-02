from scripts.build_seqgan_lab_evidence import build_evidence


def test_build_seqgan_lab_evidence_aggregate_without_payload():
    postgres_rows = [
        {
            "sample_id": "S1",
            "module_id": "Y1_basic_boolean",
            "truth_oracle_status": "matched",
            "postgres_runtime_status": "passed",
        }
    ]
    waf_rows = [
        {
            "sample_id": "S1",
            "http_status": 200,
            "waf_access_logged": True,
            "waf_audit_logged": True,
        }
    ]

    evidence = build_evidence(postgres_rows, waf_rows)

    assert len(evidence) == 3
    aggregate = evidence[0]
    assert aggregate.severity_hint == "high"
    assert aggregate.attributes["sample_count"] == 1
    assert aggregate.attributes["postgres_truth_oracle_matched"] == 1
    assert aggregate.attributes["waf_audit_logged"] == 1
    assert "payload" not in aggregate.message.lower()
    assert evidence[1].attributes["payload_exported"] is False
    assert evidence[2].attributes["payload_exported"] is False
