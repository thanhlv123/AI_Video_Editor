"""Pure live projection and authority-gated logical construction; no collaborators."""
from dataclasses import fields
from .models import *
from .validation import (require, preflight, preflight_manifest, validate_draft,
                         validate_spec_job, exact_lane_reasons)
from ..manifest.validation import require_valid
from ..manifest.render_preparation_validation import validate_plan
from ..render_preparation import engine as preparation

def _configuration_preflight(output_profile, spec, configuration):
    from ..manifest.acquisition import AcquisitionSpec
    from ..manifest.editing import EditSpec
    from ..manifest.placement_timing import PlacementTimingSpec
    from ..manifest.voice_timing import AlignmentSpec
    from ..manifest.render_timeline import RenderTimelineSpec
    schemas = dict(acquisition_spec=AcquisitionSpec, edit_spec=EditSpec,
        timing_spec=PlacementTimingSpec, timeline_spec=RenderTimelineSpec,
        voice_spec=AlignmentSpec, acceptance_policy_id=str,
        acceptance_policy_version=str, voice_acceptance_policy_id=str,
        voice_acceptance_policy_version=str)
    require(type(configuration) is dict and set(configuration) == set(schemas))
    preflight(output_profile, OutputProfile)
    preflight(spec, RenderPreparationSpec)
    for name, cls in schemas.items():
        preflight(configuration[name], cls, upstream=True)
    preparation.configuration_snapshot(output_profile, spec, configuration)

def _copy_record(value, cls):
    """Called only after bounded strict upstream validation; allowlisted records."""
    return cls(**{f.name: getattr(value, f.name) for f in fields(cls)})

def build_render_job_draft(manifest, *, output_profile, spec, **configuration):
    preflight_manifest(manifest)
    _configuration_preflight(output_profile, spec, configuration)
    require_valid(manifest)
    plan = preparation.active_plan(manifest)
    require(plan is not None)
    validate_plan(manifest, plan)
    require(preparation.current_logically_eligible(manifest, output_profile=output_profile,
                                                  spec=spec, **configuration))
    timeline = next(p for p in manifest.render_timeline.plans if
        p.render_timeline_plan_id == plan.timeline_binding.render_timeline_plan_id)
    require(len(timeline.entries) == len(plan.entries))
    clips = tuple(RenderVisualClip(**{f.name: tuple(e.diagnostics)
        if f.name == "diagnostics" else getattr(e, f.name)
        for f in fields(RenderVisualClip)}) for e in timeline.entries)
    assessments = tuple(RenderEntryAssessment(**{f.name: tuple(e.requirements)
        if f.name == "requirements" else getattr(e, f.name)
        for f in fields(RenderEntryAssessment)}) for e in plan.entries)
    narration = plan.narration_binding
    narration_values = {f.name: getattr(narration, f.name) for f in fields(NarrationBinding)}
    from ..manifest.voice_timing import AudioInspectionEvidence, AcceptanceReceipt
    narration_values["inspection"] = _copy_record(narration.inspection, AudioInspectionEvidence)
    narration_values["acceptance_receipt"] = _copy_record(narration.acceptance_receipt, AcceptanceReceipt)
    binding_values = {f.name: getattr(plan.timeline_binding, f.name)
                      for f in fields(RenderTimelineBinding)}
    from ..manifest.render_timeline import RenderTimelineSpec
    binding_values["spec"] = _copy_record(plan.timeline_binding.spec, RenderTimelineSpec)
    draft = RenderJobDraft(_copy_record(plan, RenderJobBinding),
        _copy_record(plan.output_profile, OutputProfile), _copy_record(plan.spec, RenderPreparationSpec),
        RenderTimelineBinding(**binding_values), _copy_record(timeline, RenderSourceBinding),
        RenderNarrationInput(NarrationBinding(**narration_values)),
        plan.output_duration_us, clips, assessments,
        tuple(_copy_record(i, UncoveredInterval) for i in plan.uncovered_intervals),
        tuple(plan.requirements), plan.conclusion, exact_lane_reasons(clips, plan.output_duration_us))
    return validate_draft(draft)

def construct_render_job_spec(manifest, draft, *, output_profile, spec, **configuration):
    """Construct only against the current, exact live Manifest projection."""
    current = build_render_job_draft(manifest, output_profile=output_profile,
                                     spec=spec, **configuration)
    validate_draft(draft)
    require(draft == current)
    return validate_spec_job(RenderJobSpec(draft))

def assess_render_job_draft(draft):
    """Detached consistency cannot establish current authority or constructibility."""
    validate_draft(draft)
    satisfied = not draft.requirements and all(not e.requirements for e in draft.entry_assessments)
    return RenderJobAssessment(True, False, satisfied, False)

def assess_current_render_job(manifest, *, output_profile, spec, **configuration):
    draft = build_render_job_draft(manifest, output_profile=output_profile, spec=spec, **configuration)
    detached = assess_render_job_draft(draft)
    constructible = False
    if detached.preparation_requirements_satisfied and not draft.lane_reasons:
        try:
            construct_render_job_spec(manifest, draft, output_profile=output_profile,
                                      spec=spec, **configuration)
        except ValueError:
            pass
        else:
            constructible = True
    return RenderJobAssessment(True, True, detached.preparation_requirements_satisfied,
                               constructible)
