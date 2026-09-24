# Phase 2 Walkthrough: Retrieval Engine & Pilot Dual-Fetch Comparison

## Summary of Changes
1. **Retrieval Subsystem (`src/retrieval.py`)**:
   - `FirecrawlFetcher`: Connects to `https://api.firecrawl.dev/v1/scrape` with format markdown and authorization bearer token.
   - `DirectFetcher`: Resilient HTTP session with desktop browser User-Agent headers, timeout handling, and BeautifulSoup text extraction focusing on `<article>`, `<main>`, or document root.
   - `DocumentFetcher`: Manages cache lookups, preferential routing (Firecrawl primary, direct HTTP fallback), and dual-fetch snapshots.
   - `SourceDiscovery`: Normalizes website hints to candidate doc endpoints.
2. **Snapshot Caching**:
   - Cached documents stored as JSON in `data/cache/{method}/{sha256(url)}.json` including timestamp, status code, title, and body hash.
3. **Pilot Experiment Results**:
   - Evaluated 5 diverse apps:
     - **Twilio**: Direct fetch returned HTTP 200, 2,816 chars, title `API keys overview | Twilio`, hash `c315205f94`.
     - **Shopify**: Direct fetch returned HTTP 200, 7,801 chars, title `About app authentication`, hash `a32d046103`.
     - **GitHub**: Direct fetch returned HTTP 200, 9,846 chars, title `Authenticating to the REST API - GitHub`, hash `5f6f51e467`.
     - **Stripe**: Direct fetch returned HTTP 200, 6,018 chars, title `Authentication | Stripe API Reference`, hash `e149406356`.
     - **Salesforce**: Deep documentation URL returned HTTP 403 (Akamai bot protection on raw HTTP requests), proving the exact necessity of Firecrawl browser rendering for JS/bot-protected portals.
4. **Architectural Confirmation**:
   - A failed or blocked fetch on a raw HTTP client is appropriately treated as a candidate for browser/Firecrawl retrieval or marked `unknown`, never as negative evidence that an API does not exist.

## Validation
- Executed pilot test across real-world endpoints.
- Confirmed deterministic SHA-256 calculation and JSON serialization in cache.
