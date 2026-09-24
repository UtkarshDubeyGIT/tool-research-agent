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
                "https://api.firecrawl.dev/v2/scrape",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
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
                    error=f"Firecrawl API returned HTTP {resp.status_code}"
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

    def __init__(self, cache_dir: str = "data/cache", max_firecrawl_calls: int = 20):
        self.cache_dir = cache_dir
        self.max_firecrawl_calls = max_firecrawl_calls
        self.firecrawl_calls = 0
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
        # Reuse a successful snapshot from either method before making another request.
        for method in ("firecrawl", "direct"):
            cached = self.get_cached(method, url)
            if cached and cached.status_code == 200 and len(cached.raw_markdown) >= 300 and not dual_fetch:
                return cached

        direct = self.get_cached("direct", url)
        if not direct or direct.status_code != 200 or len(direct.raw_markdown) < 300:
            direct = self.direct.fetch(url)
            if direct.status_code == 200 and direct.raw_markdown:
                self.save_cache(direct)
        if direct.status_code == 200 and len(direct.raw_markdown) >= 300 and not dual_fetch:
            return direct

        if prefer_firecrawl and self.firecrawl.api_key and self.firecrawl_calls < self.max_firecrawl_calls:
            self.firecrawl_calls += 1
            doc = self.firecrawl.fetch(url)
            if doc.status_code == 200 and doc.raw_markdown:
                self.save_cache(doc)
                return doc
        return direct


class SourceDiscovery:
    """Resolves website hints to primary official docs, auth, and API reference URLs."""

    @staticmethod
    def resolve_seed_urls(hint: str, name: str) -> list[str]:
        hint = hint.strip()
        if not hint.lower().startswith(("http://", "https://")):
            hint_url = f"https://{hint}"
        else:
            hint_url = hint

        urls = [hint_url]
        return urls
