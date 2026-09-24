import os
import json
import pytest
from src.models import AppRecord


def test_canonical_apps_list():
    assert os.path.exists("data/apps.json"), "data/apps.json must exist"
    with open("data/apps.json", "r") as f:
        apps = json.load(f)
    assert len(apps) == 90, "Exactly 90 apps must be present"
    ids = [a["id"] for a in apps]
    assert ids == list(range(1, 91)), "IDs must be sequential from 1 to 90"
    categories = set(a["category"] for a in apps)
    assert len(categories) == 9, "Exactly 9 categories must be present"


def test_final_results_schema():
    assert os.path.exists("data/final_results.json"), "data/final_results.json must exist"
    with open("data/final_results.json", "r") as f:
        records = json.load(f)
    assert len(records) == 90, "Exactly 90 records must exist in final results"
    for r in records:
        record = AppRecord(**r)
        assert record.id >= 1 and record.id <= 90
        assert record.buildability in {"buildable_now", "conditional", "outreach_needed", "unknown"}
        assert record.api_breadth in {"broad", "focused", "limited", "unknown"}
        assert record.existing_mcp in {"official", "third_party", "none_found", "unknown"}
        if record.research_status == "complete":
            assert record.evidence, f"Source-checked app #{record.id} must have evidence"
