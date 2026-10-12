"""Transient detached reconstruction and M74-gated live binding."""
from .models import *
from .validation import preflight, require, validate_policy, validate_proposal, derive_obligations
from ..render_job import validate_draft, build_render_job_draft


def build_detached_presentation_policy_proposal(draft, *, policy):
    preflight(draft, RenderJobDraft)
    preflight(policy, PresentationPolicySpec)
    validate_draft(draft)
    validate_policy(policy)
    return validate_proposal(PresentationPolicyProposal(
        draft, policy, derive_obligations(draft, policy)))


def build_presentation_policy_proposal(manifest, supplied_draft, *, output_profile,
                                       spec, policy, **configuration):
    preflight(supplied_draft, RenderJobDraft)
    preflight(policy, PresentationPolicySpec)
    validate_draft(supplied_draft)
    # M74 owns bounded live Manifest/configuration preflight and authority.
    fresh = build_render_job_draft(manifest, output_profile=output_profile,
                                  spec=spec, **configuration)
    require(supplied_draft == fresh)
    return build_detached_presentation_policy_proposal(supplied_draft, policy=policy)


def assess_presentation_policy_proposal(proposal):
    validate_proposal(proposal)
    return PresentationPolicyAssessment(True, False, True)


def assess_current_presentation_policy(manifest, supplied_draft, *, output_profile,
                                       spec, policy, **configuration):
    build_presentation_policy_proposal(manifest, supplied_draft,
        output_profile=output_profile, spec=spec, policy=policy, **configuration)
    return PresentationPolicyAssessment(True, True, True)
