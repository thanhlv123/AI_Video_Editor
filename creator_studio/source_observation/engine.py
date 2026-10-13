"""Pure transient detached construction and current logical binding."""
from .models import *
from .validation import preflight, require, validate_bundle, coverage
from ..presentation_policy import build_presentation_policy_proposal

def build_detached_source_observation_bundle(proposal, *, spec, claims, bindings):
    return validate_bundle(SourceObservationBundle(proposal, spec, claims, bindings))

def build_source_observation_bundle(manifest, proposal, *, output_profile,
                                    spec, policy, observation_spec, claims, bindings,
                                    **configuration):
    bundle = SourceObservationBundle(proposal, observation_spec, claims, bindings)
    preflight(bundle)
    validate_bundle(bundle)
    try:
        fresh = build_presentation_policy_proposal(manifest, proposal.draft,
            output_profile=output_profile, spec=spec, policy=policy, **configuration)
    except ValueError:
        raise SourceObservationError() from None
    require(proposal == fresh)
    # The public live M75 builder has already safely validated retained records.
    assets = {a.asset_id: a for a in manifest.acquisition.assets}
    materializations = {m.materialization_id: m for m in manifest.acquisition.materializations}
    for binding in bundle.bindings:
        require(binding.materialization_id in materializations)
        require(materializations[binding.materialization_id].asset_id == binding.asset_id)
        require(binding.asset_id in assets)
        if binding.observation_status is ObservationReferenceStatus.PRESENT:
            identity = bundle.claims[binding.observation_index].byte_identity
            asset = assets[binding.asset_id]
            require((identity.asset_id, identity.sha256, identity.byte_count) ==
                    (asset.asset_id, asset.sha256, asset.byte_count))
    return bundle

def assess_source_observation_bundle(bundle):
    validate_bundle(bundle)
    return SourceObservationAssessment(True, False, coverage(bundle))

def assess_current_source_observation(manifest, proposal, **configuration):
    bundle = build_source_observation_bundle(manifest, proposal, **configuration)
    return SourceObservationAssessment(True, True, coverage(bundle))
