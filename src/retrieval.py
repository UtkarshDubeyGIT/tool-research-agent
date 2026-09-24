import os
import re
import json
import time
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
import requests
from bs4 import BeautifulSoup
from src.models import RawDocument


DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 (ComposioResearchAgent/1.0)"


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    """Normalize whitespace and clean text for deterministic quote comparison."""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class DirectFetcher:
    """Independent fallback and audit retrieval engine using HTTP and BeautifulSoup."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        })

    def fetch(self, url: str) -> RawDocument:
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            status_code = resp.status_code
            final_url = resp.url
            
            if status_code >= 400:
                return RawDocument(
                    url=url,
                    final_url=final_url,
                    title="",
                    timestamp=timestamp,
                    source_method="direct_http",
                    content_hash="",
                    raw_markdown="",
                    status_code=status_code,
                    error=f"HTTP Error {status_code}"
                )

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract title
            title = ""
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            # Clean clutter
            for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
                tag.extract()

            # Focus on article / main / body
            content_root = soup.find("article") or soup.find("main") or soup.find("div", {"id": "content"}) or soup.body or soup
            raw_text = content_root.get_text(separator="\n", strip=True) if content_root else ""
            cleaned = normalize_text(raw_text)

            return RawDocument(
                url=url,
                final_url=final_url,
                title=title,
                timestamp=timestamp,
                source_method="direct_http",
                content_hash=compute_hash(cleaned),
                raw_markdown=cleaned,
                status_code=status_code,
                error=None
            )
        except Exception as e:
            return RawDocument(
                url=url,
                final_url=url,
                title="",
                timestamp=timestamp,
                source_method="direct_http",
                content_hash="",
                raw_markdown="",
                status_code=0,
                error=str(e)
            )


class FirecrawlFetcher:
    """Primary document extractor using Firecrawl API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")

    def fetch(self, url: str) -> RawDocument:
        timestamp = datetime.now(timezone.utc).isoformat()
        if not self.api_key:
            return RawDocument(
                url=url,
                final_url=url,
                title="",
                timestamp=timestamp,
                source_method="firecrawl",
                content_hash="",
                raw_markdown="",
                status_code=0,
                error="FIRECRAWL_API_KEY is not configured"
            )

        try:
            resp = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={"url": url, "formats": ["markdown"]},
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                markdown = data.get("markdown", "")
                metadata = data.get("metadata", {})
                cleaned = normalize_text(markdown)
                return RawDocument(
                    url=url,
                    final_url=metadata.get("sourceURL", url),
                    title=metadata.get("title", ""),
                    timestamp=timestamp,
                    source_method="firecrawl",
                    content_hash=compute_hash(cleaned),
                    raw_markdown=cleaned,
                    status_code=200,
                    error=None
                )
            else:
                return RawDocument(
                    url=url,
                    final_url=url,
                    title="",
                    timestamp=timestamp,
                    source_method="firecrawl",
                    content_hash="",
                    raw_markdown="",
                    status_code=resp.status_code,
                    error=f"Firecrawl API error: {resp.text}"
                )
        except Exception as e:
            return RawDocument(
                url=url,
                final_url=url,
                title="",
                timestamp=timestamp,
                source_method="firecrawl",
                content_hash="",
                raw_markdown="",
                status_code=0,
                error=str(e)
            )


class DocumentFetcher:
    """Unified fetcher managing primary Firecrawl extraction, direct fallback, and caching."""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        self.firecrawl = FirecrawlFetcher()
        self.direct = DirectFetcher()
        os.makedirs(f"{self.cache_dir}/firecrawl", exist_ok=True)
        os.makedirs(f"{self.cache_dir}/direct", exist_ok=True)

    def _cache_path(self, method: str, url: str) -> str:
        url_hash = compute_hash(url)
        return f"{self.cache_dir}/{method}/{url_hash}.json"

    def get_cached(self, method: str, url: str) -> Optional[RawDocument]:
        path = self._cache_path(method, url)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return RawDocument(**json.load(f))
            except Exception:
                return None
        return None

    def save_cache(self, doc: RawDocument) -> None:
        sub = "firecrawl" if doc.source_method == "firecrawl" else "direct"
        path = self._cache_path(sub, doc.url)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc.model_dump(), f, indent=2)

    def fetch(self, url: str, prefer_firecrawl: bool = True, dual_fetch: bool = False) -> RawDocument:
        # Check cache first
        primary_method = "firecrawl" if prefer_firecrawl and self.firecrawl.api_key else "direct"
        cached_primary = self.get_cached(primary_method, url)
        if cached_primary and not dual_fetch:
            return cached_primary

        doc = None
        if prefer_firecrawl and self.firecrawl.api_key:
            doc = self.firecrawl.fetch(url)
            if doc.status_code == 200 and not doc.error:
                self.save_cache(doc)
            else:
                # Fallback to direct HTTP on failure
                doc = self.direct.fetch(url)
                self.save_cache(doc)
        else:
            doc = self.direct.fetch(url)
            self.save_cache(doc)

        if dual_fetch:
            # If dual fetch requested, run direct fetch as well if primary was firecrawl
            if doc.source_method == "firecrawl":
                direct_doc = self.direct.fetch(url)
                self.save_cache(direct_doc)
            elif self.firecrawl.api_key:
                fc_doc = self.firecrawl.fetch(url)
                self.save_cache(fc_doc)

        return doc


class SourceDiscovery:
    """Resolves website hints to primary official docs, auth, and API reference URLs."""

    @staticmethod
    def resolve_seed_urls(hint: str, name: str) -> list[str]:
        hint = hint.strip().lower()
        if not hint.startswith("http"):
            hint_url = f"https://{hint}"
        else:
            hint_url = hint

        urls = [hint_url]
        return urls
