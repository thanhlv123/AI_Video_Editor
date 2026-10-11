"""M66 discovery-only persistent contracts and exact signature payloads."""
from dataclasses import dataclass, field, replace
from enum import Enum
from .codec import to_data
from .rights import Rights
from .semantic import Purpose, exact_signature
from .visual import SemanticMentionRef

MAX_RUNS = 64
MAX_HISTORY_CANDIDATES = 16384
MAX_HISTORY_SHOTS = 65536
MAX_SHOTS = 4096
MAX_PROVIDER_CANDIDATES = 128
MAX_SHORTLIST = 32
MAX_CANDIDATES = 4096
MAX_EVIDENCE = 64
MAX_DIAGNOSTICS = 16
MAX_PROVIDERS = 16


class SourceClass(str, Enum):
    PERSONAL_LIBRARY = "PERSONAL_LIBRARY"
    PROJECT_MEDIA = "PROJECT_MEDIA"
    LICENSED_LIBRARY = "LICENSED_LIBRARY"
    PUBLIC_STOCK = "PUBLIC_STOCK"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class VisualMediaKind(str, Enum):
    VIDEO = "VIDEO"
    IMAGE = "IMAGE"
    GRAPHIC = "GRAPHIC"
    UNKNOWN = "UNKNOWN"


