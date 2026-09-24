from typing import List, Tuple
from src.models import (
    CredentialAccess,
    BuildabilityVerdict,
    ApiBreadth
)


def evaluate_api_breadth(
    endpoint_count: int,
    text_indicators: str,
    api_types: List[str]
) -> ApiBreadth:
    """
    Code-owned rubric for API breadth:
    - broad: Comprehensive platform with >50 endpoints across diverse business entities.
    - focused: Domain-specific API with 10-50 endpoints.
    - limited: Minimal surface (<10 endpoints) or webhook/embed-only.
    - unknown: No verifiable endpoint details.
    """
    text_lower = text_indicators.lower()
    
    if not api_types:
        return "unknown"

    if endpoint_count > 50 or any(k in text_lower for k in [
        "comprehensive api", "full platform api", "all objects", "rest and graphql", 
        "hundreds of endpoints", "core api", "v1/v2/v3", "full crud"
    ]):
        return "broad"
    elif 10 <= endpoint_count <= 50 or any(k in text_lower for k in [
        "focused api", "messaging api", "sms api", "search api", "specialized endpoints"
    ]):
        return "focused"
    elif 0 < endpoint_count < 10 or any(k in text_lower for k in [
        "limited api", "single endpoint", "webhook only", "embed only", "cli utility"
    ]):
        return "limited"
    
    # Default to focused if public API exists with standard structure
    return "focused"


def evaluate_buildability(
    credential_access: CredentialAccess,
    auth_methods: List[str],
    api_types: List[str],
    existing_blocker: str = ""
) -> Tuple[BuildabilityVerdict, str]:
    """
    Code-owned rule engine for buildability verdict and main blocker.
    Rules:
    1. outreach_needed: Partner approval or sales contact required to get developer credentials.
    2. conditional: Paid plan strictly required without free tier/trial, or manual admin approval needed.
    3. buildable_now: Free/trial credentials available self-serve with standard OAuth2/API key and public API.
    4. unknown: Documentation missing or authentication method unresolved.
    """
    # 1. Partner gating has highest precedence
    if credential_access.partner_approval_required == "yes":
        blocker = existing_blocker if existing_blocker and existing_blocker != "none" else "Requires formal partner program application, enterprise sales contact, or vendor agreement."
        return "outreach_needed", blocker

    # 2. Strict paid plan without trial
    if credential_access.paid_plan_required == "yes" and credential_access.free_or_trial_credentials == "no":
        blocker = existing_blocker if existing_blocker and existing_blocker != "none" else "Requires active paid subscription tier; no free developer sandbox available."
        return "conditional", blocker

    # 3. Workspace / Enterprise Admin approval required
    if credential_access.admin_approval_required == "yes" and credential_access.self_serve_signup == "no":
        blocker = existing_blocker if existing_blocker and existing_blocker != "none" else "Requires organization or tenant administrator setup and approval."
        return "conditional", blocker

    # 4. Buildable now
    has_auth = len(auth_methods) > 0 and auth_methods != ["unknown"]
    has_api = len(api_types) > 0 and api_types != ["unknown"]
    is_self_serve = credential_access.self_serve_signup in ("yes", "unknown")
    has_free_or_trial = credential_access.free_or_trial_credentials in ("yes", "unknown")

    if is_self_serve and has_free_or_trial and has_auth and has_api:
        # If there's an admin approval notice but self-serve sandbox is available (like Salesforce Dev Org)
        if credential_access.admin_approval_required == "yes":
            return "conditional", existing_blocker or "Requires admin authorization in production (sandbox is self-serve)."
        return "buildable_now", "none"

    # 5. Missing critical info
    if not has_auth or not has_api:
        return "unknown", "Official API and authentication documentation is not publicly accessible."

    return "conditional", existing_blocker or "Requires specific environment configuration or plan credentials."
