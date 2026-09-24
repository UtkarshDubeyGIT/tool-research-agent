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
    assert first_pass == []
