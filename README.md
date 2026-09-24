# Tool Research Agent | Composio AI Product Ops Take-Home

> An automated, repeatable research agent that investigates developer platforms, produces evidence-backed integration assessments, verifies its own findings via multi-stage decision checks, and publishes an interactive case study web application.

[![Python Tests](https://img.shields.io/badge/pytest-5%20passed-brightgreen.svg)]()
[![Dataset Coverage](https://img.shields.io/badge/coverage-90%2F90%20apps%20(100%25)-blue.svg)]()
[![Schema Validation](https://img.shields.io/badge/validation-0%20errors-success.svg)]()
[![License](https://img.shields.io/badge/license-MIT-gray.svg)]()

---

## 🌐 Live URLs & Deployment

- **Live Case Study Web App:** [https://utkarshdubeygit.github.io/tool-research-agent/](https://utkarshdubeygit.github.io/tool-research-agent/)
- **Public GitHub Repository:** [https://github.com/UtkarshDubeyGIT/tool-research-agent](https://github.com/UtkarshDubeyGIT/tool-research-agent)
- **Vercel Deployment:** Pre-configured via `vercel.json` (`outputDirectory: "site"`). Ready for 1-click deployment on Vercel.

---

## ⚠️ Scope Discrepancy Disclosure

The assignment prompt specifies: *"You will evaluate 100 apps across 10 categories"*. However, the itemized table provided in the take-home PDF document itemizes exactly **90 applications across 9 categories**, terminating at `#90 PitchBook` in Category 9 (*Finance and Fintech*). Category 10 (#91–#100) is absent from the prompt document.

In adherence to strict data integrity standards:
1. **Zero Data Fabrication:** No placeholder or hallucinated entries were injected. The pipeline evaluates all 90 provided entries faithfully.
2. **Coverage Disclosure:** Coverage is transparently reported as **90/90 (100% of provided dataset)** across the README and deployed case study.
3. **Plug-and-Play Extensibility:** If the remaining 10 apps are provided, appending them to `data/apps.json` and running `python -m src.research --all --resume` will seamlessly incorporate them without changing pipeline logic.

---

## 🏗️ System Architecture

The research pipeline rejects single-prompt end-to-end LLM generation in favor of a **multi-stage verification cascade**:

```
                                  [ data/apps.json ] (IDs 1-90)
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 1: Source Discovery     │
                         │   & Firecrawl / HTTP Fetch      │
                         └────────────────┬────────────────┘
                                          │  Markdown Snapshots (Cached SHA-256)
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 2: Generative Extraction│
                         │   (OpenAI gpt-6-luna)           │
                         └────────────────┬────────────────┘
                                          │  Candidate Claims & Verbatim Quotes
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 3: Decision Cascade     │
                         │   (TypeSafe Jev typesafe/jev-1.13)│
                         └────────────────┬────────────────┘
                                          │  Atomic Noul (Binary) & Choice Checks
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 4: Deterministic Rules  │
                         │   (Code-Owned Rule Composition) │
                         └────────────────┬────────────────┘
                                          │  api_breadth & buildability Verdict
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 5: Strict Validation    │
                         │   (src/validate.py)             │
                         └────────────────┬────────────────┘
                                          │  90 Valid App Records
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 6: Stratified Audit     │
                         │   (src/audit.py - 18 apps / 20%)│
                         └────────────────┬────────────────┘
                                          │  Before / After Measured Accuracy
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 7: Static Site & Web UI │
                         │   (site/ - HTML, CSS, Zero-CORS)│
                         └─────────────────────────────────┘
```

1. **Retrieval (`src/retrieval.py`):** Primary extraction via Firecrawl with direct HTTP fallback and SHA-256 local caching in `data/cache/`.
2. **Synthesis (`src/research.py`):** OpenAI generative model extracts candidate integration claims paired with verbatim quotes and source URLs.
3. **Verification (`src/jev_client.py`):** TypeSafe Jev (`typesafe/jev-1.13` on OpenRouter) evaluates atomic Noul and Choice decision queries against raw documentation excerpts to eliminate hallucinations.
4. **Code-Owned Rules (`src/rules.py`):** Python code deterministically computes `api_breadth` (from documented API surfaces) and `buildability` (`buildable_now`, `conditional`, `outreach_needed`) according to explicit credential gating logic.
5. **Validation (`src/validate.py`):** Deterministic verification of Pydantic models, sequential IDs (1–90), quote matching against saved markdown, and logical contradiction checks.
6. **Stratified Audit (`src/audit.py`):** Independent human audit of 18 sampled apps (2 per category) benchmarking baseline unassisted accuracy against verified ground truth.
7. **Analytics & Frontend (`src/analyze.py` & `site/`):** Generates summary metrics, CSV/JSON datasets, zero-CORS data bundle, and deploys the responsive single-page case study.

---

## 📊 Key Findings & Results

| Metric | Result | Operational Significance |
| :--- | :--- | :--- |
| **Total Researched** | **90 / 90 (100%)** | All 90 apps supplied in PDF covered across 9 categories |
| **Buildable Now** | **72 apps (80.0%)** | Immediate self-serve signup & free or trial API keys |
| **Conditional** | **14 apps (15.6%)** | Paid tier required (SEMrush, Ahrefs) or admin approval needed |
| **Outreach Needed** | **4 apps (4.4%)** | Formal partner agreements or enterprise sales gates (Salesforce, PitchBook, DealCloud, Gladly) |
| **Dominant Auth** | **OAuth 2.0 (75.6%)** | Followed closely by API keys / tokens (67.8%) |
| **Audit Field Accuracy**| **77.8% (56/72)** | Improved from 75.0% (54/72) baseline after Jev & human audit |
| **Audit App Accuracy** | **44.4% (8/18)** | Improved from 38.9% (7/18) baseline after resolving enterprise edge cases |

---

## 🚀 Quick Start & CLI Execution

### 1. Prerequisites
- Python 3.10+
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/UtkarshDubeyGIT/tool-research-agent.git
cd tool-research-agent

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Setup
Copy `.env.example` to `.env` and provide your API keys:
```bash
cp .env.example .env
```
```env
OPENAI_API_KEY="sk-..."
OPENROUTER_API_KEY="sk-or-..."
FIRECRAWL_API_KEY="fc-..."
```
*(Note: Pre-cached scrapes in `data/cache/` allow running the pipeline in deterministic offline mode without live API billing if desired).*

### 4. Runnable Commands

```bash
# 1. Investigate a single app by ID (e.g. #1 Salesforce)
python -m src.research --app-id 1

# 2. Run the research pipeline across all 90 apps with automatic resumption
python -m src.research --all --resume

# 3. Deterministically validate schemas, URLs, quotes, and rule consistency
python -m src.validate

# 4. Run reproducible human audit report and benchmark accuracy
python -m src.audit --report

# 5. Compile static analytics and export web assets
python -m src.analyze

# 6. Run automated pytest test suite
pytest
```

---

## 🧪 Testing & Validation

The test suite validates schema conformance, deterministic rule execution, and stratified audit math:
```bash
$ pytest -v
============================= test session starts ==============================
tests/test_audit.py::test_audit_stratification PASSED                     [ 20%]
tests/test_rules.py::test_buildability_derivation PASSED                  [ 40%]
tests/test_rules.py::test_api_breadth_derivation PASSED                   [ 60%]
tests/test_schema.py::test_valid_app_record PASSED                        [ 80%]
tests/test_schema.py::test_invalid_app_record_fails PASSED                [100%]
============================== 5 passed in 0.11s ===============================
```

---

## 📁 Repository Directory Structure

```
.
├── README.md                      # Project documentation, architecture & runbook
├── requirements.txt               # Pydantic, Requests, Pytest dependencies
├── vercel.json                    # Zero-config static deployment for site/
├── .env.example                   # Template environment variables
├── conftest.py                    # Pytest configuration
├── data/
│   ├── apps.json                  # Canonical input list (IDs 1-90 from PDF)
│   ├── final_results.json         # 90 fully validated structured app records
│   ├── first_pass.json            # Unassisted baseline results before audit
│   ├── audit.json                 # 18-app stratified human audit & ground truth
│   └── cache/                     # Cached Firecrawl and Direct HTTP scrape snapshots
├── devlog/                        # Milestone implementation plans, tasks & walkthroughs
│   ├── phase1-*.md                # Scaffolding & Data Contract
│   ├── phase2-*.md                # Retrieval Engine & Pilot Dual-Fetch
│   ├── phase3-*.md                # Research Agent, Jev Decisions & Composition
│   ├── phase4-*.md                # Validation, Audit & Accuracy Tracking
│   ├── phase5-*.md                # Analytics, Case Study Frontend & Test Suite
│   └── phase6-*.md                # Final Integration, Deployment & Walkthrough
├── site/                          # Deployable Single-Page Case Study Web App
│   ├── index.html                 # Semantic dark-mode case study interface
│   ├── style.css                  # Composio-inspired styling
│   ├── app.js                     # Interactive search, filters & evidence drawer
│   └── data/
│       ├── bundle.js              # Zero-CORS offline data bundle
│       ├── summary.json           # Aggregated metrics & category breakdown
│       ├── records.json           # Full 90-app records for client fetch
│       └── records.csv            # Tabular export for spreadsheet analysis
├── src/
│   ├── models.py                  # Strict Pydantic models & validation constraints
│   ├── retrieval.py               # Firecrawl & Direct fetchers with SHA-256 caching
│   ├── jev_client.py              # TypeSafe Jev Decision client (Noul & Choice)
│   ├── rules.py                   # Code-owned buildability & breadth composition
│   ├── research.py                # Resumable per-app research CLI pipeline
│   ├── validate.py                # Deterministic quote and schema validator
│   ├── audit.py                   # Stratified sampling and accuracy calculator
│   └── analyze.py                 # Cross-category analytics & bundle exporter
└── tests/                         # Pytest unit tests
    ├── test_schema.py
    ├── test_rules.py
    └── test_audit.py
```

---

## 🎯 Case Study Web Application Features

The single-page case study application (`site/index.html`) includes:
- **Transparent Scope Banner:** Discloses PDF termination at #90 in Category 9.
- **Executive Metric Cards:** Total Researched (90), Buildable Now (72), Conditional (14), Outreach Needed (4).
- **Interactive Matrix Table:** Full text search across names, categories, and blockers; instant filtering by verdict and category.
- **Slide-Over Evidence Drawer:** Click any application row to inspect its operational summary, credential access flags, and exact verbatim quoted passages with source URLs and Jev verification badges.
- **Human-in-the-Loop Audit Section:** Side-by-side comparison of baseline vs ground truth accuracy and documented case studies of baseline misses (PitchBook, DealCloud, Salesforce, Gladly).
- **Zero-CORS Resilience:** Can be served over HTTP or opened directly from disk via `file://site/index.html` using the embedded `bundle.js`.

---

## ⚖️ Disclaimers & Attribution

This project is an independent submission developed by Utkarsh Dubey for the Composio AI Product Ops take-home evaluation. It is not an official Composio product. All third-party trademarks and brand names are the property of their respective owners.
