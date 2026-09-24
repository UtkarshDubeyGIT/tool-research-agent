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

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "auth_methods": {"type": "array", "items": {"type": "string", "enum": ["oauth2", "api_key", "basic", "token", "other"]}},
        "credential_access": {
            "type": "object",
            "properties": {
                key: {"type": "string", "enum": ["yes", "no", "unknown"]}
                for key in (
                    "self_serve_signup", "free_or_trial_credentials",
                    "paid_plan_required", "admin_approval_required",
                    "partner_approval_required"
                )
            },
            "required": [
                "self_serve_signup", "free_or_trial_credentials",
                "paid_plan_required", "admin_approval_required",
                "partner_approval_required"
            ],
            "additionalProperties": False
        },
        "api_types": {"type": "array", "items": {"type": "string", "enum": ["rest", "graphql", "grpc", "soap", "webhooks", "other"]}},
        "documented_endpoint_count": {"type": ["integer", "null"]},
        "existing_mcp": {
            "type": "string",
            "enum": ["official", "third_party", "none_found", "unknown"]
        },
        "main_blocker": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "enum": [
                            "summary", "auth_methods", "credential_access",
                            "api_types", "api_breadth", "existing_mcp",
                            "buildability"
                        ]
                    },
                    "claim": {"type": "string"},
                    "quote": {"type": "string"},
                    "source_url": {"type": "string"}
                },
                "required": ["field", "claim", "quote", "source_url"],
                "additionalProperties": False
            }
        }
    },
    "required": [
        "summary", "auth_methods", "credential_access", "api_types",
        "documented_endpoint_count", "existing_mcp", "main_blocker", "evidence"
    ],
    "additionalProperties": False
}


