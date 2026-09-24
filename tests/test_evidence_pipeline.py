from src.models import AppRecord, EvidenceItem, RawDocument
from src.retrieval import DocumentFetcher, SourceDiscovery
from src.validate import EvidenceValidator


def test_validates_quote_against_any_saved_snapshot(tmp_path):
    fetcher = DocumentFetcher(cache_dir=str(tmp_path), max_firecrawl_calls=0)
    url = "https://example.com/api"
    for text, timestamp in [("Old text", "2026-01-01T00:00:00Z"), ("The API supports OAuth 2.0.", "2026-02-01T00:00:00Z")]:
        fetcher.save_cache(RawDocument(
            url=url, final_url=url, title="Docs", timestamp=timestamp,
            source_method="direct_http" if text == "Old text" else "firecrawl",
            content_hash="hash", raw_markdown=text,
        ))
    record = AppRecord(
        id=1, name="Example", category="Test", website_hint="example.com",
        research_status="complete",
        evidence=[EvidenceItem(field="auth_methods", claim="OAuth is supported",
                               verification="supported", url=url,
                               quote="The API supports OAuth 2.0.",
                               retrieved_at="2026-02-01T00:00:00Z")],
    )
    assert EvidenceValidator(cache_dir=str(tmp_path))._check_evidence(record) == []


def test_reuses_successful_direct_cache_before_paid_fetch(tmp_path):
    fetcher = DocumentFetcher(cache_dir=str(tmp_path), max_firecrawl_calls=1)
    url = "https://example.com/docs"
    cached = RawDocument(url=url, final_url=url, title="Docs", timestamp="2026-01-01T00:00:00Z",
                         source_method="direct_http", content_hash="hash", raw_markdown="Source documentation. " * 30)
    fetcher.save_cache(cached)
    fetcher.firecrawl.api_key = "test-key"
    fetcher.direct.fetch = lambda _: (_ for _ in ()).throw(AssertionError("unexpected direct fetch"))
    fetcher.firecrawl.fetch = lambda _: (_ for _ in ()).throw(AssertionError("unexpected paid fetch"))
    assert fetcher.fetch(url).raw_markdown == cached.raw_markdown
    assert fetcher.firecrawl_calls == 0


def test_source_hint_keeps_case_sensitive_path():
    assert SourceDiscovery.resolve_seed_urls("docs.example.com/API/V2", "Example") == ["https://docs.example.com/API/V2"]
