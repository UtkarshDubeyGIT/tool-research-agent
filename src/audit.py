import json
import argparse
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlsplit


SAMPLED_APP_IDS = [1, 10, 11, 20, 21, 28, 31, 35, 41, 49, 56, 59, 61, 67, 71, 74, 81, 90]
AUDIT_FIELDS = ["auth_methods", "credential_access", "api_breadth", "buildability"]


def _load_records(path: str) -> Dict[int, Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return {}
    return {item["id"]: item for item in data if isinstance(item, dict) and isinstance(item.get("id"), int)}


def _matches(field: str, value: Any, expected: Any) -> bool:
    if field == "auth_methods":
        return set(value or []) == set(expected or [])
    if field == "credential_access":
        return value == expected
    return value == expected


def run_audit(
    first_pass_path: str = "data/first_pass.json",
    final_pass_path: str = "data/final_results.json",
    audit_output_path: str = "data/audit.json",
) -> Dict[str, Any]:
    """Score only field-level checks explicitly entered from independent human review."""
    manifest_path = Path(audit_output_path)
    if not manifest_path.exists():
        return {
            "status": "pending",
            "reason": "No independent human audit manifest exists yet.",
            "planned_sample_size": len(SAMPLED_APP_IDS),
            "planned_sample_ids": SAMPLED_APP_IDS,
            "metrics": None,
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "ready_to_score":
        manifest["status"] = "pending"
        manifest["metrics"] = None
        return manifest

    records = manifest.get("audit_records", [])
    audit_by_id = {item.get("id"): item for item in records if isinstance(item, dict)}
    if set(audit_by_id) != set(SAMPLED_APP_IDS):
        manifest["status"] = "pending"
        manifest["reason"] = "The human audit must contain every planned sample ID before scoring."
        manifest["metrics"] = None
        return manifest

    try:
        first_pass = _load_records(first_pass_path)
        final_pass = _load_records(final_pass_path)
    except (OSError, json.JSONDecodeError):
        first_pass, final_pass = {}, {}
    if not set(SAMPLED_APP_IDS).issubset(first_pass) or not set(SAMPLED_APP_IDS).issubset(final_pass):
        manifest["status"] = "pending"
        manifest["reason"] = "Capture real first-pass and final-pass records before scoring the manual audit."
        manifest["metrics"] = None
        return manifest

    first_correct = final_correct = scorable_fields = unverifiable = 0
    first_app_correct = final_app_correct = scorable_apps = 0
    scored_records = []
    concrete_misses = []

    for app_id in SAMPLED_APP_IDS:
        audit_record = audit_by_id[app_id]
        field_checks = audit_record.get("fields", {})
        first_app_all = final_app_all = True
        app_scorable = True
        scored_fields = {}

        for field in AUDIT_FIELDS:
            check = field_checks.get(field, {})
            source_url = check.get("source_url", "")
            status = check.get("status")
            valid_url = urlsplit(source_url).scheme in {"http", "https"} and bool(urlsplit(source_url).netloc)
            if status != "verified" or not valid_url or "ground_truth" not in check:
                unverifiable += 1
                app_scorable = False
                first_app_all = final_app_all = False
                scored_fields[field] = {"status": "unverifiable", "source_url": source_url}
                continue

            expected = check["ground_truth"]
            first_value = first_pass[app_id].get(field)
            final_value = final_pass[app_id].get(field)
            first_match = _matches(field, first_value, expected)
            final_match = _matches(field, final_value, expected)
            scorable_fields += 1
            first_correct += int(first_match)
            final_correct += int(final_match)
            first_app_all &= first_match
            final_app_all &= final_match
            scored_fields[field] = {
                "status": "verified",
                "source_url": source_url,
                "ground_truth": expected,
                "first_pass": first_value,
                "final_pass": final_value,
                "first_pass_status": "correct" if first_match else "incorrect",
                "final_pass_status": "correct" if final_match else "incorrect",
            }
            if not first_match and len(concrete_misses) < 6:
                concrete_misses.append({
                    "app_id": app_id,
                    "field": field,
                    "first_pass_value": first_value,
                    "checked_value": expected,
                    "final_pass_value": final_value,
                    "source_url": source_url,
                })

        if app_scorable:
            scorable_apps += 1
            first_app_correct += int(first_app_all)
            final_app_correct += int(final_app_all)
        scored_records.append({"id": app_id, "fields": scored_fields})

    manifest["status"] = "complete"
    manifest["sample_size"] = len(SAMPLED_APP_IDS)
    manifest["sampled_app_ids"] = SAMPLED_APP_IDS
    manifest["audit_records"] = scored_records
    manifest["concrete_misses"] = concrete_misses
    manifest["metrics"] = {
        "first_pass": {
            "field_level_accuracy_pct": round(first_correct / scorable_fields * 100, 1) if scorable_fields else None,
            "field_numerator": first_correct,
            "field_denominator": scorable_fields,
            "app_level_accuracy_pct": round(first_app_correct / scorable_apps * 100, 1) if scorable_apps else None,
            "app_numerator": first_app_correct,
            "app_denominator": scorable_apps,
        },
        "final_pass": {
            "field_level_accuracy_pct": round(final_correct / scorable_fields * 100, 1) if scorable_fields else None,
            "field_numerator": final_correct,
            "field_denominator": scorable_fields,
            "app_level_accuracy_pct": round(final_app_correct / scorable_apps * 100, 1) if scorable_apps else None,
            "app_numerator": final_app_correct,
            "app_denominator": scorable_apps,
        },
        "unverifiable_fields": unverifiable,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def prepare_review_queue(
    first_pass_path: str = "data/first_pass.json",
    final_pass_path: str = "data/final_results.json",
    output_path: str = "data/review_queue.json",
) -> Dict[str, Any]:
    """Prepare the fixed sample for independent review without inventing ground truth."""
    first_pass = _load_records(first_pass_path)
    final_pass = _load_records(final_pass_path)
    queue = []
    for app_id in SAMPLED_APP_IDS:
        first = first_pass.get(app_id, {})
        final = final_pass.get(app_id, {})
        urls = list(dict.fromkeys(
            item.get("url") for item in final.get("evidence", [])
            if isinstance(item.get("url"), str) and item.get("url")
        ))
        queue.append({
            "id": app_id,
            "name": final.get("name") or first.get("name"),
            "category": final.get("category") or first.get("category"),
            "candidate_sources": urls,
            "fields": {
                field: {
                    "first_pass": first.get(field),
                    "final_pass": final.get(field),
                    "review_status": "pending",
                    "checked_value": None,
                    "official_source_url": None,
                }
                for field in AUDIT_FIELDS
            },
        })
    output = {
        "purpose": "Reviewer worksheet; values here are not ground truth or an accuracy score.",
        "sample_rule": "Two fixed IDs from each of the nine supplied categories.",
        "entries": queue,
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description="Score an independently documented human audit")
    parser.add_argument("--first-pass", default="data/first_pass.json")
    parser.add_argument("--final-pass", default="data/final_results.json")
    parser.add_argument("--manifest", default="data/audit.json")
    parser.add_argument("--prepare", action="store_true", help="Generate a reviewer worksheet without scoring")
    args = parser.parse_args()
    if args.prepare:
        queue = prepare_review_queue(args.first_pass, args.final_pass)
        print(f"Prepared {len(queue['entries'])} independent review entries in data/review_queue.json.")
        return
    report = run_audit(args.first_pass, args.final_pass, args.manifest)
    if report.get("status") != "complete":
        print("Human audit pending; no accuracy score was calculated.")
        print(report.get("reason", "Add independently checked field values and source URLs to the manifest."))
        return
    print(json.dumps(report.get("metrics", {}), indent=2))


if __name__ == "__main__":
    main()
