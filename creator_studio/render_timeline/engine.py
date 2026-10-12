"""Atomic M72 builder; current eligibility and byte usability are observations."""
from copy import deepcopy
from dataclasses import fields
from types import FunctionType, BuiltinFunctionType
from ..manifest.render_timeline import *
from ..manifest.render_timeline_validation import (require, bounded_value, preflight_history,
    project_plan, validate_history, validate_plan, complete_render_timeline, uncovered_intervals,
    preflight_upstream)
from ..manifest.validation import require_valid
from ..manifest.semantic import exact_signature
from ..placement_timing.engine import (preflight as timing_preflight,
    active_plan as active_timing, logical_inputs, current_placement_timing_eligibility)
from ..orchestrator.contracts import CancellationToken, Cancelled
from .models import RenderTimelineError, RenderTimelineEligibility

def normalize_dependencies(dependencies):
    try:
        require(not isinstance(dependencies, (str, bytes, dict)))
        iterator = iter(dependencies)
        values = []
        for _ in range(4):
            try:
                values.append(next(iterator))
            except StopIteration:
                break
        result = tuple(values)
        require(result in ((), ("media_acquisition", "edit_planning", "placement_timing")))
        return result
    except Exception:
        raise RenderTimelineError() from None

def preflight_for_expensive_operation(manifest):
    """Complete capacity sweep with no cancellation or external observations."""
    preflight_history(getattr(manifest, "render_timeline", None))
    preflight_upstream(manifest)
    timing_preflight(manifest)


def preflight(manifest, control=None):
    if control:
        control.check()
    preflight_for_expensive_operation(manifest)


def callable_identity(value):
    owner = getattr(value, "__self__", None)
    function = getattr(value, "__func__", None)
    if function is not None:
        return (id(owner), id(function))
    if owner is not None:
        return (id(owner), id(getattr(type(owner), value.__name__, value)))
    if value is None or isinstance(value, (FunctionType, BuiltinFunctionType)):
        return (id(value),)
    return (id(value), id(getattr(type(value), "__call__", None)))


class _FencedControl:
    """Close upstream cancellation callback windows before they return."""
    def __init__(self, control, manifest):
        self.control, self.manifest = control, manifest
        self.identity = callable_identity(control.check)

    def check(self):
        require(callable_identity(self.control.check) == self.identity)
        self.control.check()
        preflight_for_expensive_operation(self.manifest)
        require(callable_identity(self.control.check) == self.identity)


def collaborator_fence(storage, inspector, control):
    from ..acquisition.storage import ManagedStorage
    methods = [callable_identity(getattr(storage, "verify", None)), callable_identity(control.check)]
    configuration = []
    if isinstance(storage, ManagedStorage):
        methods.extend(callable_identity(getattr(storage, name))
            for name in ("resolve", "hash_file", "_check"))
        configuration.append(storage.root)
    if inspector is not None:
        methods.append(callable_identity(inspector.inspect))
        values = tuple(getattr(inspector, name) for name in
            ("inspector_id", "inspector_version", "policy_id", "policy_version"))
        bounded_value(values)
        configuration.append(values)
    return (id(storage), id(inspector), tuple(methods), tuple(configuration))


def active_plan(manifest):
    return next((p for p in manifest.render_timeline.plans if
        p.render_timeline_plan_id == manifest.render_timeline.active_render_timeline_plan_id), None)

def boundary_unchanged(before, after):
    return all(getattr(before, f.name) == getattr(after, f.name)
        for f in fields(before) if f.name != "render_timeline")

def narration_storage_fence(configuration):
    """Transient authority only; never included in a deterministic signature."""
    storage = configuration.get("storage")
    return (id(storage), callable_identity(getattr(storage, "open_read", None)))


def configuration_snapshot(spec, configuration):
    require(set(configuration) <= {"storage", "acquisition_spec", "edit_spec", "timing_spec",
        "acceptance_policy_id", "acceptance_policy_version", "voice_spec",
        "voice_acceptance_policy_id", "voice_acceptance_policy_version"})
    values = {k: v for k, v in configuration.items() if k != "storage"}
    bounded_value([spec, values])
    return (signed("configuration", [spec, values]), narration_storage_fence(configuration))

def _upstream_configuration(manifest, configuration):
    from ..manifest.acquisition import AcquisitionSpec
    from ..manifest.editing import EditSpec
    from ..manifest.placement_timing import PlacementTimingSpec
    values = dict(configuration)
    expected_acquisition = values.pop("acquisition_spec", None) or AcquisitionSpec()
    expected_edit = values.pop("edit_spec", None) or EditSpec()
    expected_timing = values.pop("timing_spec", None) or PlacementTimingSpec()
    bounded_value([expected_acquisition, expected_edit, expected_timing])
    edit, _, _ = logical_inputs(manifest, CancellationToken())
    acquisition = next(r for r in manifest.acquisition.runs if r.acquisition_id == edit.acquisition_id)
    require(acquisition.acquisition_spec == expected_acquisition and edit.edit_spec == expected_edit)
    values["spec"] = expected_timing
    return values