class UsageRestriction(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    REFERENCE_ONLY = "REFERENCE_ONLY"


class ClaimOrigin(str, Enum):
    UNKNOWN = "UNKNOWN"
    PROVIDER_DECLARATION = "PROVIDER_DECLARATION"


class ShotOutcome(str, Enum):
    CANDIDATES = "CANDIDATES"
    EMPTY = "EMPTY"
    INSUFFICIENT_INTENT = "INSUFFICIENT_INTENT"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class ProviderOutcomeKind(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


class MatchAspect(str, Enum):
    SUBJECT = "SUBJECT"
    ACTION = "ACTION"
    ENVIRONMENT = "ENVIRONMENT"
    GEOGRAPHY = "GEOGRAPHY"
    TEMPORAL = "TEMPORAL"
    MEDIA_FORM = "MEDIA_FORM"
    SHOT_PREFERENCE = "SHOT_PREFERENCE"


class Finding(str, Enum):
    MATCH = "MATCH"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RetrievalDiagnostic:
    code: str


@dataclass(frozen=True)
class CandidateTechnicalMetadata:
    width: int | None = None
    height: int | None = None
    source_duration_seconds: float | None = None


@dataclass(frozen=True)
class ProvenanceHint:
    declared_rights: Rights = Rights.UNKNOWN
    claim_origin: ClaimOrigin = ClaimOrigin.UNKNOWN
    license_identifier: str | None = None
    attribution: str | None = None


@dataclass(frozen=True)
class CandidateDescriptor:
    candidate_id: str
    provider_id: str
    provider_candidate_ref: str
    catalog_namespace: str
    source_class: SourceClass
    visual_media_kind: VisualMediaKind
    label: str | None
    technical_metadata: CandidateTechnicalMetadata
    provenance_hint: ProvenanceHint
    usage_restriction: UsageRestriction
    metadata_fingerprint: str


@dataclass(frozen=True)
class MatchEvidence:
    candidate_id: str
    aspect: MatchAspect
    finding: Finding
    method_id: str
    method_version: str
    evidence_ref: SemanticMentionRef | None = None


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    provider_version: str
    catalog_namespace: str
    supported_kinds: list[VisualMediaKind]
    supports_structured_intent: bool
    source_class: SourceClass
    request_limit: int = 32


@dataclass(frozen=True)
class RetrievalSpec:
    contract_version: str = "1"
    engine_version: str = "1"
    retriever_id: str = "structured_discovery"
    retriever_version: str = "1"
    providers: list[ProviderSpec] = field(default_factory=list)
    source_precedence: list[SourceClass] = field(default_factory=lambda: list(SourceClass))
    allowed_media_kinds: list[VisualMediaKind] = field(default_factory=lambda: [
        VisualMediaKind.VIDEO, VisualMediaKind.IMAGE, VisualMediaKind.GRAPHIC])
    provider_candidate_limit: int = 32
    candidates_per_shot: int = 8
    total_unique_candidates: int = 1024
    ordering_policy_version: str = "1"


@dataclass(frozen=True)
class ShotRetrievalResult:
    visual_unit_id: str
    planned_shot_id: str
    story_unit_ids: list[str]
    request_signature: str
    outcome: ShotOutcome
    candidate_ids: list[str]
    assessments: list[MatchEvidence]
    diagnostics: list[RetrievalDiagnostic]


@dataclass(frozen=True)
class ProviderOutcome:
    provider_id: str
    planned_shot_id: str
    outcome: ProviderOutcomeKind
    diagnostics: list[RetrievalDiagnostic] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalRun:
    retrieval_id: str
    purpose: Purpose
    visual_plan_id: str
    visual_plan_output_signature: str
    upstream_binding_signature: str
    retrieval_spec: RetrievalSpec
    retrieval_input_fingerprint: str
    retrieval_signature: str
    candidates: list[CandidateDescriptor]
    shot_results: list[ShotRetrievalResult]
    provider_outcomes: list[ProviderOutcome]
    diagnostics: list[RetrievalDiagnostic]
    output_signature: str


@dataclass
class RetrievalState:
    runs: list[RetrievalRun] = field(default_factory=list)
    active_creator_retrieval_id: str | None = None


def candidate_id(provider_id, catalog_namespace, reference):
    return "candidate:" + exact_signature(["2", provider_id, catalog_namespace, reference])


def metadata_fingerprint(candidate):
    data = to_data(candidate)
    data.pop("candidate_id")
    data.pop("metadata_fingerprint")
    return exact_signature(data)


def input_fingerprint(plan, binding):
    return exact_signature([plan.visual_plan_id, plan.output_signature, binding, [
        [u.visual_unit_id, s.planned_shot_id, s.story_unit_ids]
        for u in plan.units for s in u.planned_shots]])


def retrieval_signature(fingerprint, spec):
    return exact_signature([fingerprint, spec])


def generated_payload(run):
    return [run.candidates, run.shot_results, run.provider_outcomes, run.diagnostics]


def run_id(run):
    return "retrieval:" + exact_signature([run.retrieval_signature,
                                           exact_signature(generated_payload(run))])


def output_signature(run):
    data = to_data(run)
    data.pop("output_signature")
    return exact_signature(data)


def assign_identity(run):
    run = replace(run, retrieval_id=run_id(run))
    return replace(run, output_signature=output_signature(run))


def upstream_payload(manifest, plan):
    document = next(d for d in manifest.semantic.documents
                    if d.semantic_document_id == plan.semantic_document_id)
    source = next(s for s in manifest.semantic.source_revisions
                  if s.source_revision_id == document.source_revision_id)
    return [plan.visual_plan_id, plan.output_signature, document.semantic_document_id,
            document.output_signature, document.analysis_signature,
            document.content_revision_signature, source.source_revision_id,
            exact_signature(source.content)]


def upstream_binding(manifest, plan):
    return exact_signature(upstream_payload(manifest, plan))


def request_payload(plan, unit, shot, spec):
    """Pure structured projection shared with runtime; never includes narration."""
    preference = shot.media_form_preference.value
    preferred = {"VIDEO_PREFERRED": VisualMediaKind.VIDEO,
                 "IMAGE_PREFERRED": VisualMediaKind.IMAGE,
                 "GRAPHIC_PREFERRED": VisualMediaKind.GRAPHIC}.get(preference)
    kinds = [k for k in spec.allowed_media_kinds if preferred is None or k == preferred]
    return dict(visual_plan_id=plan.visual_plan_id,
        visual_plan_output_signature=plan.output_signature,
        visual_unit_id=unit.visual_unit_id, planned_shot_id=shot.planned_shot_id,
        story_unit_ids=shot.story_unit_ids, visual_purpose=unit.visual_purpose,
        representation_mode=unit.representation_mode, depiction_fidelity=unit.depiction_fidelity,
        requirements=[*unit.requirements, *shot.requirements],
        geography=unit.geography_requirement, temporal=unit.temporal_requirement,
        continuity=unit.continuity_requirements,
        constraints=[*unit.constraints, *shot.constraints], shot_role=shot.shot_role,
        shot_scale_preference=shot.shot_scale_preference,
        camera_motion_preference=shot.camera_motion_preference,
        media_form_preference=shot.media_form_preference, allowed_media_kinds=kinds,
        provider_request_limit=spec.provider_candidate_limit)


def request_signature(signature, payload):
    return exact_signature([signature, payload])


def has_intent(payload):
    return (any(payload[k].value != "UNKNOWN" for k in ("visual_purpose",
        "representation_mode", "depiction_fidelity", "shot_role", "shot_scale_preference",
        "camera_motion_preference", "media_form_preference")) or bool(
        payload["requirements"] or payload["constraints"] or payload["continuity"]
        or any(r is not None and (r.fidelity.value != "UNKNOWN" or r.evidence.mentions)
               for r in (payload["geography"], payload["temporal"]))))
