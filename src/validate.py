import os
import sys
import json
import argparse
import re
from urllib.parse import urlsplit, urlunsplit
from typing import List, Dict, Any
from src.models import AppRecord


class EvidenceValidator:
    """Validate records and match evidence quotes to cached source snapshots."""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        self.cached_sources = self._load_cached_sources()

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlsplit(url.strip())
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))

    @staticmethod
    def _normalize(text: Any) -> str:
        if not isinstance(text, str):
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def _load_cached_sources(self) -> Dict[str, List[str]]:
        sources: Dict[str, List[str]] = {}
        if not os.path.isdir(self.cache_dir):
            return sources
        for current, _, filenames in os.walk(self.cache_dir):
            for filename in filenames:
                if not filename.endswith(".json"):
                    continue
                path = os.path.join(current, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        item = json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
                text = item.get("raw_markdown", "")
                if not isinstance(text, str) or not text:
                    continue
                for url in (item.get("url"), item.get("final_url")):
                    if isinstance(url, str) and url:
                        sources.setdefault(self._canonical_url(url), []).append(text)
        return sources

    def validate_dataset(self, records_path: str = "data/final_results.json") -> Dict[str, Any]:
        if not os.path.exists(records_path):
            raise FileNotFoundError(f"Records file {records_path} does not exist.")

        with open(records_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        report: Dict[str, Any] = {
            "total_records": len(raw_data),
            "expected_count": 90,
            "missing_ids": [],
            "duplicate_ids": [],
            "schema_errors": [],
            "logical_contradictions": [],
            "evidence_issues": [],
            "valid_records_count": 0,
            "flagged_records_count": 0,
            "cached_source_count": len(self.cached_sources),
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

            try:
                record = AppRecord(**item)
            except Exception as exc:
                report["schema_errors"].append(f"Record #{app_id} ({item.get('name')}) schema validation failed: {exc}")
                continue

            contradictions = self._check_contradictions(record)
            evidence_issues = self._check_evidence(record)
            report["logical_contradictions"].extend(
                f"#{app_id} ({record.name}): {issue}" for issue in contradictions
            )
            report["evidence_issues"].extend(
                f"#{app_id} ({record.name}): {issue}" for issue in evidence_issues
            )
            if contradictions or evidence_issues:
                report["flagged_records_count"] += 1
            else:
                report["valid_records_count"] += 1

        expected_ids = set(range(1, 91))
        report["missing_ids"] = sorted(expected_ids - seen_ids)
        return report

    @staticmethod
    def _check_contradictions(record: AppRecord) -> List[str]:
        issues = []
        cred = record.credential_access
        if record.buildability == "buildable_now" and cred.partner_approval_required == "yes":
            issues.append("buildability is 'buildable_now' but partner_approval_required is 'yes'.")
        if record.buildability == "buildable_now" and (not record.auth_methods or record.auth_methods == ["unknown"]):
            issues.append("buildability is 'buildable_now' but auth_methods is empty or unknown.")
        if record.buildability == "buildable_now" and (not record.api_types or record.api_types == ["unknown"]):
            issues.append("buildability is 'buildable_now' but api_types is empty or unknown.")
        if record.buildability == "outreach_needed" and (record.main_blocker == "none" or not record.main_blocker):
            issues.append("buildability is 'outreach_needed' but main_blocker is empty.")
        return issues

    def _check_evidence(self, record: AppRecord) -> List[str]:
        issues = []
        if record.research_status != "complete":
            issues.append(f"record is marked '{record.research_status}', not complete.")
        if not record.evidence:
            issues.append("record has no evidence entries.")

        for index, evidence in enumerate(record.evidence):
            parsed = urlsplit(evidence.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                issues.append(f"evidence item {index} has an invalid HTTP(S) URL.")
                continue

            source = self.cached_sources.get(self._canonical_url(evidence.url))
            if source is None:
                issues.append(f"evidence item {index} has no matching cached source snapshot.")
                continue

            quote = self._normalize(evidence.quote)
            source_text = self._normalize(source)
            if not quote or quote not in source_text:
                issues.append(f"evidence item {index} quote does not exactly match its cached source.")
            if evidence.verification != "supported":
                issues.append(f"evidence item {index} is marked '{evidence.verification}'.")
        return issues


def main():
    parser = argparse.ArgumentParser(description="Validate record schemas and source-backed evidence")
    parser.add_argument("--input", default="data/final_results.json", help="Path to research output JSON")
    parser.add_argument("--cache", default="data/cache", help="Directory containing retrieval snapshots")
    args = parser.parse_args()

    validator = EvidenceValidator(cache_dir=args.cache)
    try:
        report = validator.validate_dataset(args.input)
    except Exception as exc:
        print(f"Validation could not run: {exc}")
        sys.exit(1)

    print(f"Records: {report['total_records']} / {report['expected_count']}")
    print(f"Cached source snapshots: {report['cached_source_count']}")
    print(f"Records passing all checks: {report['valid_records_count']}")
    print(f"Records flagged: {report['flagged_records_count']}")
    print(f"Missing IDs: {report['missing_ids'] or 'none'}")
    print(f"Duplicate IDs: {report['duplicate_ids'] or 'none'}")
    print(f"Schema errors: {len(report['schema_errors'])}")
    print(f"Logical contradictions: {len(report['logical_contradictions'])}")
    print(f"Evidence issues: {len(report['evidence_issues'])}")

    if (report['schema_errors'] or report['missing_ids'] or report['duplicate_ids'] or
            report['logical_contradictions'] or report['evidence_issues']):
        sys.exit(1)


if __name__ == "__main__":
    main()
