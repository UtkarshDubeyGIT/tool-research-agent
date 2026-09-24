"""Atomic source-claim verification through OpenRouter's Jev Decisions API."""

import os
from typing import Any, Dict, Optional

import requests


OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_JEV_MODEL = "typesafe/jev-1.13"
VALID_CHOICES = {"supported", "contradicted", "insufficient_evidence"}


class JevClient:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_JEV_MODEL):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model

    def verify_claim(self, claim: str, excerpt: str) -> Dict[str, Any]:
        """Fail closed if the key, provider, or response is unavailable."""
        if not self.api_key:
            return {"choice": "insufficient_evidence", "method": "no_api_key"}

        payload = {
            "model": self.model,
            "state": {"claim": claim, "excerpt": excerpt},
            "questions": {
                "claim_support": {
                    "type": "choice",
                    "instructions": "Compare the claim with the source excerpt. Select direct support, contradiction, or insufficient evidence.",
                    "criteria": {
                        "supported": "The source directly states facts that establish this claim.",
                        "contradicted": "The source directly contradicts the claim.",
                        "insufficient_evidence": "The source does not establish or contradict the claim.",
                    },
                }
            },
        }
        try:
            response = requests.post(
                OPENROUTER_DECISIONS_URL,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            if response.status_code != 200:
                return {"choice": "insufficient_evidence", "method": "provider_error"}
            answer = response.json().get("answers", {}).get("claim_support", {})
            choice = answer.get("choice", "insufficient_evidence")
            if choice not in VALID_CHOICES:
                choice = "insufficient_evidence"
            return {
                "choice": choice,
                "confidence": answer.get("confidence"),
                "probabilities": answer.get("probabilities", {}),
            }
        except (requests.RequestException, ValueError, TypeError):
            return {"choice": "insufficient_evidence", "method": "provider_error"}
