import pytest
from src.models import CredentialAccess
from src.rules import evaluate_buildability, evaluate_api_breadth


def test_buildability_rules():
    # 1. Partner gated
    cred = CredentialAccess(partner_approval_required="yes")
    verdict, blocker = evaluate_buildability(cred, ["oauth2"], ["rest"])
    assert verdict == "outreach_needed"
    assert "partner" in blocker.lower() or "sales" in blocker.lower()

    # 2. Strict paid plan
    cred = CredentialAccess(paid_plan_required="yes", free_or_trial_credentials="no")
    verdict, blocker = evaluate_buildability(cred, ["api_key"], ["rest"])
    assert verdict == "conditional"
    assert "paid" in blocker.lower()

    # 3. Buildable now
    cred = CredentialAccess(self_serve_signup="yes", free_or_trial_credentials="yes", partner_approval_required="no")
    verdict, blocker = evaluate_buildability(cred, ["api_key"], ["rest"])
    assert verdict == "buildable_now"
    assert blocker == "none"

    # 4. Unknown when no auth
    cred = CredentialAccess(self_serve_signup="yes", free_or_trial_credentials="yes")
    verdict, blocker = evaluate_buildability(cred, [], ["rest"])
    assert verdict == "unknown"


def test_api_breadth_rules():
    assert evaluate_api_breadth(100, "Comprehensive platform API with hundreds of endpoints", ["rest"]) == "broad"
    assert evaluate_api_breadth(25, "SMS messaging API", ["rest"]) == "focused"
    assert evaluate_api_breadth(3, "Single webhook endpoint", ["rest"]) == "limited"
    assert evaluate_api_breadth(0, "No docs", []) == "unknown"
