"""Bounded exact schemas before semantic validation or equality."""
from dataclasses import is_dataclass
from enum import Enum
import re
from ..render_job.models import SIGNATURE_LENGTH
from types import UnionType
from typing import get_args, get_origin, get_type_hints
from .models import *
from ..render_job import validate_draft
from ..manifest.render_preparation import UncoveredInterval


def require(condition):
    if not condition:
        raise PresentationPolicyError()


def preflight(value, schema=PresentationPolicyProposal):
    """One occurrence budget; ancestry rejects cycles, shared records are allowed.

    Only trusted schema classes are inspected. Unknown instance classes are
    compared by identity, never hashed or asked for attributes.
    """
    remaining = MAX_TRAVERSAL_NODES
    ancestry = set()
    def walk(item, expected, depth):
        nonlocal remaining
        remaining -= 1
        require(remaining >= 0 and depth <= MAX_TRAVERSAL_DEPTH)
        origin = get_origin(expected)
        if origin is UnionType:
            options = get_args(expected)
            selected = next((t for t in options if type(item) is t), None)
            require(selected is not None)
            walk(item, selected, depth)
            return
        if origin is tuple:
            require(type(item) is tuple)
            require(len(item) <= MAX_PRESENTATION_OBLIGATIONS + (1 if get_args(expected)[0] is UncoveredInterval else 0))
            container = True
        else:
            require(type(item) is expected)
            container = is_dataclass(expected)
        if container:
            require(id(item) not in ancestry)
            ancestry.add(id(item))
            try:
                if origin is tuple:
                    for child in item:
                        walk(child, get_args(expected)[0], depth + 1)
                else:
                    hints = get_type_hints(expected)
                    members = object.__getattribute__(item, "__dict__")
                    require(type(members) is dict and len(members) == len(hints))
                    for key in members:
                        require(type(key) is str)
                    require(set(members) == set(hints))
                    for key, child_schema in hints.items():
                        walk(members[key], child_schema, depth + 1)
            finally:
                ancestry.remove(id(item))
        elif expected is int:
            require(0 <= item <= MAX_INTEGER)
        elif expected is str:
            require(len(item) <= MAX_GENERAL_SCALAR)
        elif isinstance(expected, type) and issubclass(expected, Enum):
            require(any(item is member for member in expected))
        else:
            require(expected is bool or expected is type(None))
    walk(value, schema, 0)


def validate_policy(policy):
    preflight(policy, PresentationPolicySpec)
    require(policy.contract_version == "1" and policy.engine_version == "1")
    expected = tuple(PresentationChoice)
    actual = (policy.still_holding_rule, policy.display_geometry_rule,
        policy.square_pixel_rule, policy.rotation_rule, policy.opacity_rule,
        policy.whole_video_frame_lattice_rule)
    require(all(a is b for a, b in zip(actual, expected)))
    return policy


def derive_obligations(draft, policy):
    """Internal reconstruction after exact preflight and M74 validation."""
    result = []
    profile = draft.output_profile
    # M74 validation guarantees equal lengths, ordinal order, and exact
    # clip/assessment identity, usage, timeline, and source coordinates.
    for clip, assessment in zip(draft.visual_clips, draft.entry_assessments):
        require(clip.source_usage is SourceUsage.STILL_IMAGE or
                clip.source_usage is SourceUsage.WHOLE_VIDEO)
        video = clip.source_usage is SourceUsage.WHOLE_VIDEO
        result.append(PresentationObligation(clip.ordinal, clip.placement_id,
            clip.materialization_id, clip.asset_id,
            clip.materialization_evidence_signature, clip.asset_evidence_signature,
            clip.source_usage, assessment.source_width_px, assessment.source_height_px,
            clip.timeline_start_us, clip.timeline_end_us, profile.width_px,
            profile.height_px, policy.square_pixel_rule, policy.rotation_rule,
            policy.opacity_rule, policy.display_geometry_rule,
            None if video else policy.still_holding_rule,
            policy.whole_video_frame_lattice_rule if video else None,
            profile.frame_rate_num if video else None,
            profile.frame_rate_den if video else None,
            clip.source_start_us if video else None,
            clip.source_end_us if video else None))
    return tuple(result)


def validate_proposal(proposal):
    preflight(proposal)
    validate_draft(proposal.draft)
    validate_policy(proposal.policy)
    for obligation in proposal.obligations:
        for dimension in (obligation.source_width_px, obligation.source_height_px):
            require(dimension is None or 0 < dimension <= MAX_INTEGER)
        for signature in (obligation.materialization_evidence_signature,
                          obligation.asset_evidence_signature):
            require(type(signature) is str and len(signature) == SIGNATURE_LENGTH and
                    re.fullmatch(r"[0-9a-f]{64}", signature) is not None)
    require(proposal.obligations == derive_obligations(proposal.draft, proposal.policy))
    return proposal
