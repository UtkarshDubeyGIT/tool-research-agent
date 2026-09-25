# Integration field notes

An independent Product Ops take-home case study for researching API integration feasibility. The [public Vercel review page](https://composio-research-agent.dubey.page/) and [GitHub Pages mirror](https://utkarshdubeygit.github.io/tool-research-agent/) let an examiner search the app list, open a record, and follow checked claims to saved source quotes and the original page. The [repository](https://github.com/UtkarshDubeyGIT/tool-research-agent) contains the inputs, agent, first pass, final pass, source snapshots, and reviewer worksheet.

## Author

[Utkarsh Dubey](https://dubey.page/) · [GitHub](https://github.com/utkarshdubeygit) · [Email](mailto:utkarshd9990@gmail.com)

## Scope and current quality state

The brief says **100 apps in 10 categories**, but its supplied table has **90 entries in 9 categories**, ending at #90 PitchBook. `data/apps.json` preserves all 90 supplied rows; no missing entries were invented.

The final automated run has **90/90 records**, of which **60 pass every logged claim's source checks**, **28 need review**, and **2 are blocked by unavailable readable sources**. The validator reports **0 missing IDs, 0 schema errors, 0 logical contradictions, and 79 evidence issues across the 30 unresolved records**. A `needs_review` record may still contain individual checked claims. `unknown` means the retrieved sources did not establish an answer.

The first pass matched **260/292 quotes (89.0%)** to saved pages; the final pass matched **288/308 (93.5%)**. This is an **evidence traceability** measure, not answer accuracy. The independent 18-app field audit remains pending in `data/audit.json`, so no human accuracy or improvement percentage is claimed. `data/review_queue.json` gives the fixed sample and first/final values without inventing reviewer answers.

## Research method

1. `data/source_seeds.json` freezes candidate documentation leads separately from generated findings. The supplied website hint is a fallback.
2. The fetcher reuses successful source snapshots, tries direct HTTP, then uses a **budgeted Firecrawl v2** scrape when needed. Up to two readable pages inform a record.
3. OpenAI extracts a structured candidate with a short claim, exact quote, and source URL for each evidence item. Absent facts stay unknown.
4. Exact quote matching gates Jev verification; unsupported or contradictory claims keep the record in review. Python rules compute API breadth and buildability from candidate access and API details.
5. The validator checks schema, IDs, contradictions, source snapshots, quote matches, and Jev support. The analysis step publishes static JSON, CSV, and the browser bundle.

`data/run_manifest.json` records the input and source-lead hashes, run phases, request counts, and final quality status. It contains no keys.

## Reproduce locally

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
```

Put temporary local values for `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and `FIRECRAWL_API_KEY` in `.env.local`. This file is Git-ignored. `OPENAI_MODEL` defaults to `gpt-6-luna`. The first-pass and final-pass examples below make paid-call caps explicit; successful cached pages avoid additional Firecrawl calls.

```bash
python -m src.research --all --mode first_pass --output data/first_pass.json --max-firecrawl-calls 20 --max-model-calls 90 --max-jev-calls 0
python -m src.research --all --mode cascade --output data/final_results.json --refresh --max-firecrawl-calls 20 --max-model-calls 90 --max-jev-calls 360
python -m src.validate
python -m src.audit --prepare
python -m src.analyze
python -B -m http.server 8765 --directory site
```

The validator exits nonzero while any record is unresolved. The manual audit command stays pending until an independent reviewer enters checked values and official source URLs for all 18 sample IDs in `data/audit.json`, then sets its status to `ready_to_score`. Run `python -m src.audit` after that review. The sample worksheet is a preparation aid, not ground truth.

For a bounded single-app pilot, use `python -m src.research --app-id 81 --output /tmp/stripe-pilot.json --max-firecrawl-calls 1 --max-model-calls 1 --max-jev-calls 10`.

## Deployment and keys

The page is static. [Vercel production](https://composio-research-agent.dubey.page/) is the primary examiner link; [GitHub Pages](https://utkarshdubeygit.github.io/tool-research-agent/) is a public mirror. `vercel.json` serves `site/` with the framework preset set to Other. **No production API keys are needed for this deployed UI**, and no key is shipped to the browser. The Python research pipeline runs locally before publishing the generated files.

If a private server-side research endpoint is added later, put unprefixed `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and `FIRECRAWL_API_KEY` in **Vercel Project Settings → Environment Variables**, scoped to the needed environment, then redeploy. Never use `NEXT_PUBLIC_` or `VITE_` prefixes for these secrets. For local work, keep using the ignored `.env.local`.

## Repository map

- `data/apps.json` — supplied input list.
- `data/source_seeds.json` — frozen candidate source URLs.
- `data/first_pass.json`, `data/final_results.json` — captured baseline and final automated output.
- `data/cache/` — saved source snapshots used for exact quote validation.
- `data/audit.json`, `data/review_queue.json` — pending independent audit and reviewer worksheet.
- `data/run_manifest.json` — non-secret reproducibility metadata.
- `src/` — retrieval, extraction, verification, rules, validation, analysis, and audit CLI.
- `site/` — static review page and generated data.

Run `pytest -q -p no:cacheprovider` for local regression checks.
