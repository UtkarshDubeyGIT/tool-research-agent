import os
import re
import requests
from typing import Dict, Any, Optional, List
from src.models import (
    JevChoiceAnswer,
    JevNoulAnswer,
    JevScoreAnswer,
    CredentialAccess
)


OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_JEV_MODEL = "typesafe/jev-1.13"


class JevClient:
    """Client for TypeSafe Jev decision model on OpenRouter."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_JEV_MODEL):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model

    def make_decisions(self, state: Dict[str, Any], questions: Dict[str, Any]) -> Dict[str, Any]:
        """Send application state and typed questions to Jev Decisions API."""
        if not self.api_key:
            return {}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "state": state,
            "questions": questions
        }

        try:
            resp = requests.post(OPENROUTER_DECISIONS_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("answers", {})
            else:
                return {}
        except Exception:
            return {}

    def verify_claim(self, claim: str, excerpt: str) -> Dict[str, Any]:
        """Verify whether an extracted claim is supported by a documentation excerpt."""
        state = {
            "claim": claim,
            "excerpt": excerpt
        }
        questions = {
            "claim_support": {
                "type": "choice",
                "instructions": "Compare the claim against the excerpt. Which one describes it?",
                "criteria": {
                    "supported": "The claim is directly asserted or confirmed by facts in the excerpt.",
                    "contradicted": "The excerpt contradicts the claim.",
                    "insufficient_evidence": "The excerpt does not contain enough facts to prove or disprove the claim."
                }
            }
        }
        if not self.api_key:
            return {
                "choice": "insufficient_evidence",
                "confidence": 0.0,
                "probabilities": {"insufficient_evidence": 1.0},
                "method": "no_api_key"
            }

        answers = self.make_decisions(state, questions)
        support = answers.get("claim_support", {})
        choice = support.get("choice", "insufficient_evidence")
        confidence = support.get("confidence", 0.9)
        return {
            "choice": choice,
            "confidence": confidence,
            "probabilities": support.get("probabilities", {choice: confidence})
        }

    def classify_access_and_auth(self, excerpt: str) -> Dict[str, Any]:
        """Ask atomic Noul and Choice questions over documentation excerpts."""
        state = {"excerpt": excerpt}
        questions = {
            "has_oauth2": {
                "type": "noul",
                "instructions": "Does this text state or describe support for OAuth 2.0?",
                "criteria": {
                    "true": "OAuth 2.0, authorization code, client credentials, or PKCE is mentioned as an auth method.",
                    "false": "OAuth 2.0 is not mentioned or stated as unsupported."
                }
            },
            "has_api_key": {
                "type": "noul",
                "instructions": "Does this text describe API keys or personal access tokens?",
                "criteria": {
                    "true": "API key, secret key, Bearer token, or personal access token is supported.",
                    "false": "No API key mechanism mentioned."
                }
            },
            "has_rest": {
                "type": "noul",
                "instructions": "Does this text document a REST API or HTTP endpoints?",
                "criteria": {
                    "true": "REST endpoints, JSON HTTP requests, or HTTP methods (GET, POST) are documented.",
                    "false": "No REST API mentioned."
                }
            },
            "has_graphql": {
                "type": "noul",
                "instructions": "Does this text document GraphQL support?",
                "criteria": {
                    "true": "GraphQL queries, mutations, or /graphql endpoint is documented.",
                    "false": "No GraphQL support mentioned."
                }
            },
            "self_serve_signup": {
                "type": "noul",
                "instructions": "Can a developer sign up or create an account self-serve without contacting sales?",
                "criteria": {
                    "true": "Self-serve signup, free sign-up form, or instant account creation is described.",
                    "false": "Requires sales contact, enterprise agreement, or closed invitation."
                }
            },
            "paid_plan_required": {
                "type": "noul",
                "instructions": "Is a paid subscription strictly required to use the API?",
                "criteria": {
                    "true": "API access is gated exclusively behind paid tiers, enterprise plans, or active billing.",
                    "false": "Free tier, developer sandbox, or trial credentials exist."
                }
            },
            "admin_approval_required": {
                "type": "noul",
                "instructions": "Does creating or authorizing API credentials require workspace or organization admin approval?",
                "criteria": {
                    "true": "Workspace admin, tenant administrator, or internal admin permission is required.",
                    "false": "Any standard account owner can generate credentials immediately."
                }
            },
            "partner_approval_required": {
                "type": "noul",
                "instructions": "Is formal partnership approval, application review, or sales contact required from the provider?",
                "criteria": {
                    "true": "Requires partner program application, manual compliance review, or vendor approval before API access.",
                    "false": "Self-serve or standard developer registration."
                }
            }
        }
        return self.make_decisions(state, questions)

    def _heuristic_fallback(self, state: Dict[str, Any], questions: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic offline fallback for Jev decision queries when API key is unavailable."""
        text = str(state).lower()
        answers: Dict[str, Any] = {}

        for q_name, q_spec in questions.items():
            q_type = q_spec.get("type")
            if q_type == "noul":
                prob = 0.5
                if q_name == "has_oauth2":
                    prob = 0.95 if any(k in text for k in ["oauth", "oauth2", "oauth 2.0", "client_id", "authorization code"]) else 0.05
                elif q_name == "has_api_key":
                    prob = 0.95 if any(k in text for k in ["api key", "apikey", "bearer token", "access token", "x-api-key"]) else 0.05
                elif q_name == "has_rest":
                    prob = 0.95 if any(k in text for k in ["rest api", "http request", "json api", "endpoints", "get /", "post /"]) else 0.2
                elif q_name == "has_graphql":
                    prob = 0.95 if any(k in text for k in ["graphql", "mutation", "query {", "/graphql"]) else 0.05
                elif q_name == "self_serve_signup":
                    prob = 0.90 if any(k in text for k in ["sign up free", "create account", "get started", "free trial", "developer portal"]) else 0.3
                elif q_name == "paid_plan_required":
                    prob = 0.85 if any(k in text for k in ["paid plan required", "enterprise only", "available on pro and enterprise", "contact sales for api"]) else 0.15
                elif q_name == "admin_approval_required":
                    prob = 0.85 if any(k in text for k in ["admin approval", "administrator must enable", "workspace owner", "connected app"]) else 0.15
                elif q_name == "partner_approval_required":
                    prob = 0.85 if any(k in text for k in ["partner approval", "partner program", "apply for access", "contact sales", "request access"]) else 0.10

                answers[q_name] = {"type": "noul", "noul": prob}

            elif q_type == "choice":
                if q_name == "claim_support":
                    claim = state.get("claim", "").lower().replace("_", " ")
                    excerpt = state.get("excerpt", "").lower().replace("_", " ")
                    stop_words = {"this", "that", "with", "from", "supports", "using", "access", "developer", "which", "where", "about", "apps"}
                    claim_words = [w for w in re.findall(r"\w+", claim) if len(w) > 2 and w not in stop_words]
                    matches = sum(1 for w in claim_words if w in excerpt)
                    ratio = matches / max(1, len(claim_words))
                    # If key domain concepts overlap or ratio is above 20%
                    has_domain_concept = any(k in claim and k in excerpt for k in ["oauth", "api key", "token", "rest", "graphql", "bearer", "mcp", "basic", "secret", "sandbox", "self-serve", "partner"])
                    choice = "supported" if (ratio >= 0.2 or has_domain_concept) else "insufficient_evidence"
                    answers[q_name] = {
                        "type": "choice",
                        "choice": choice,
                        "confidence": 0.90 if choice == "supported" else 0.60,
                        "probabilities": {choice: 0.90, "insufficient_evidence": 0.10}
                    }
                else:
                    criteria = q_spec.get("criteria", {})
                    first_choice = list(criteria.keys())[0] if criteria else "unknown"
                    answers[q_name] = {
                        "type": "choice",
                        "choice": first_choice,
                        "confidence": 0.7,
                        "probabilities": {first_choice: 1.0}
                    }

        return answers
