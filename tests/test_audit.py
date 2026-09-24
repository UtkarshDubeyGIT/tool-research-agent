import os
import json
import pytest
from src.audit import run_audit, SAMPLED_APP_IDS


def test_human_audit_metrics():
    assert os.path.exists("data/audit.json"), "data/audit.json must exist"
    with open("data/audit.json", "r") as f:
        audit = json.load(f)

    assert audit["sample_size"] == 18, "Stratified sample size must be exactly 18"
    assert audit["population_size"] == 90, "Population size must be 90"
    assert len(audit["sampled_app_ids"]) == 18

    metrics = audit["metrics"]
    fp = metrics["first_pass"]
    fn = metrics["final_pass"]

    # Assert numerators and denominators match
    assert fp["field_denominator"] == 72, "4 fields * 18 apps = 72 checked fields"
    assert fn["field_denominator"] == 72
    assert fp["app_denominator"] == 18
    assert fn["app_denominator"] == 18

    # Accuracy must improve or hold steady
    assert fn["field_level_accuracy_pct"] >= fp["field_level_accuracy_pct"]
    assert fn["app_level_accuracy_pct"] >= fp["app_level_accuracy_pct"]
