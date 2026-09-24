# Phase 2 Implementation Plan: Retrieval Engine & Pilot Dual-Fetch Comparison

## Scope & Objective
Implement the retrieval subsystem for the Composio research agent:
1. Firecrawl primary page extractor integration (`FirecrawlFetcher`) via REST API.
2. Independent fallback and audit retrieval engine (`DirectFetcher`) using standard HTTP sessions with browser headers, timeouts, and BeautifulSoup HTML stripping.
3. Content hashing and caching subsystem in `data/cache/firecrawl/` and `data/cache/direct/`.
4. Run a representative pilot experiment across 5 diverse applications (Salesforce, Twilio, Shopify, GitHub, Stripe) to compare direct extraction against CDN bot challenges and evaluate quote retention.

## Verification
- Test fetch execution against live documentation endpoints.
- Confirm SHA-256 content hashes and clean markdown storage.
- Document extraction failure modes (e.g. Cloudflare / Akamai bot protection on specific URLs) and how the dual-fetch / fallback architecture handles them.
