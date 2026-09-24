import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List
from src.validate import EvidenceValidator


def _write_json(path: str, value: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")


def analyze_dataset(
    results_path: str = "data/final_results.json",
    audit_path: str = "data/audit.json",
    output_path: str = "site/data/summary.json",
) -> Dict[str, Any]:
    """Generate provisional analytics and all static data files from the records."""
    if not os.path.exists(results_path):
        raise FileNotFoundError(f"Results file {results_path} not found.")

    with open(results_path, "r", encoding="utf-8") as f:
        records: List[Dict[str, Any]] = json.load(f)
    with open("data/apps.json", "r", encoding="utf-8") as f:
        supplied_apps = json.load(f)

    audit_data: Dict[str, Any] = {}
    if os.path.exists(audit_path):
        with open(audit_path, "r", encoding="utf-8") as f:
            audit_data = json.load(f)

    total_apps = len(records)
    if total_apps == 0:
        raise ValueError("No result records are available to analyze.")
    categories = sorted({r.get("category", "Unknown") for r in records})

    verdict_counts = Counter(r.get("buildability", "unknown") for r in records)
    buildability_breakdown = {
        verdict: {
            "count": verdict_counts.get(verdict, 0),
            "percentage": round(verdict_counts.get(verdict, 0) / total_apps * 100, 1),
        }
        for verdict in ["buildable_now", "conditional", "outreach_needed", "unknown"]
    }

    all_auth_methods = []
    auth_patterns = {"oauth2_only": 0, "api_key_only": 0, "hybrid_both": 0, "token_or_other": 0}
    for record in records:
        methods = set(record.get("auth_methods", []))
        all_auth_methods.extend(methods)
        has_oauth = "oauth2" in methods
        has_key = any(method in methods for method in ["api_key", "basic"])
        if has_oauth and has_key:
            auth_patterns["hybrid_both"] += 1
        elif has_oauth:
            auth_patterns["oauth2_only"] += 1
        elif has_key:
            auth_patterns["api_key_only"] += 1
        else:
            auth_patterns["token_or_other"] += 1
    auth_counts = Counter(all_auth_methods)
    auth_breakdown = {
        key: {"count": value, "percentage": round(value / total_apps * 100, 1)}
        for key, value in auth_counts.items()
    }

    credential_fields = [
        "self_serve_signup", "free_or_trial_credentials", "paid_plan_required",
        "admin_approval_required", "partner_approval_required",
    ]
    gating_totals = {}
    for field in credential_fields:
        gating_totals[field] = {
            answer: sum(1 for r in records if r.get("credential_access", {}).get(field, "unknown") == answer)
            for answer in ["yes", "no", "unknown"]
        }

    category_matrix = {}
    for category in categories:
        subset = [r for r in records if r.get("category") == category]
        count = len(subset)
        category_auth = Counter(method for r in subset for method in r.get("auth_methods", []))
        category_matrix[category] = {
            "total": count,
            "buildable_now": sum(r.get("buildability") == "buildable_now" for r in subset),
            "conditional": sum(r.get("buildability") == "conditional" for r in subset),
            "outreach_needed": sum(r.get("buildability") == "outreach_needed" for r in subset),
            "unknown": sum(r.get("buildability") == "unknown" for r in subset),
            "self_serve_pct": round(sum(r.get("credential_access", {}).get("self_serve_signup") == "yes" for r in subset) / count * 100, 1) if count else 0,
            "partner_gated_count": sum(r.get("credential_access", {}).get("partner_approval_required") == "yes" for r in subset),
            "dominant_auth": category_auth.most_common(1)[0][0] if category_auth else "unknown",
        }

    mcp_counts = Counter(r.get("existing_mcp", "unknown") for r in records)
    mcp_breakdown = {
        "official": mcp_counts.get("official", 0),
        "third_party": mcp_counts.get("third_party", 0),
        "none_found": mcp_counts.get("none_found", 0),
        "unknown": mcp_counts.get("unknown", 0),
        "total_with_mcp": mcp_counts.get("official", 0) + mcp_counts.get("third_party", 0),
        "mcp_readiness_pct": round((mcp_counts.get("official", 0) + mcp_counts.get("third_party", 0)) / total_apps * 100, 1),
    }

    blocker_clusters = {
        "partner_application_or_sales_gate": 0,
        "active_paid_plan_required": 0,
        "admin_or_enterprise_authorization": 0,
        "closed_portal_or_unreleased_api": 0,
    }
    for record in records:
        blocker = (record.get("main_blocker") or "none").lower()
        if blocker == "none":
            continue
        if any(word in blocker for word in ["partner", "sales contact", "commercial agreement", "underwriting", "annual subscription"]):
            blocker_clusters["partner_application_or_sales_gate"] += 1
        elif any(word in blocker for word in ["paid", "seat", "pro and enterprise", "paid subscription"]):
            blocker_clusters["active_paid_plan_required"] += 1
        elif any(word in blocker for word in ["admin", "connected app", "tenant", "authorization in production"]):
            blocker_clusters["admin_or_enterprise_authorization"] += 1
        else:
            blocker_clusters["closed_portal_or_unreleased_api"] += 1

    validator = EvidenceValidator()
    def quote_match_stats(rows):
        total = exact = 0
        for row in rows:
            for evidence in row.get("evidence", []):
                total += 1
                sources = validator.cached_sources.get(validator._canonical_url(evidence.get("url", "")), [])
                quote = validator._normalize(evidence.get("quote", ""))
                if quote and any(quote in validator._normalize(source) for source in sources):
                    exact += 1
        return {"exact": exact, "total": total, "percentage": round(exact / total * 100, 1) if total else None}

    try:
        with open("data/first_pass.json", "r", encoding="utf-8") as f:
            first_pass_records = json.load(f)
    except (OSError, json.JSONDecodeError):
        first_pass_records = []
    evidence_quality = {
        "first_pass": quote_match_stats(first_pass_records),
        "final_pass": quote_match_stats(records),
        "metric_definition": "Exact quote matches against saved source snapshots; this is not a human accuracy score.",
    }
    record_status_counts = Counter(r.get("research_status", "needs_review") for r in records)
    audit_complete = audit_data.get("status") == "complete"
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_status": "verified" if record_status_counts.get("complete", 0) == total_apps and audit_complete else "provisional",
        "quality_notice": (
            "All records passed source checks and the independent sample audit is complete."
            if record_status_counts.get("complete", 0) == total_apps and audit_complete
            else (
                f"{record_status_counts.get('complete', 0)} records have source-checked logged claims; "
                f"{record_status_counts.get('needs_review', 0) + record_status_counts.get('blocked', 0)} still need review. "
                "The independent manual sample audit is pending."
            )
        ),
        "coverage": {
            "supplied_input_count": len(supplied_apps),
            "records_present": total_apps,
            "complete_records": record_status_counts.get("complete", 0),
            "needs_review_records": record_status_counts.get("needs_review", 0),
            "blocked_records": record_status_counts.get("blocked", 0),
            "expected_prompt_count": 100,
            "categories_count": len(categories),
            "scope_discrepancy_note": "The assignment says 100 apps, while its supplied table contains 90 across 9 categories and ends at #90 PitchBook.",
        },
        "buildability_breakdown": buildability_breakdown,
        "auth_breakdown": auth_breakdown,
        "auth_patterns": auth_patterns,
        "gating_totals": gating_totals,
        "category_matrix": category_matrix,
        "mcp_breakdown": mcp_breakdown,
        "blocker_clusters": blocker_clusters,
        "evidence_quality": evidence_quality,
        "audit_status": "complete" if audit_complete else "pending",
        "audit_metrics": audit_data.get("metrics", {}) if audit_complete else {},
        "concrete_misses": audit_data.get("concrete_misses", []) if audit_complete else [],
        "sample_selection_rule": audit_data.get("sample_selection_rule", ""),
        "planned_sample_ids": audit_data.get("planned_sample_ids", []),
    }

    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    _write_json(output_path, summary)
    _write_json(os.path.join(output_dir, "records.json"), records)
    with open(os.path.join(output_dir, "records.csv"), "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "id", "name", "category", "website_hint", "summary", "auth_methods",
            "credential_access", "api_types", "api_breadth", "existing_mcp", "buildability",
            "main_blocker", "confidence", "research_status", "notes", "evidence",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for record in records:
            row = dict(record)
            for key in ["auth_methods", "credential_access", "api_types", "evidence"]:
                row[key] = json.dumps(row.get(key), ensure_ascii=False)
            writer.writerow(row)
    with open(os.path.join(output_dir, "bundle.js"), "w", encoding="utf-8") as f:
        f.write("window.CASE_STUDY_DATA = ")
        f.write(json.dumps({"summary": summary, "records": records}, ensure_ascii=False))
        f.write(";\n")
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate analytics and static datasets from research records")
    parser.add_argument("--results", default="data/final_results.json")
    parser.add_argument("--audit", default="data/audit.json")
    parser.add_argument("--output", default="site/data/summary.json")
    args = parser.parse_args()
    summary = analyze_dataset(args.results, args.audit, args.output)
    coverage = summary["coverage"]
    print(f"Input entries: {coverage['supplied_input_count']}; records present: {coverage['records_present']}")
    print(f"Provisional record statuses: {coverage['complete_records']} complete, {coverage['needs_review_records']} needs review, {coverage['blocked_records']} blocked")
    print(f"Audit status: {summary['audit_status']}; no accuracy score is shown unless human checks are complete.")
    print(f"Generated static datasets in {os.path.dirname(args.output) or '.'}")


if __name__ == "__main__":
    main()
