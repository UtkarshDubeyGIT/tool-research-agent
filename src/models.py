from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


YesNoUnknown = Literal["yes", "no", "unknown"]
VerificationStatus = Literal["supported", "contradicted", "insufficient_evidence"]
ApiBreadth = Literal["broad", "focused", "limited", "unknown"]
ExistingMcp = Literal["official", "third_party", "none_found", "unknown"]
BuildabilityVerdict = Literal["buildable_now", "conditional", "outreach_needed", "unknown"]
ConfidenceLevel = Literal["high", "medium", "low"]
ResearchStatus = Literal["complete", "needs_review", "blocked"]


class CredentialAccess(BaseModel):
    self_serve_signup: YesNoUnknown = "unknown"
    free_or_trial_credentials: YesNoUnknown = "unknown"
    paid_plan_required: YesNoUnknown = "unknown"
    admin_approval_required: YesNoUnknown = "unknown"
    partner_approval_required: YesNoUnknown = "unknown"


class EvidenceItem(BaseModel):
    field: str = Field(..., description="Target field name, e.g. auth_methods, credential_access, api_types")
    claim: str = Field(..., description="Exact claim being verified")
    verification: VerificationStatus = Field(default="insufficient_evidence", description="Evidence status; support must be explicitly established")
    url: str = Field(..., description="Exact documentation URL where quote was found")
    quote: str = Field(..., description="Verbatim short excerpt from the fetched document")
    retrieved_at: str = Field(..., description="ISO-8601 timestamp of retrieval")


class AppRecord(BaseModel):
    id: int = Field(..., ge=1, le=90, description="App ID preserving PDF numbering 1 to 90")
    name: str = Field(..., description="App name as given in assignment")
    category: str = Field(..., description="One of the 9 categories from PDF")
    website_hint: str = Field(..., description="Original hint from PDF")
    summary: str = Field(default="", description="One-line description of what the app does")
    auth_methods: List[str] = Field(default_factory=list, description="List of auth methods: oauth2, api_key, basic, token, etc.")
    credential_access: CredentialAccess = Field(default_factory=CredentialAccess)
    api_types: List[str] = Field(default_factory=list, description="Supported API paradigms: rest, graphql, grpc, webhooks, etc.")
    api_breadth: ApiBreadth = Field(default="unknown")
    existing_mcp: ExistingMcp = Field(default="unknown")
    buildability: BuildabilityVerdict = Field(default="unknown")
    main_blocker: str = Field(default="none", description="Key hurdle if not buildable_now")
    confidence: ConfidenceLevel = Field(default="medium")
    evidence: List[EvidenceItem] = Field(default_factory=list)
    research_status: ResearchStatus = Field(default="complete")
    notes: str = Field(default="")


class RawDocument(BaseModel):
    url: str
    final_url: str
    title: str = ""
    timestamp: str
    source_method: Literal["firecrawl", "direct_http", "browser"]
    content_hash: str
    raw_markdown: str
    status_code: int = 200
    error: Optional[str] = None


class JevChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    confidence: Optional[float] = 0.0
    probabilities: Dict[str, float] = Field(default_factory=dict)


class JevNoulAnswer(BaseModel):
    type: Literal["noul"]
    noul: float  # probability of yes (0.0 to 1.0)


class JevScoreAnswer(BaseModel):
    type: Literal["score"]
    score: float
    confidence: Optional[float] = 0.0
    probabilities: Dict[str, float] = Field(default_factory=dict)
    legend: Optional[Dict[str, str]] = None


class AuditEntry(BaseModel):
    id: int
    name: str
    category: str
    sampled: bool = True
    ground_truth_url: str
    fields_checked: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Map of field -> {first_pass: val, final_pass: val, ground_truth: val, status: correct|incorrect|unverifiable, notes: str}"
    )
    overall_status: Literal["all_correct", "has_misses", "unverifiable"]
    audit_notes: str = ""
