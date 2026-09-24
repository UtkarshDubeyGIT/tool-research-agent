import os
import json
import argparse
from typing import Dict, Any, List
from collections import Counter


def analyze_dataset(
    results_path: str = "data/final_results.json",
    audit_path: str = "data/audit.json",
    output_path: str = "site/data/summary.json"
) -> Dict[str, Any]:
    """Computes all statistical aggregates, category patterns, and matrices from validated JSON."""
    if not os.path.exists(results_path):
        raise FileNotFoundError(f"Results file {results_path} not found.")

    with open(results_path, "r", encoding="utf-8") as f:
        records: List[Dict[str, Any]] = json.load(f)

    audit_data = {}
    if os.path.exists(audit_path):
        with open(audit_path, "r", encoding="utf-8") as f:
            audit_data = json.load(f)

    total_apps = len(records)
    categories = sorted(list(set(r["category"] for r in records)))

    # 1. Buildability Distribution
    verdict_counts = Counter(r["buildability"] for r in records)
    buildability_breakdown = {
        "buildable_now": {
            "count": verdict_counts.get("buildable_now", 0),
            "percentage": round(verdict_counts.get("buildable_now", 0) / total_apps * 100, 1)
        },
        "conditional": {
            "count": verdict_counts.get("conditional", 0),
            "percentage": round(verdict_counts.get("conditional", 0) / total_apps * 100, 1)
        },
        "outreach_needed": {
            "count": verdict_counts.get("outreach_needed", 0),
            "percentage": round(verdict_counts.get("outreach_needed", 0) / total_apps * 100, 1)
        },
        "unknown": {
            "count": verdict_counts.get("unknown", 0),
            "percentage": round(verdict_counts.get("unknown", 0) / total_apps * 100, 1)
        }
    }

    # 2. Auth Methods Distribution
    all_auth_methods = []
    auth_patterns = {"oauth2_only": 0, "api_key_only": 0, "hybrid_both": 0, "token_or_other": 0}
    for r in records:
        methods = set(r.get("auth_methods", []))
        all_auth_methods.extend(methods)
        has_oauth = "oauth2" in methods
        has_key = any(k in methods for k in ["api_key", "basic"])
        if has_oauth and has_key:
            auth_patterns["hybrid_both"] += 1
        elif has_oauth:
            auth_patterns["oauth2_only"] += 1
        elif has_key:
            auth_patterns["api_key_only"] += 1
        else:
            auth_patterns["token_or_other"] += 1

    auth_counts = Counter(all_auth_methods)
    auth_breakdown = {k: {"count": v, "percentage": round(v / total_apps * 100, 1)} for k, v in auth_counts.items()}

    # 3. Credential Gating Analysis
    gating_totals = {
        "self_serve_signup": sum(1 for r in records if r["credential_access"]["self_serve_signup"] == "yes"),
        "free_or_trial_credentials": sum(1 for r in records if r["credential_access"]["free_or_trial_credentials"] == "yes"),
        "paid_plan_required": sum(1 for r in records if r["credential_access"]["paid_plan_required"] == "yes"),
        "admin_approval_required": sum(1 for r in records if r["credential_access"]["admin_approval_required"] == "yes"),
        "partner_approval_required": sum(1 for r in records if r["credential_access"]["partner_approval_required"] == "yes")
    }

    # 4. Category-by-Category Matrix
    category_matrix = {}
    for cat in categories:
        cat_records = [r for r in records if r["category"] == cat]
        cat_total = len(cat_records)
        category_matrix[cat] = {
            "total": cat_total,
            "buildable_now": sum(1 for r in cat_records if r["buildability"] == "buildable_now"),
            "conditional": sum(1 for r in cat_records if r["buildability"] == "conditional"),
            "outreach_needed": sum(1 for r in cat_records if r["buildability"] == "outreach_needed"),
            "self_serve_pct": round(sum(1 for r in cat_records if r["credential_access"]["self_serve_signup"] == "yes") / cat_total * 100, 1),
            "partner_gated_count": sum(1 for r in cat_records if r["credential_access"]["partner_approval_required"] == "yes"),
            "dominant_auth": Counter([m for r in cat_records for m in r.get("auth_methods", [])]).most_common(1)[0][0] if cat_records else "none"
        }

    # 5. MCP Ecosystem Readiness
    mcp_counts = Counter(r.get("existing_mcp", "none_found") for r in records)
    mcp_breakdown = {
        "official": mcp_counts.get("official", 0),
        "third_party": mcp_counts.get("third_party", 0),
        "none_found": mcp_counts.get("none_found", 0),
        "unknown": mcp_counts.get("unknown", 0),
        "total_with_mcp": mcp_counts.get("official", 0) + mcp_counts.get("third_party", 0),
        "mcp_readiness_pct": round((mcp_counts.get("official", 0) + mcp_counts.get("third_party", 0)) / total_apps * 100, 1)
    }

    # 6. Blocker Clustering
    blockers_list = []
    for r in records:
        b = r.get("main_blocker", "none")
        if b != "none" and b:
            blockers_list.append(b)
    
    # Categorize blockers into standardized clusters
    blocker_clusters = {
        "partner_application_or_sales_gate": 0,
        "active_paid_plan_required": 0,
        "admin_or_enterprise_authorization": 0,
        "closed_portal_or_unreleased_api": 0
    }
    for b in blockers_list:
        bl = b.lower()
        if any(k in bl for k in ["partner", "sales contact", "commercial agreement", "underwriting", "annual subscription"]):
            blocker_clusters["partner_application_or_sales_gate"] += 1
        elif any(k in bl for k in ["paid", "seat", "pro and enterprise", "paid subscription"]):
            blocker_clusters["active_paid_plan_required"] += 1
        elif any(k in bl for k in ["admin", "connected app", "tenant", "authorization in production"]):
            blocker_clusters["admin_or_enterprise_authorization"] += 1
        else:
            blocker_clusters["closed_portal_or_unreleased_api"] += 1

    summary = {
        "generated_at": records[0].get("evidence", [{}])[0].get("retrieved_at", "2026-09-24T23:30:00Z"),
        "coverage": {
            "total_researched": total_apps,
            "expected_prompt_count": 100,
            "scope_discrepancy_note": "The take-home PDF specification itemizes exactly 90 apps across Categories 1 through 9, omitting Category 10 (#91-#100). The pipeline preserves all 90 supplied entries without fabricating missing rows.",
            "categories_count": len(categories)
        },
        "buildability_breakdown": buildability_breakdown,
        "auth_breakdown": auth_breakdown,
        "auth_patterns": auth_patterns,
        "gating_totals": gating_totals,
        "category_matrix": category_matrix,
        "mcp_breakdown": mcp_breakdown,
        "blocker_clusters": blocker_clusters,
        "audit_metrics": audit_data.get("metrics", {}),
        "concrete_misses": audit_data.get("concrete_misses", []),
        "sample_selection_rule": audit_data.get("sample_selection_rule", "")
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Statistical Analysis & Pattern Generation Engine")
    parser.add_argument("--results", default="data/final_results.json", help="Path to final results JSON")
    parser.add_argument("--audit", default="data/audit.json", help="Path to audit JSON")
    parser.add_argument("--output", default="site/data/summary.json", help="Path to summary output JSON")

    args = parser.parse_args()
    summary = analyze_dataset(args.results, args.audit, args.output)

    print("\n================ SUMMARY ANALYSIS ================")
    print(f"Total Apps Researched: {summary['coverage']['total_researched']} / {summary['coverage']['expected_prompt_count']}")
    print(f"Buildable Now:         {summary['buildability_breakdown']['buildable_now']['count']} ({summary['buildability_breakdown']['buildable_now']['percentage']}%)")
    print(f"Conditional:           {summary['buildability_breakdown']['conditional']['count']} ({summary['buildability_breakdown']['conditional']['percentage']}%)")
    print(f"Outreach Needed:       {summary['buildability_breakdown']['outreach_needed']['count']} ({summary['buildability_breakdown']['outreach_needed']['percentage']}%)")
    print(f"MCP Readiness:         {summary['mcp_breakdown']['total_with_mcp']} apps ({summary['mcp_breakdown']['mcp_readiness_pct']}%)")
    print(f"[✓] Summary data exported to {args.output}")
    print("==================================================\n")


if __name__ == "__main__":
    main()
