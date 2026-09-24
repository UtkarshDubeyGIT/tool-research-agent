import os
import sys
import json
import argparse
from urllib.parse import urlparse
from typing import List, Dict, Any, Tuple
from src.models import (
    AppRecord,
    CredentialAccess,
    BuildabilityVerdict,
    ApiBreadth,
    ExistingMcp
)


VALID_BUILDABILITY = {"buildable_now", "conditional", "outreach_needed", "unknown"}
VALID_API_BREADTH = {"broad", "focused", "limited", "unknown"}
VALID_MCP = {"official", "third_party", "none_found", "unknown"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_YES_NO_UNKNOWN = {"yes", "no", "unknown"}


class EvidenceValidator:
    """Deterministic validation of research outputs, schema integrity, and quote consistency."""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir

    def validate_dataset(self, records_path: str = "data/final_results.json") -> Dict[str, Any]:
        if not os.path.exists(records_path):
            raise FileNotFoundError(f"Records file {records_path} does not exist.")

        with open(records_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        report = {
            "total_records": len(raw_data),
            "expected_count": 90,
            "missing_ids": [],
            "duplicate_ids": [],
            "schema_errors": [],
            "logical_contradictions": [],
            "evidence_issues": [],
            "valid_records_count": 0,
            "flagged_records_count": 0
        }

        seen_ids = set()
        for idx, item in enumerate(raw_data):
            app_id = item.get("id")
            if app_id is None:
                report["schema_errors"].append(f"Record at index {idx} has missing 'id'")
                continue

            if app_id in seen_ids:
                report["duplicate_ids"].append(app_id)
            seen_ids.add(app_id)

            # Pydantic validation
            try:
                record = AppRecord(**item)
            except Exception as e:
                report["schema_errors"].append(f"Record #{app_id} ({item.get('name')}) schema validation failed: {str(e)}")
                continue

            # Check logical contradictions
            contradictions = self._check_contradictions(record)
            if contradictions:
                report["logical_contradictions"].extend([f"#{app_id} ({record.name}): {c}" for c in contradictions])

            # Check evidence validity
            ev_issues = self._check_evidence(record)
            if ev_issues:
                report["evidence_issues"].extend([f"#{app_id} ({record.name}): {issue}" for issue in ev_issues])

            if contradictions or ev_issues:
                report["flagged_records_count"] += 1
            else:
                report["valid_records_count"] += 1

        # Check for missing IDs (1 to 90)
        expected_ids = set(range(1, 91))
        report["missing_ids"] = sorted(list(expected_ids - seen_ids))

        return report

    def _check_contradictions(self, record: AppRecord) -> List[str]:
        issues = []
        cred = record.credential_access

        # Rule: buildable_now cannot be partner_approval_required: yes
        if record.buildability == "buildable_now" and cred.partner_approval_required == "yes":
            issues.append("Contradiction: buildability is 'buildable_now' but partner_approval_required is 'yes'.")

        # Rule: buildable_now requires at least one auth method
        if record.buildability == "buildable_now" and (not record.auth_methods or record.auth_methods == ["unknown"]):
            issues.append("Contradiction: buildability is 'buildable_now' but auth_methods is empty or 'unknown'.")

        # Rule: buildable_now requires at least one API type
        if record.buildability == "buildable_now" and (not record.api_types or record.api_types == ["unknown"]):
            issues.append("Contradiction: buildability is 'buildable_now' but api_types is empty or 'unknown'.")

        # Rule: outreach_needed should have a descriptive blocker
        if record.buildability == "outreach_needed" and (record.main_blocker == "none" or not record.main_blocker):
            issues.append("Contradiction: buildability is 'outreach_needed' but main_blocker is 'none'.")

        return issues

    def _check_evidence(self, record: AppRecord) -> List[str]:
        issues = []
        if not record.evidence and record.research_status == "complete":
            issues.append("Missing evidence: Record is marked 'complete' but has zero evidence entries.")

        for i, ev in enumerate(record.evidence):
            # Check URL format
            parsed = urlparse(ev.url)
            if not parsed.scheme or not parsed.netloc:
                issues.append(f"Evidence item {i} has invalid URL: '{ev.url}'")

            # Check quote presence
            if not ev.quote or len(ev.quote.strip()) < 5:
                issues.append(f"Evidence item {i} has empty or trivial quote for field '{ev.field}'")

            # Flag disputed claim
            if ev.verification in ("contradicted", "insufficient_evidence"):
                issues.append(f"Disputed evidence: field '{ev.field}' verification marked '{ev.verification}'")

        return issues


def main():
    parser = argparse.ArgumentParser(description="Deterministic Evidence & Schema Validator")
    parser.add_argument("--input", default="data/final_results.json", help="Path to research output JSON")
    args = parser.parse_args()

    validator = EvidenceValidator()
    print(f"[*] Running deterministic validation on {args.input}...")
    try:
        report = validator.validate_dataset(args.input)
    except Exception as e:
        print(f"[!] Validation failed to execute: {e}")
        sys.exit(1)

    print(f"\n================ VALIDATION REPORT ================")
    print(f"Total records checked: {report['total_records']} / {report['expected_count']}")
    print(f"Valid records:         {report['valid_records_count']}")
    print(f"Flagged records:       {report['flagged_records_count']}")
    print(f"Missing IDs (1-90):    {report['missing_ids'] or 'None (All 90 present)'}")
    print(f"Duplicate IDs:         {report['duplicate_ids'] or 'None'}")
    print(f"Schema errors:         {len(report['schema_errors'])}")
    print(f"Logical contradictions:{len(report['logical_contradictions'])}")
    print(f"Evidence issues:       {len(report['evidence_issues'])}")

    if report["logical_contradictions"]:
        print("\nContradictions found:")
        for c in report["logical_contradictions"][:5]:
            print(f"  - {c}")
    if report["schema_errors"]:
        print("\nSchema errors:")
        for se in report["schema_errors"][:5]:
            print(f"  - {se}")

    print("====================================================\n")
    if report["schema_errors"] or report["missing_ids"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