def current_render_timeline_eligibility(manifest, *, spec=None, control=None, **timing_configuration):
    control = _FencedControl(control or CancellationToken(), manifest)
    preflight(manifest, control)
    captured = exact_signature(manifest)
    configuration = configuration_snapshot(spec, timing_configuration)
    historical = logical = current = False
    plan = active_plan(manifest)
    try:
        require_valid(manifest)
        historical = True
        edit, _, _ = logical_inputs(manifest, control)
        timing = active_timing(manifest)
        logical = plan is not None and timing is not None and (
            plan.acquisition_id, plan.edit_plan_id, plan.edit_output_signature,
            plan.placement_timing_plan_id, plan.timing_evidence_signature) == (
            edit.acquisition_id, edit.edit_plan_id, edit.output_signature,
            timing.placement_timing_plan_id, signed("timing_evidence", timing))
        upstream_configuration = _upstream_configuration(manifest, timing_configuration)
        current = current_placement_timing_eligibility(manifest, control=control,
            **upstream_configuration).eligible
    except Cancelled:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, StopIteration):
        pass
    require(configuration_snapshot(spec, timing_configuration) == configuration)
    preflight_for_expensive_operation(manifest)
    control.check()
    preflight(manifest, control)
    require(configuration_snapshot(spec, timing_configuration) == configuration)
    preflight_for_expensive_operation(manifest)
    require(exact_signature(manifest) == captured)
    return RenderTimelineEligibility(historical, logical, current,
        plan is not None and plan.spec == (spec or RenderTimelineSpec()),
        plan is not None and historical and complete_render_timeline(manifest, plan))

def build_render_timeline(manifest, *, spec=None, dependencies=(), control=None, **timing_configuration):
    control = _FencedControl(control or CancellationToken(), manifest)
    control.check()
    normalized_dependencies = normalize_dependencies(dependencies)
    preflight(manifest, control)
    require_valid(manifest)
    spec = spec or RenderTimelineSpec()
    require(spec == RenderTimelineSpec())
    captured = exact_signature(manifest)
    configuration = configuration_snapshot(spec, timing_configuration)
    logical_inputs(manifest, control)
    upstream_configuration = _upstream_configuration(manifest, timing_configuration)
    timing = active_timing(manifest)
    require(timing is not None)
    proposal_plan = project_plan(manifest, timing, spec, control)
    control.check()
    current = active_plan(manifest)
    reuse = current is not None and current == proposal_plan
    if reuse:
        from .stage import RenderTimelineStage
        stage = RenderTimelineStage(spec=spec, dependencies=normalized_dependencies, **timing_configuration)
        states = [s for s in manifest.processing if s.stage == stage.stage_id]
        require(len(states) == 1 and stage.validate_reuse(manifest, states[0].execution))
    else:
        state = manifest.render_timeline
        require(len(state.plans) < MAX_PLANS)
        require(sum(len(p.entries) for p in state.plans) + len(proposal_plan.entries) <= MAX_TOTAL_ENTRIES)
        require(all(p.render_timeline_plan_id != proposal_plan.render_timeline_plan_id for p in state.plans))
        preflight_history(RenderTimelineState(state.plans + [proposal_plan]), control)
    # M71 owns narration usability; M72 also fences its actual byte-access authority.
    require(current_placement_timing_eligibility(manifest, control=control,
        **upstream_configuration).eligible)
    require(configuration_snapshot(spec, timing_configuration) == configuration)
    preflight_for_expensive_operation(manifest)
    control.check()
    preflight(manifest, control)
    require(configuration_snapshot(spec, timing_configuration) == configuration)
    preflight_for_expensive_operation(manifest)
    require(exact_signature(manifest) == captured)
    if reuse:
        result = deepcopy(manifest)
    else:
        control.check()
        require(configuration_snapshot(spec, timing_configuration) == configuration)
        preflight_for_expensive_operation(manifest)
        result = deepcopy(manifest)
        result.render_timeline.plans.append(proposal_plan)
        result.render_timeline.active_render_timeline_plan_id = proposal_plan.render_timeline_plan_id
    captured_result = exact_signature(result)
    control.check()
    preflight(result, control)
    require(configuration_snapshot(spec, timing_configuration) == configuration)
    preflight_for_expensive_operation(result)
    preflight_for_expensive_operation(manifest)
    require_valid(result)
    require(boundary_unchanged(manifest, result))
    preflight(manifest, control)
    control.check()
    # Final pure fences follow every callback-capable cancellation boundary.
    preflight(manifest)
    preflight(result)
    require(configuration_snapshot(spec, timing_configuration) == configuration)
    preflight_for_expensive_operation(manifest)
    preflight_for_expensive_operation(result)
    require(exact_signature(manifest) == captured and exact_signature(result) == captured_result)
    return result

def observe_media_usability(manifest, *, storage, inspector=None, acquisition_spec=None, control=None):
    """Point-in-time M68 observation; no mutation or executable-render claim."""
    from ..acquisition.engine import current_usability
    control = _FencedControl(control or CancellationToken(), manifest)
    preflight(manifest, control)
    require_valid(manifest)
    captured = exact_signature(manifest)
    bounded_value(acquisition_spec)
    configuration = signed("usability_configuration", acquisition_spec)
    identities = collaborator_fence(storage, inspector, control.control)
    check_identity = callable_identity(control.check)
    result = current_usability(manifest, storage=storage, inspector=inspector,
        spec=acquisition_spec, control=control)
    preflight_for_expensive_operation(manifest)
    require(callable_identity(control.check) == check_identity)
    require(collaborator_fence(storage, inspector, control.control) == identities)
    control.check()
    preflight(manifest, control)
    bounded_value(acquisition_spec)
    require(exact_signature(manifest) == captured and signed("usability_configuration", acquisition_spec) == configuration)
    require(collaborator_fence(storage, inspector, control.control) == identities)
    require_valid(manifest)
    require(exact_signature(manifest) == captured)
    require(type(result) is bool)
    return result
