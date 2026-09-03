"""Pydantic schemas for the deep-research data model."""

from datetime import datetime
from pydantic import BaseModel, Field
from .enums import Perspective, Confidence, VerificationStatus, RunStatus


class Claim(BaseModel):
    """A single finding from a researcher."""

    text: str = Field(description="The claim statement")
    confidence: Confidence = Field(description="Researcher's confidence level")
    sources: list[str] = Field(default_factory=list, description="URLs supporting this claim")
    counterpoints: list[str] = Field(default_factory=list, description="Known opposing evidence or caveats")


class ResearchCard(BaseModel):
    """Output of a single Researcher Agent."""

    perspective: str = Field(description="Which perspective this card covers")
    role: str = Field(default="", description="The role/stance assigned by the orchestrator (e.g. 技术专家/批判者)")
    research_question: str = Field(description="The specific question assigned to this researcher")
    key_findings: list[Claim] = Field(description="List of claims discovered")
    gaps: list[str] = Field(default_factory=list, description="Areas this perspective failed to cover")
    raw_transcript: str = Field(default="", description="Full search transcript")


class ReflectionResult(BaseModel):
    """Quality gate output — a reviewer's assessment of Phase 1 research.

    The Reflector agent produces quality_score + issues + feedback;
    `acceptable` is computed deterministically by the pipeline
    (score >= QUALITY_THRESHOLD AND findings >= MIN_FINDINGS), never
    trusted to the model.
    """

    quality_score: int = Field(default=0, ge=0, le=100, description="0-100 quality score")
    issues: list[str] = Field(default_factory=list, description="Concrete defects found")
    feedback: str = Field(default="", description="Improvement instructions for the next search round")
    acceptable: bool = Field(default=False, description="Set by pipeline from score + finding-count thresholds")
    skipped: bool = Field(default=False, description="True when there were no findings to reflect on")


class VerificationEntry(BaseModel):
    """Verification result for a single claim."""

    claim_index: int = Field(description="Index into ResearchCard.key_findings")
    claim_text: str = Field(description="The original claim text")
    status: VerificationStatus = Field(description="Verification outcome")
    reasoning: str = Field(description="Why this status was assigned")
    checked_sources: list[str] = Field(default_factory=list, description="Sources actually verified")
    fact_status: str | None = Field(default=None, description="Whether the underlying fact holds (verified/suspect/disputed/false/unverifiable)")
    confidence: int | None = Field(default=None, ge=0, le=100, description="0-100 confidence from independent review")
    presentation_issues: list[str] = Field(default_factory=list, description="Wording/context caveats that do not change the fact")


class RefutationEntry(BaseModel):
    """A refutation challenge from the Refuter."""

    claim_index: int
    # claim_text is OPTIONAL at the model boundary: the model sometimes
    # omits it, and dropping the whole refutation loses real content.
    # The crew backfills it from the original claims via claim_index.
    claim_text: str = Field(default="", description="The original claim text")
    challenge: str = Field(description="The specific challenge to this claim")
    severity: str = Field(default="minor", description="critical / moderate / minor")
    counter_evidence: list[str] = Field(default_factory=list, description="URLs that contradict the claim")


class VerifiedCard(BaseModel):
    """Output after adversarial verification."""

    perspective: str
    original_card_id: str = ""
    verification_round: int = Field(default=1, description="Which round of verification")
    entries: list[VerificationEntry] = Field(default_factory=list)
    refutations: list[RefutationEntry] = Field(default_factory=list)
    resolved: bool = Field(default=False, description="True if no disputes remain")
    summary: str = Field(default="", description="Verifier's overall assessment")


class ScoreResult(BaseModel):
    """Quality Scorer output."""

    overall_score: int = Field(default=0, ge=0, le=100, description="0-100 overall confidence score")
    claim_scores: list[dict] = Field(default_factory=list, description="Per-claim {claim_index, source_reliability, verification_consistency, perspective_coverage, grade}")
    summary: str = ""


class InsightResult(BaseModel):
    """Insight Extractor output."""

    consensus_signals: list[str] = Field(default_factory=list, description="Claims agreed across perspectives")
    contradictions: list[str] = Field(default_factory=list, description="Conflicting claims across perspectives")
    blind_spots: list[str] = Field(default_factory=list, description="Areas no perspective covered")
    time_sensitive_items: list[str] = Field(default_factory=list, description="Items that may become outdated")


class ResearchRun(BaseModel):
    """Complete record of one research execution."""

    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S"))
    question: str
    status: RunStatus = RunStatus.PENDING
    research_cards: list[ResearchCard] = Field(default_factory=list)
    verified_cards: list[VerifiedCard] = Field(default_factory=list)
    score: ScoreResult | None = None
    insights: InsightResult | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None


class ClaimSourceRef(BaseModel):
    """Reference to the research-phase claim that an answer claim maps to."""

    perspective: str = Field(default="", description="Research card perspective")
    card_index: int | None = Field(default=None, description="Index into research cards list")
    claim_index: int | None = Field(default=None, description="Index into key_findings")


class EvidenceLink(BaseModel):
    """One piece of evidence supporting or contradicting a claim."""

    url: str = Field(default="", description="Source URL")
    tool: str = Field(default="", description="Tool that produced this evidence")
    event_id: str = Field(default="", description="Event-sourcing event ID if known")
    snippet: str = Field(default="", description="Short supporting snippet")
    source_reliability: int = Field(default=0, ge=0, le=5, description="Source reliability 1-5")
    support: str = Field(default="neutral", description="support / contradict / neutral")


class ClaimNode(BaseModel):
    """A single atomic claim extracted from the final answer."""

    claim_id: str = Field(default="", description="Stable claim ID within this run")
    text: str = Field(description="Exact substring of the original answer text")
    claim_type: str = Field(default="direct_answer", description="direct_answer / supporting / contextual")
    span: dict | None = Field(default=None, description="Character span {start,end} in original_text")
    parent_claim_id: str | None = Field(default=None, description="Parent claim ID for hierarchy")
    source_claim_ref: ClaimSourceRef | None = Field(default=None, description="Mapped research claim")
    status: str = Field(default="unverifiable", description="verified / suspect / disputed / false / unverifiable")
    confidence: int = Field(default=0, ge=0, le=100, description="0-100 confidence")
    reasoning: str = Field(default="", description="Verification reasoning or summary")
    evidence_links: list[EvidenceLink] = Field(default_factory=list, description="Evidence URLs")
    event_ids: list[str] = Field(default_factory=list, description="Related event-sourcing event IDs")


class AnswerDocument(BaseModel):
    """The non-destructive claim annotation layer over a final answer."""

    run_id: str = Field(default="", description="Research run ID")
    original_text: str = Field(default="", description="Original report text, unchanged")
    overall_confidence: int = Field(default=0, ge=0, le=100, description="Aggregated confidence")
    claims: list[ClaimNode] = Field(default_factory=list)
    generated_at: str = Field(default="", description="ISO timestamp of annotation generation")
