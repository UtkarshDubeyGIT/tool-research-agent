# Composio AI Product Ops take-home case study

An independent research-agent prototype and static case-study page for the Product Ops take-home assignment.

## Current status

The assignment prompt says 100 apps, but its supplied table contains 90 entries across 9 categories and ends at #90 PitchBook. The repository preserves those 90 inputs in `data/apps.json`.

The checked-in result rows are a **provisional snapshot**, not a verified 90-app research run. All 90 are marked `needs_review`; the current validator reports 0/90 passing and 279 evidence issues, with no schema errors or logical contradictions. The independent human audit is pending. The previous “improved accuracy” figures came from a synthetic first pass and static expected values, so those rows and claims were removed. No accuracy score is currently reported.

## Latest local verification

On 25 September 2026, a one-app Stripe (#81) run used the temporary local OpenAI and OpenRouter keys with a saved direct source page. The cascade produced six candidate evidence items: four were marked supported by Jev and two had insufficient evidence. Exact source validation still failed, so the record remains needs_review; this pilot is not an accuracy score. Firecrawl was disabled for this cached-source pilot to limit paid requests. The full 90-app batch was not rerun.

The local test suite passed (5 tests). The checked-in 90-row dataset still has 0 passing records, 279 evidence issues, an empty first-pass baseline, and a pending 18-app human audit. Complete those checks before submitting the dataset as verified research.

## Deliverables

- Case-study page: [GitHub Pages](https://utkarshdubeygit.github.io/tool-research-agent/)
- Source repository: [GitHub](https://github.com/UtkarshDubeyGIT/tool-research-agent)
- Vercel: the repository is configured to serve `site/`; import instructions are below. The current site is static and does not run the Python research agent on Vercel.

## Run the agent locally

Prerequisites: Python 3.10+ and Git.

```bash
git clone https://github.com/UtkarshDubeyGIT/tool-research-agent.git
cd tool-research-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
```

Put local CLI keys in the ignored `.env.local` file. The CLI reads `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and `FIRECRAWL_API_KEY`; `OPENAI_MODEL` defaults to `gpt-6-luna`. Never put real keys in `.env.example`, source files, generated site data, or the README. `.env.local` is ignored by Git.

```bash
# Try one app first; uncached runs use paid APIs
python -m src.research --app-id 81 --mode cascade --output stripe-pilot.json

# Capture a real first pass before making manual corrections
python -m src.research --all --mode first_pass --output data/first_pass.json

# Run the verification cascade and checkpoint results
python -m src.research --all --resume

# Check schemas, contradictions, cached source URLs, and exact quote matches
python -m src.validate

# Score an audit only after recording field-level human checks in data/audit.json
python -m src.audit

# Regenerate summary, JSON, CSV, and the static browser bundle
python -m src.analyze
```

Without a readable source page or OpenAI key, the agent leaves findings unknown/blocked. Without an OpenRouter key, Jev claim verification is marked insufficient. The research code currently fetches one resolved seed page per app; multi-page documentation discovery, bounded retries/concurrency, and systematic conflict handling remain work to do.

The human audit manifest is intentionally pending. For each `planned_sample_ids` entry, add `fields` containing `auth_methods`, `credential_access`, `api_breadth`, and `buildability`. Each field entry must include `status: "verified"` or `"unverifiable"`; verified entries also need `ground_truth` and an official `source_url`. Example shape for one app:

```json
{
  "id": 1,
  "fields": {
    "auth_methods": {"status": "verified", "ground_truth": ["replace with checked value"], "source_url": "https://official.example/docs"},
    "credential_access": {"status": "unverifiable", "source_url": "https://official.example/docs"},
    "api_breadth": {"status": "verified", "ground_truth": "replace with checked value", "source_url": "https://official.example/docs"},
    "buildability": {"status": "verified", "ground_truth": "replace with checked value", "source_url": "https://official.example/docs"}
  }
}
```

After all sample records are filled, change the manifest status to `ready_to_score` and run `python -m src.audit`. Keep unverifiable fields out of the denominator. The scorer requires real first-pass and final-pass records and will not invent a baseline.

## Deploy the static page to Vercel

1. Import `UtkarshDubeyGIT/tool-research-agent` into Vercel.
2. Set the project root to the repository root. Select the **Other** framework preset.
3. Leave the build command empty and use `site` as the output directory. `vercel.json` already sets this output directory.
4. Deploy. Git-connected pushes to the production branch will create deployments; preview branches create previews.

This deployment serves HTML, CSS, JavaScript, and pre-generated JSON/CSV only. **No production API keys are needed or used by the deployed page.** The Python CLI is not a Vercel function and does not run on page requests.

If a server-side research endpoint is added later, add its keys in Vercel Project Settings → Environment Variables, scoped to the required environments. Use the unprefixed names `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and `FIRECRAWL_API_KEY`, plus `OPENAI_MODEL` if needed. Never use client-exposed prefixes such as `NEXT_PUBLIC_` or `VITE_` for secrets. Adding environment variables requires a new deployment.

## Repository map

- `data/apps.json`: supplied input list.
- `data/final_results.json`: provisional current records.
- `data/first_pass.json`: empty until a real baseline run is captured.
- `data/audit.json`: pending manifest for independent checks; no synthetic accuracy result.
- `data/cache/`: retrieval snapshots used for source-quote matching.
- `src/`: retrieval, extraction, decision, rules, validation, analysis, and audit CLI.
- `site/`: static case-study page and generated JSON/CSV/browser bundle.

The local test suite can be rerun with `pytest -q`; all 5 tests passed during the latest review.