class ResearchOrchestrator:
    """Repeatable per-app research agent orchestrating Firecrawl retrieval, GPT-6 Luna extraction, and Jev decisions."""

    def __init__(
        self,
        apps_file: str = "data/apps.json",
        output_file: str = "data/final_results.json",
        cache_dir: str = "data/cache",
        mode: str = "cascade",
        max_firecrawl_calls: int = 20,
        max_model_calls: int = 90,
        max_jev_calls: int = 360,
    ):
        self.apps_file = apps_file
        self.output_file = output_file
        self.mode = mode
        self.fetcher = DocumentFetcher(cache_dir=cache_dir, max_firecrawl_calls=max_firecrawl_calls)
        self.max_model_calls = max_model_calls
        self.max_jev_calls = max_jev_calls
        self.model_calls = 0
        self.jev_calls = 0
        self.jev = JevClient()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.model = DEFAULT_OPENAI_MODEL
        self.client = OpenAI(api_key=self.openai_api_key, timeout=30.0, max_retries=0) if self.openai_api_key else None

        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)
        self.apps = self._load_apps()
        # Source leads are frozen separately from generated findings for repeatability.
        try:
            leads = json.load(open("data/source_seeds.json", encoding="utf-8"))
            self.source_seeds = {int(app_id): urls[:2] for app_id, urls in leads.items()}
        except (OSError, ValueError, KeyError, TypeError):
            self.source_seeds = {}

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
        seed_urls = list(dict.fromkeys(
            self.source_seeds.get(app_id, []) + SourceDiscovery.resolve_seed_urls(hint, name)
        ))[:3]
        source_docs = []
        fallback_doc = None
        for url in seed_urls:
            candidate = self.fetcher.fetch(url, prefer_firecrawl=True, dual_fetch=dual_fetch)
            fallback_doc = candidate if fallback_doc is None else fallback_doc
            if candidate.status_code == 200 and len(candidate.raw_markdown) >= 300:
                if candidate.final_url not in {d.final_url for d in source_docs}:
                    source_docs.append(candidate)
            if len(source_docs) == 2:
                break
        doc = source_docs[0] if source_docs else fallback_doc
        excerpt = "\n\n".join(
            f"SOURCE URL: {source.final_url}\n{source.raw_markdown[:2700]}"
            for source in source_docs
        ) if source_docs else ""

        # 2. Extract candidate facts only from fetched, saved source content.
        candidate_data = self._generate_candidate_record(app_meta, doc, excerpt, source_docs)

        # 3. Verify each quote against its own page before spending a Jev call.
        if self.mode == "cascade" and source_docs:
            by_url = {source.final_url.rstrip("/"): source for source in source_docs}
            for ev in candidate_data.get("evidence", []):
                source = by_url.get(str(ev.get("url", "")).rstrip("/"))
                quote = " ".join(str(ev.get("quote", "")).split())
                source_text = " ".join(source.raw_markdown.split()) if source else ""
                if quote and quote in source_text and self.jev_calls < self.max_jev_calls:
                    self.jev_calls += 1
                    jev_res = self.jev.verify_claim(ev.get("claim", ""), source.raw_markdown[:4000])
                    ev["verification"] = jev_res.get("choice", "insufficient_evidence")
                else:
                    ev["verification"] = "insufficient_evidence"

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

        candidate_data["api_breadth"] = breadth
        candidate_data["buildability"] = verdict
        if candidate_data.get("research_status") == "blocked":
            blocker = candidate_data.get("main_blocker", blocker)
        status = ("blocked" if candidate_data.get("research_status") == "blocked"
                  else self._candidate_status(candidate_data, source_docs))

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
            confidence="medium" if status == "complete" else "low",
            evidence=[EvidenceItem(**e) for e in candidate_data.get("evidence", [])],
            research_status=status,
            notes=notes
        )
        return record

    def _generate_candidate_record(self, app_meta: Dict[str, Any], doc: RawDocument, excerpt: str, source_docs: List[RawDocument]) -> Dict[str, Any]:
        """Generate claims only from a fetched source; unresolved cases stay unknown."""
        if not self.client:
            return self._unknown_candidate_record("OPENAI_API_KEY is not configured.")
        if self.model_calls >= self.max_model_calls:
            return self._unknown_candidate_record("Model call budget reached.")
        if not source_docs:
            return self._unknown_candidate_record("No readable source document was retrieved.")

        try:
            system_prompt = (
                "Extract facts only from the supplied official source excerpt. "
                "Return one flat JSON object matching the schema; do not wrap it in app_record. "
                "Use unknown or an empty array when the excerpt does not establish a fact. "
                "Use a short one-line summary, and use the canonical enum labels for auth and API types. "
                "For each material value you provide, include an evidence item with its field, "
                "a narrow claim, a contiguous 8-20 word quote copied exactly from one source, "
                "and that source's exact SOURCE URL. "
                "If no exact quote is available, leave the field unknown or empty. "
                "Do not infer credential access from silence. "
                "Count endpoints only when explicitly enumerated; otherwise use null. "
                "Set existing_mcp to unknown unless this excerpt explicitly mentions an MCP. "
                "Do not use prior knowledge."
            )
            user_prompt = (
                f"App: {app_meta['name']}\nCategory: {app_meta['category']}\n"
                f"Source excerpts:\n{excerpt[:6500]}"
            )
            self.model_calls += 1
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "integration_research",
                        "strict": True,
                        "schema": EXTRACTION_SCHEMA
                    }
                },
                reasoning_effort="none",
                max_completion_tokens=2400
            )
            content = resp.choices[0].message.content
            if not content:
                return self._unknown_candidate_record("The model returned an empty response.")
            candidate = json.loads(content)
            if not isinstance(candidate, dict) or "evidence" not in candidate:
                return self._unknown_candidate_record("The model returned an invalid record shape.")
            source_by_url = {source.final_url.rstrip("/"): source for source in source_docs}
            for item in candidate["evidence"]:
                source = source_by_url.get(str(item.pop("source_url", "")).rstrip("/"))
                item["url"] = source.final_url if source else ""
                item["retrieved_at"] = source.timestamp if source else doc.timestamp
                # Markdown often puts punctuation on its own line. A shorter
                # contiguous quote is still verbatim and can be checked exactly.
                if source:
                    source_text = " ".join(source.raw_markdown.split())
                    quote = " ".join(str(item.get("quote", "")).split())
                    if quote not in source_text:
                        shorter = quote.rstrip(".,;:!?")
                        if shorter and shorter in source_text:
                            item["quote"] = shorter
                item["verification"] = "insufficient_evidence"
            return candidate
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            body = getattr(exc, "body", None)
            error = body.get("error", body) if isinstance(body, dict) else {}
            code = error.get("code") if isinstance(error, dict) else None
            param = error.get("param") if isinstance(error, dict) else None
            details = ", ".join(str(part) for part in (type(exc).__name__, status, code, param) if part)
            return self._unknown_candidate_record(f"Model extraction failed ({details}); manual review is required.")

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
    def _candidate_status(candidate_data: Dict[str, Any], source_docs: List[RawDocument]) -> str:
        if not source_docs:
            return "blocked"

        evidence = candidate_data.get("evidence", [])
        if not evidence:
            return "needs_review"

        source_text_by_url = {
            source.final_url.rstrip("/"): " ".join(source.raw_markdown.split())
            for source in source_docs
        }
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
            source_text = source_text_by_url.get(item.get("url", "").rstrip("/"), "")
            if (not quote or quote not in source_text or
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
    parser.add_argument("--max-firecrawl-calls", type=int, default=20, help="Maximum paid Firecrawl scrapes (default: 20)")
    parser.add_argument("--max-model-calls", type=int, default=90, help="Maximum OpenAI extraction calls (default: 90)")
    parser.add_argument("--max-jev-calls", type=int, default=360, help="Maximum OpenRouter verification calls (default: 360)")

    args = parser.parse_args()

    if min(args.max_firecrawl_calls, args.max_model_calls, args.max_jev_calls) < 0:
        parser.error("Call budgets must be nonnegative")
    orchestrator = ResearchOrchestrator(
        output_file=args.output, mode=args.mode,
        max_firecrawl_calls=args.max_firecrawl_calls,
        max_model_calls=args.max_model_calls,
        max_jev_calls=args.max_jev_calls,
    )
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

    statuses = {status: sum(r.research_status == status for r in existing_results.values())
                for status in ("complete", "needs_review", "blocked")}
    print(f"[✓] Saved {len(existing_results)} records to {args.output}. "
          f"Complete: {statuses['complete']}; needs review: {statuses['needs_review']}; "
          f"blocked: {statuses['blocked']}. "
          f"Paid calls: Firecrawl {orchestrator.fetcher.firecrawl_calls}, "
          f"OpenAI {orchestrator.model_calls}, OpenRouter {orchestrator.jev_calls}.")


if __name__ == "__main__":
    main()
