import json
from pathlib import Path
from src.audit import SAMPLED_APP_IDS


def test_audit_stays_pending_without_independent_source_checks():
    audit = json.loads(Path("data/audit.json").read_text(encoding="utf-8"))
    first_pass = json.loads(Path("data/first_pass.json").read_text(encoding="utf-8"))

    assert audit["status"] == "pending"
    assert audit["metrics"] is None
    assert audit["planned_sample_size"] == 18
    assert audit["planned_sample_ids"] == SAMPLED_APP_IDS
    assert len(first_pass) == 90
    assert {record["id"] for record in first_pass} == set(range(1, 91))


def test_review_queue_does_not_claim_ground_truth(tmp_path):
    from src.audit import prepare_review_queue
    queue = prepare_review_queue(output_path=str(tmp_path / "review_queue.json"))
    assert len(queue["entries"]) == 18
    for entry in queue["entries"]:
        for field in entry["fields"].values():
            assert field["review_status"] == "pending"
            assert field["checked_value"] is None
