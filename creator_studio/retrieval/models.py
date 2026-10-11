"""Runtime-only structured requests and untrusted provider proposals."""
from dataclasses import dataclass, field
from ..manifest.retrieval import (VisualMediaKind, CandidateTechnicalMetadata,
    ProvenanceHint, UsageRestriction, MatchEvidence, ProviderOutcomeKind, RetrievalDiagnostic)
from ..manifest.visual import (VisualPurpose, RepresentationMode, DepictionFidelity,
    VisualRequirement, GeographyRequirement, TemporalRequirement, ContinuityRequirement,
    VisualConstraint, ShotRole, ShotScale, CameraMotion, MediaFormPreference)


class RetrievalError(ValueError):
    def __init__(self, code="retrieval_candidate_invalid"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RetrievalRequest:
    visual_plan_id: str
    visual_plan_output_signature: str
    visual_unit_id: str
    planned_shot_id: str
    story_unit_ids: list[str]
    visual_purpose: VisualPurpose
    representation_mode: RepresentationMode
    depiction_fidelity: DepictionFidelity
    requirements: list[VisualRequirement]
    geography: GeographyRequirement | None
    temporal: TemporalRequirement | None
    continuity: list[ContinuityRequirement]
    constraints: list[VisualConstraint]
    shot_role: ShotRole
    shot_scale_preference: ShotScale
    camera_motion_preference: CameraMotion
    media_form_preference: MediaFormPreference
    allowed_media_kinds: list[VisualMediaKind]
    provider_request_limit: int


@dataclass(frozen=True)
class ProviderCapabilities:
    supported_kinds: list[VisualMediaKind]
    supports_structured_intent: bool


@dataclass(frozen=True)
class CandidateProposal:
    provider_candidate_ref: str
    visual_media_kind: VisualMediaKind
    label: str | None = None
    technical_metadata: CandidateTechnicalMetadata = field(default_factory=CandidateTechnicalMetadata)
    provenance_hint: ProvenanceHint = field(default_factory=ProvenanceHint)
    usage_restriction: UsageRestriction = UsageRestriction.UNVERIFIED


@dataclass(frozen=True)
class ProposalAssessment:
    # Position refers to this result's proposals, not a provider-authoritative ID.
    candidate_position: int
    evidence: MatchEvidence


@dataclass(frozen=True)
class ProviderRetrievalResult:
    candidates: list[CandidateProposal] = field(default_factory=list)
    assessments: list[ProposalAssessment] = field(default_factory=list)
    outcome: ProviderOutcomeKind = ProviderOutcomeKind.SUCCESS
    diagnostics: list[RetrievalDiagnostic] = field(default_factory=list)
