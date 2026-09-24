from src.jev_client import JevClient


class FakeResponse:
    status_code = 200

    def json(self):
        return {"answers": {"claim_support": {"choice": "unrecognized"}}}


def test_jev_rejects_unrecognized_provider_choice(monkeypatch):
    monkeypatch.setattr("src.jev_client.requests.post", lambda *args, **kwargs: FakeResponse())
    result = JevClient(api_key="temporary-test-key").verify_claim("claim", "source")
    assert result["choice"] == "insufficient_evidence"


def test_jev_without_key_never_calls_provider(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("src.jev_client.requests.post", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    result = JevClient(api_key="").verify_claim("claim", "source")
    assert result["choice"] == "insufficient_evidence"
