"""M67 logical choices and append-only review contracts. No acquired assets."""
from dataclasses import dataclass, field, replace
from enum import Enum
from .codec import to_data
from .semantic import Purpose, ReviewStatus, exact_signature

MAX_SELECTION_RUNS = 64
MAX_SHOT_SELECTIONS_PER_RUN = 4096
MAX_TOTAL_HISTORICAL_SHOT_SELECTIONS = 65536
MAX_SELECTION_REVIEWS = 65536
MAX_DIAGNOSTICS_PER_LIST = 16


class SelectionOutcome(str, Enum):
    SELECTED = "SELECTED"
    UNRESOLVED = "UNRESOLVED"


class SelectionSource(str, Enum):
    AUTOMATIC = "AUTOMATIC"
    CREATOR = "CREATOR"


class SelectionReason(str, Enum):
    FIRST_ELIGIBLE = "first_eligible"
    CREATOR_CHOICE = "creator_choice"
    RETRIEVAL_EMPTY = "retrieval_empty"
    RETRIEVAL_UNSUPPORTED = "retrieval_unsupported"
    RETRIEVAL_FAILED = "retrieval_failed"
    INSUFFICIENT_INTENT = "insufficient_intent"
    NO_ELIGIBLE_CANDIDATE = "no_eligible_candidate"
    HARD_REQUIREMENT_UNVERIFIED = "hard_requirement_unverified"
    CREATOR_REVIEW_REQUIRED = "creator_review_required"


@dataclass(frozen=True)
class SelectionSpec:
    selection_contract_version: str = "1"
    baseline_policy_id: str = "first_eligible"
    baseline_policy_version: str = "1"


@dataclass(frozen=True)
class SelectedCandidateRef:
    candidate_id: str
    metadata_fingerprint: str


@dataclass(frozen=True)
class ShotSelection:
    shot_selection_id: str
    planned_shot_id: str
    outcome: SelectionOutcome
    selected_candidate: SelectedCandidateRef | None
    source: SelectionSource
    reason: SelectionReason


@dataclass(frozen=True)
class SelectionRun:
    selection_id: str
    purpose: Purpose
    retrieval_id: str
    retrieval_output_signature: str
    selection_spec: SelectionSpec
    selection_input_fingerprint: str
    selection_signature: str
    shot_selections: list[ShotSelection]
    diagnostics: list[SelectionReason]
    output_signature: str


@dataclass(frozen=True)
class SelectionReview:
    review_id: str
    shot_selection_id: str
    predecessor_review_id: str | None
    status: ReviewStatus
    locked: bool


@dataclass
class SelectionState:
    runs: list[SelectionRun] = field(default_factory=list)
    reviews: list[SelectionReview] = field(default_factory=list)
    active_creator_selection_id: str | None = None


def input_fingerprint(retrieval):
    return exact_signature([retrieval.retrieval_id, retrieval.output_signature])


def selection_signature(fingerprint, spec):
    return exact_signature([fingerprint, spec])


def choice_payload(choice):
    # Origin and selected-choice reason do not change logical choice identity.
    return [choice.planned_shot_id, choice.outcome, choice.selected_candidate,
            choice.reason if choice.outcome == SelectionOutcome.UNRESOLVED else None]


def shot_id(retrieval_id, spec, choice):
    return "shot_selection:" + exact_signature([
        spec.selection_contract_version, retrieval_id, choice_payload(choice)])


def run_id(run):
    return "selection:" + exact_signature([run.selection_signature,
        [choice_payload(s) for s in run.shot_selections]])


def output_signature(run):
    data = to_data(run)
    data.pop("output_signature")
    return exact_signature(data)


def assign_identity(run):
    choices = [replace(s, shot_selection_id=shot_id(run.retrieval_id, run.selection_spec, s))
               for s in run.shot_selections]
    run = replace(run, shot_selections=choices)
    run = replace(run, selection_id=run_id(run))
    return replace(run, output_signature=output_signature(run))


def review_id(review):
    return "selection_review:" + exact_signature([review.shot_selection_id,
        review.predecessor_review_id, review.status, review.locked])


def effective_reviews(state):
    """Use only after chain validation. Record order is the transition order."""
    return {r.shot_selection_id: r for r in state.reviews}


def effective_review_projection(state, run):
    reviews = effective_reviews(state)
    return [[s.shot_selection_id, reviews[s.shot_selection_id].review_id,
             reviews[s.shot_selection_id].status, reviews[s.shot_selection_id].locked]
            if s.shot_selection_id in reviews else
            [s.shot_selection_id, None, ReviewStatus.PENDING, False]
            for s in run.shot_selections]


def effective_output_signature(state, run):
    return exact_signature([output_signature(run), effective_review_projection(state, run)])


def complete(run):
    return all(s.outcome == SelectionOutcome.SELECTED for s in run.shot_selections)
