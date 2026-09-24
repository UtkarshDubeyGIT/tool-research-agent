import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from openai import OpenAI
from src.models import (
    AppRecord,
    CredentialAccess,
    EvidenceItem,
    RawDocument
)
from src.retrieval import DocumentFetcher, SourceDiscovery
from src.jev_client import JevClient
from src.rules import evaluate_api_breadth, evaluate_buildability


DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")


class ResearchOrchestrator:
    """Repeatable per-app research agent orchestrating Firecrawl retrieval, GPT-6 Luna extraction, and Jev decisions."""

    def __init__(
        self,
        apps_file: str = "data/apps.json",
        output_file: str = "data/final_results.json",
        cache_dir: str = "data/cache",
        mode: str = "cascade"
    ):
        self.apps_file = apps_file
        self.output_file = output_file
        self.mode = mode
        self.fetcher = DocumentFetcher(cache_dir=cache_dir)
        self.jev = JevClient()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.model = DEFAULT_OPENAI_MODEL
        self.client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None

        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)
        self.apps = self._load_apps()

    def _load_apps(self) -> List[Dict[str, Any]]:
        with open(self.apps_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_existing_results(self) -> Dict[int, AppRecord]:
        if not os.path.exists(self.output_file):
            return {}
        try:
            with open(self.output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {item["id"]: AppRecord(**item) for item in data}
        except Exception:
            return {}

    def _save_all_results(self, records: Dict[int, AppRecord]) -> None:
        sorted_records = [records[k].model_dump() for k in sorted(records.keys())]
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(sorted_records, f, indent=2)

    def research_app(self, app_meta: Dict[str, Any], dual_fetch: bool = False) -> AppRecord:
        app_id = app_meta["id"]
        name = app_meta["name"]
        category = app_meta["category"]
        hint = app_meta.get("website_hint", "")
        notes = app_meta.get("notes", "")

        # 1. Discover & Fetch
        seed_urls = SourceDiscovery.resolve_seed_urls(hint, name)
        primary_url = seed_urls[0]
        
        doc = self.fetcher.fetch(primary_url, prefer_firecrawl=True, dual_fetch=dual_fetch)
        retrieved_at = doc.timestamp or datetime.now(timezone.utc).isoformat()
        excerpt = doc.raw_markdown[:4000] if doc.raw_markdown else f"{name} documentation for {category}. Hint: {hint}. Notes: {notes}"

        # 2. Extract candidate facts with GPT-6 Luna or deterministic rule base
        candidate_data = self._generate_candidate_record(app_meta, doc, excerpt)

        # 3. Jev Decision Verification Cascade (if cascade mode)
        if self.mode == "cascade" and doc.raw_markdown:
            jev_classifications = self.jev.classify_access_and_auth(excerpt)
            
            # Map Jev Noul answers to credential access
            cred_dict = candidate_data.get("credential_access", {})
            if "self_serve_signup" in jev_classifications:
                p = jev_classifications["self_serve_signup"].get("noul", 0.5)
                cred_dict["self_serve_signup"] = "yes" if p > 0.6 else ("no" if p < 0.3 else cred_dict.get("self_serve_signup", "unknown"))
            if "paid_plan_required" in jev_classifications:
                p = jev_classifications["paid_plan_required"].get("noul", 0.5)
                cred_dict["paid_plan_required"] = "yes" if p > 0.6 else ("no" if p < 0.3 else cred_dict.get("paid_plan_required", "unknown"))
            if "admin_approval_required" in jev_classifications:
                p = jev_classifications["admin_approval_required"].get("noul", 0.5)
                cred_dict["admin_approval_required"] = "yes" if p > 0.6 else ("no" if p < 0.3 else cred_dict.get("admin_approval_required", "unknown"))
            if "partner_approval_required" in jev_classifications:
                p = jev_classifications["partner_approval_required"].get("noul", 0.5)
                cred_dict["partner_approval_required"] = "yes" if p > 0.6 else ("no" if p < 0.3 else cred_dict.get("partner_approval_required", "unknown"))

            candidate_data["credential_access"] = cred_dict

            # Verify claims with Jev
            for ev in candidate_data.get("evidence", []):
                claim = ev.get("claim", "")
                quote = ev.get("quote", "")
                # Compare each claim with the retrieved source, never with its own proposed quote.
                jev_res = self.jev.verify_claim(claim, excerpt)
                ev["verification"] = jev_res.get("choice", "supported")

        # 4. Code-owned rule composition
        cred_access = CredentialAccess(**candidate_data.get("credential_access", {}))
        auth_methods = candidate_data.get("auth_methods", [])
        api_types = candidate_data.get("api_types", [])

        breadth = evaluate_api_breadth(
            endpoint_count=int(candidate_data.get("documented_endpoint_count", 0) or 0),
            text_indicators=excerpt,
            api_types=api_types
        )
        verdict, blocker = evaluate_buildability(
            credential_access=cred_access,
            auth_methods=auth_methods,
            api_types=api_types,
            existing_blocker=candidate_data.get("main_blocker", "none")
        )

        record = AppRecord(
            id=app_id,
            name=name,
            category=category,
            website_hint=hint,
            summary=candidate_data.get("summary", f"{name} integration and API platform."),
            auth_methods=auth_methods,
            credential_access=cred_access,
            api_types=api_types,
            api_breadth=breadth,
            existing_mcp=candidate_data.get("existing_mcp", "unknown"),
            buildability=verdict,
            main_blocker=blocker,
            confidence=candidate_data.get("confidence", "high"),
            evidence=[EvidenceItem(**e) for e in candidate_data.get("evidence", [])],
            research_status=self._candidate_status(candidate_data, doc),
            notes=notes
        )
        return record

    def _generate_candidate_record(self, app_meta: Dict[str, Any], doc: RawDocument, excerpt: str) -> Dict[str, Any]:
        """Generate claims only from a fetched source; unresolved cases stay unknown."""
        if not self.client:
            return self._unknown_candidate_record("OPENAI_API_KEY is not configured.")
        if not doc.raw_markdown:
            return self._unknown_candidate_record("No readable source document was retrieved.")

        try:
            system_prompt = (
                "You are an API researcher. Extract only facts supported by the supplied official documentation. "
                "Return a JSON object with the AppRecord fields and documented_endpoint_count. Every non-unknown "
                "material value must have an evidence item with its source URL and a short exact quote copied from "
                "the excerpt. Count endpoints only when the excerpt enumerates them; otherwise use null. If a fact is "
                "not established by the excerpt, return unknown. Do not use prior company knowledge."
            )
            user_prompt = (
                f"App: {app_meta['name']}\nCategory: {app_meta['category']}\n"
                f"Website hint: {app_meta.get('website_hint', '')}\n\nSource URL: {doc.final_url}\n"
                f"Excerpt:\n{excerpt[:3000]}"
            )
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            content = resp.choices[0].message.content
            if not content:
                return self._unknown_candidate_record("The model returned an empty response.")
            return json.loads(content)
        except Exception:
            return self._unknown_candidate_record("Model extraction failed; manual review is required.")

    @staticmethod
    def _unknown_candidate_record(reason: str) -> Dict[str, Any]:
        return {
            "summary": "Research is incomplete; see review status.",
            "auth_methods": ["unknown"],
            "credential_access": {
                "self_serve_signup": "unknown",
                "free_or_trial_credentials": "unknown",
                "paid_plan_required": "unknown",
                "admin_approval_required": "unknown",
                "partner_approval_required": "unknown"
            },
            "api_types": [],
            "api_breadth": "unknown",
            "existing_mcp": "unknown",
            "buildability": "unknown",
            "main_blocker": reason,
            "confidence": "low",
            "evidence": [],
            "research_status": "blocked"
        }

    @staticmethod
    def _candidate_status(candidate_data: Dict[str, Any], doc: RawDocument) -> str:
        if not doc.raw_markdown:
            return "blocked"

        evidence = candidate_data.get("evidence", [])
        if not evidence:
            return "needs_review"

        source_urls = {doc.url.rstrip("/"), doc.final_url.rstrip("/")}
        source_text = " ".join(doc.raw_markdown.split())
        evidence_fields = {item.get("field") for item in evidence}
        required_fields = {"summary"}
        if candidate_data.get("auth_methods") not in (None, [], ["unknown"]):
            required_fields.add("auth_methods")
        credentials = candidate_data.get("credential_access", {})
        if any(value != "unknown" for value in credentials.values()):
            required_fields.add("credential_access")
        if candidate_data.get("api_types") not in (None, [], ["unknown"]):
            required_fields.add("api_types")
        if candidate_data.get("api_breadth", "unknown") != "unknown":
            required_fields.add("api_breadth")
        if candidate_data.get("existing_mcp", "unknown") != "unknown":
            required_fields.add("existing_mcp")
        if candidate_data.get("buildability", "unknown") != "unknown":
            required_fields.add("buildability")
        if not required_fields.issubset(evidence_fields):
            return "needs_review"

        for item in evidence:
            quote = " ".join(str(item.get("quote", "")).split())
            if (item.get("url", "").rstrip("/") not in source_urls or
                    not quote or quote not in source_text or
                    item.get("verification") != "supported"):
                return "needs_review"
        return "complete"


def main():
    parser = argparse.ArgumentParser(description="Repeatable Research Agent for Composio AI Product Ops Take-Home")
    parser.add_argument("--app-id", type=int, help="Run research for a single app ID (1-90)")
    parser.add_argument("--all", action="store_true", help="Process all apps in dataset")
    parser.add_argument("--resume", action="store_true", help="Skip already completed app IDs")
    parser.add_argument("--refresh", action="store_true", help="Force refresh even if already completed")
    parser.add_argument("--limit", type=int, help="Limit number of apps to process")
    parser.add_argument("--mode", choices=["first_pass", "cascade"], default="cascade", help="Research mode")
    parser.add_argument("--output", default="data/final_results.json", help="Output JSON path")
    parser.add_argument("--dual-fetch", action="store_true", help="Dual-fetch with Firecrawl and Direct HTTP for audit")

    args = parser.parse_args()

    orchestrator = ResearchOrchestrator(output_file=args.output, mode=args.mode)
    existing_results = orchestrator._load_existing_results()

    apps_to_run = orchestrator.apps
    if args.app_id:
        apps_to_run = [a for a in apps_to_run if a["id"] == args.app_id]
        if not apps_to_run:
            print(f"Error: App ID {args.app_id} not found in range 1-90.")
            sys.exit(1)
    elif args.limit:
        apps_to_run = apps_to_run[:args.limit]

    print(f"[*] Starting Research Pipeline (mode={args.mode}, target={len(apps_to_run)} apps, output={args.output})")
    
    count = 0
    for app in apps_to_run:
        app_id = app["id"]
        if (args.resume and not args.refresh and app_id in existing_results and
                existing_results[app_id].research_status == "complete"):
            continue

        print(f"  -> Investigating #{app['id']}: {app['name']} ({app['category']})...")
        record = orchestrator.research_app(app, dual_fetch=args.dual_fetch)
        existing_results[app_id] = record
        orchestrator._save_all_results(existing_results)
        count += 1

    print(f"[✓] Research complete. Successfully saved {len(existing_results)} records to {args.output}")


if __name__ == "__main__":
    main()
