from scripts.run_seqgan_full_projected_loop import (
    make_predicate,
    project_from_full_rows,
    static_valid,
)


def test_projected_predicates_are_static_valid_and_unique():
    rows = [
        {
            "generated_payload": "raw seqgan 10 random 20 tokens",
            "target_truth": "TRUE",
            "sample_id": "RAW-1",
        },
        {
            "generated_payload": "raw seqgan 30 random 40 tokens",
            "target_truth": "FALSE",
            "sample_id": "RAW-2",
        },
    ]

    projected = project_from_full_rows(rows, "TEST-RUN", 12)

    assert len(projected) == 12
    assert len({row["generated_payload_sha256"] for row in projected}) == 12
    assert all(row["generator_kind"] == "full_pytorch_seqgan_v3_oracle_projected" for row in projected)
    assert all(row["source_full_seqgan_candidate_sha256"] for row in projected)
    assert all(static_valid(row["generated_payload"]) for row in projected)


def test_make_predicate_static_templates():
    for expected in ["TRUE", "FALSE"]:
        for strategy in ["eq", "neq", "lt", "gt", "between", "paren"]:
            payload = make_predicate([10, 20], expected, strategy, 3)
            assert static_valid(payload)
