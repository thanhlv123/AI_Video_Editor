"""Atomic deterministic proposals and separately fenced transient observations."""
from copy import deepcopy
from dataclasses import fields
from ..manifest.render_preparation import *
from ..manifest.render_preparation_validation import (require, bounded_value,
    preflight_history, validate_profile, validate_spec, project_plan, validate_plan,
    preflight_upstream_evidence)
from ..manifest.validation import require_valid
from ..manifest.semantic import exact_signature
from ..orchestrator.contracts import CancellationToken, Cancelled
from ..render_timeline.engine import callable_identity
from .models import RenderPreparationError, RenderPreparationAssessment

def normalize_dependencies(dependencies):
    try:
        require(not isinstance(dependencies, (str, bytes, dict)))
        iterator = iter(dependencies)
        values = []
        for _ in range(2):
            try:
                values.append(next(iterator))
            except StopIteration:
                break
        result = tuple(values)
        require(result in ((), ("render_timeline",)))
        return result
    except Exception:
        raise RenderPreparationError() from None

def preflight(manifest):
    from ..render_timeline.engine import preflight_for_expensive_operation
    preflight_history(getattr(manifest, "render_preparation", None))
    preflight_upstream_evidence(manifest)
    preflight_for_expensive_operation(manifest)

def active_plan(manifest):
    return next((p for p in manifest.render_preparation.plans if p.render_preparation_plan_id ==
        manifest.render_preparation.active_render_preparation_plan_id), None)

CONFIGURATION_KEYS = {"acquisition_spec", "edit_spec", "timing_spec", "timeline_spec",
    "acceptance_policy_id", "acceptance_policy_version", "voice_spec",
    "voice_acceptance_policy_id", "voice_acceptance_policy_version"}

def configuration_snapshot(profile, spec, configuration):
    require(type(configuration) is dict and len(configuration) <= len(CONFIGURATION_KEYS))
    require(set(configuration) <= CONFIGURATION_KEYS)
    validate_profile(profile)
    validate_spec(spec)
    # Upstream retained spec records are bounded by their own capacity contracts.
    from ..manifest.render_timeline_validation import bounded_value as upstream_bound
    upstream_bound(configuration)
    return exact_signature([profile, spec, configuration])

def _logical_upstream(manifest, configuration):
    """Pure M73 projection: no M72 combined eligibility or byte observations."""
    from ..placement_timing.engine import logical_inputs, active_plan as active_timing
    from ..render_timeline.engine import active_plan as active_timeline
    from ..manifest.acquisition import AcquisitionSpec
    from ..manifest.editing import EditSpec
    from ..manifest.placement_timing import PlacementTimingSpec
    from ..manifest.voice_timing import AlignmentSpec
    from ..manifest.render_timeline import RenderTimelineSpec
    edit, alignment, lineage = logical_inputs(manifest, CancellationToken())
    timing, timeline = active_timing(manifest), active_timeline(manifest)
    require(timing is not None and timeline is not None)
    acquisition = next(r for r in manifest.acquisition.runs if r.acquisition_id == lineage.acquisition_id)
    require(acquisition.acquisition_spec == configuration.get("acquisition_spec", AcquisitionSpec()))
    require(edit.edit_spec == configuration.get("edit_spec", EditSpec()))
    require(timing.spec == configuration.get("timing_spec", PlacementTimingSpec()))
    require(timeline.spec == configuration.get("timeline_spec", RenderTimelineSpec()))
    require(alignment.spec == configuration.get("voice_spec", AlignmentSpec()))
    require((timing.acceptance_policy_id, timing.acceptance_policy_version) == (
        configuration.get("acceptance_policy_id"), configuration.get("acceptance_policy_version")))
    require((alignment.receipt.acceptance_policy_id, alignment.receipt.acceptance_policy_version) == (
        configuration.get("voice_acceptance_policy_id"), configuration.get("voice_acceptance_policy_version")))
    require((timing.edit_plan_id, timing.edit_output_signature, timing.alignment_run_id,
        timing.narration_revision_id, timing.lineage) == (edit.edit_plan_id, edit.output_signature,
        alignment.alignment_run_id, alignment.narration_revision_id, lineage))
    require(timeline.placement_timing_plan_id == timing.placement_timing_plan_id)
    from ..manifest.render_timeline_validation import validate_plan as validate_timeline
    validate_timeline(manifest, timeline)
    return timeline

def current_logically_eligible(manifest, *, output_profile, spec, **configuration):
    preflight(manifest)
    configuration_snapshot(output_profile, spec, configuration)
    try:
        require_valid(manifest)
        timeline = _logical_upstream(manifest, configuration)
        plan = active_plan(manifest)
        require(plan is not None and plan.output_profile == output_profile and plan.spec == spec)
        require(plan.timeline_binding.render_timeline_plan_id == timeline.render_timeline_plan_id)
        validate_plan(manifest, plan)
        return True
    except (ValueError, TypeError, AttributeError, KeyError, StopIteration):
        return False

def boundary_unchanged(before, after):
    return all(getattr(before, f.name) == getattr(after, f.name)
        for f in fields(before) if f.name != "render_preparation")

class ObservationFence:
    """Transient guard around each actual injected callable; no identities persist.

    Guards detection, not rollback of arbitrary external collaborator side effects.
    """
    def __init__(self, manifest, output_profile, spec, configuration, collaborators=()):
        self.manifest, self.profile, self.spec = manifest, output_profile, spec
        self.configuration, self.collaborators = configuration, tuple(collaborators)

    def identities(self):
        from ..render_timeline import engine as timeline_engine
        from ..placement_timing import engine as placement_engine
        from ..voice_timing import engine as voice_engine, inspector as voice_inspector
        from ..acquisition import engine as acquisition_engine
        # Capture the actual delegated aliases, including aliases imported by an
        # upstream module, rather than just their original defining module.
        delegated = ((timeline_engine, "current_render_timeline_eligibility"),
            (timeline_engine, "observe_media_usability"),
            (timeline_engine, "current_placement_timing_eligibility"),
            (placement_engine, "current_timing_eligibility"),
            (voice_engine, "current_timing_eligibility"), (voice_engine, "verify_audio"),
            (voice_inspector, "verify_audio"), (voice_inspector, "inspect_stream"),
            (acquisition_engine, "current_usability"), (acquisition_engine, "inspect_media"))
        result = [tuple(callable_identity(getattr(module, name)) for module, name in delegated)]
        for collaborator in self.collaborators:
            if collaborator is None:
                result.append(None)
                continue
            methods = []
            for name in ("check", "open_read", "verify", "resolve", "hash_file", "_check", "inspect",
                    "read", "__enter__", "__exit__"):
                value = getattr(collaborator, name, None)
                methods.append((name, callable_identity(value)))
            declared = []
            for name in ("root", "inspector_id", "inspector_version", "policy_id", "policy_version"):
                value = getattr(collaborator, name, None)
                # root is a transient Path on ManagedStorage, never serialized.
                if name == "root":
                    from pathlib import Path
                    require(value is None or isinstance(value, Path) or type(value) is str)
                    if type(value) is str:
                        require(len(value) <= 32768)
                else:
                    require(value is None or type(value) is str and len(value) <= MAX_GENERAL_SCALAR)
                declared.append((name, value))
            paths = getattr(collaborator, "_paths", None)
            if paths is not None:
                from pathlib import Path
                require(type(paths) is dict and len(paths) <= 64)
                require(all(type(k) is str and len(k) <= 96 and isinstance(v, Path)
                    for k, v in paths.items()))
                declared.append(("paths", tuple(sorted(paths.items()))))
            result.append((id(collaborator), tuple(methods), tuple(declared)))
        return tuple(result)

    def capture(self):
        preflight(self.manifest)
        config = configuration_snapshot(self.profile, self.spec, self.configuration)
        return exact_signature(self.manifest), config, self.identities()

    def call(self, getter, *args, result_check=None, **kwargs):
        captured = self.capture()
        function = getter()
        identity = callable_identity(function)
        completed = False
        try:
            result = function(*args, **kwargs)
            completed = True
        finally:
            # Pure capacity fence must run even when a callback raises/cancels.
            preflight(self.manifest)
            require(callable_identity(getter()) == identity)
            require(self.identities() == captured[2])
            if completed and result_check is not None:
                result_check(result)
            require(configuration_snapshot(self.profile, self.spec, self.configuration) == captured[1])
            require(exact_signature(self.manifest) == captured[0])
        preflight(self.manifest)
        require(self.capture() == captured)
        return result

class _Control:
    def __init__(self, control, fence):
        self.control, self.fence = control, fence
    def check(self):
        self.fence.call(lambda: self.control.check, result_check=lambda r: require(r is None))

class _Storage:
    def __init__(self, storage, fence):
        self.storage, self.fence = storage, fence
        self.methods = {}
    def __getattr__(self, name):
        value = getattr(self.storage, name)
        if not callable(value):
            return value
        if name not in self.methods:
            def guarded(*args, **kwargs):
                def check_result(result):
                    if name == "inspect":
                        from ..manifest.acquisition import InspectionFacts
                        from ..manifest.render_timeline_validation import bounded_value as upstream_bound
                        require(type(result) is InspectionFacts)
                        upstream_bound(result)
                result = self.fence.call(lambda: getattr(self.storage, name), *args,
                    result_check=check_result, **kwargs)
                if name == "open_read":
                    return _ReadContext(result, self.fence)
                return result
            self.methods[name] = guarded
        return self.methods[name]

class _ReadContext:
    def __init__(self, context, fence):
        self.context, self.fence = context, fence
        self.enter_identity = callable_identity(context.__enter__)
        self.exit_identity = callable_identity(context.__exit__)
    def __enter__(self):
        require(callable_identity(self.context.__enter__) == self.enter_identity)
        stream = self.fence.call(lambda: self.context.__enter__)
        return _Reader(stream, self.fence)
    def __exit__(self, *args):
        require(callable_identity(self.context.__exit__) == self.exit_identity)
        return self.fence.call(lambda: self.context.__exit__, *args,
            result_check=lambda r: require(r is None or type(r) is bool))

class _Reader:
    def __init__(self, stream, fence):
        self.stream, self.fence = stream, fence
        self.identity = callable_identity(stream.read)
    def read(self, size):
        from ..manifest.voice_timing import READ_CHUNK
        require(type(size) is int and 0 <= size <= READ_CHUNK)
        require(callable_identity(self.stream.read) == self.identity)
        return self.fence.call(lambda: self.stream.read, size,
            result_check=lambda r: require(type(r) is bytes and len(r) <= size))

def _observation_result(result, cls):
    require(type(result) is cls)
    bounded_value(result)
    require(all(type(getattr(result, f.name)) is bool for f in fields(cls)))

def build_render_preparation(manifest, *, output_profile, spec, dependencies=(), control=None,
        **configuration):
    preflight(manifest)
    configuration_snapshot(output_profile, spec, configuration)
    control = control if control is not None else CancellationToken()
    fence = ObservationFence(manifest, output_profile, spec, configuration, (control,))
    guarded = _Control(control, fence)
    capture = fence.capture()
    dependencies = fence.call(lambda: normalize_dependencies, dependencies)
    guarded.check()
    require_valid(manifest)
    from .stage import RenderPreparationStage
    stage = RenderPreparationStage(output_profile=output_profile, spec=spec,
        dependencies=dependencies, **configuration)
    stage._upstream(manifest)
    timeline = _logical_upstream(manifest, configuration)
    plan = project_plan(manifest, timeline, output_profile, spec)
    current = active_plan(manifest)
    if current == plan:
        states = [s for s in manifest.processing if s.stage == stage.stage_id]
        require(len(states) == 1 and stage.validate_reuse(manifest, states[0].execution))
    else:
        state = manifest.render_preparation
        require(len(state.plans) < MAX_PLANS)
        require(sum(len(p.entries) for p in state.plans) + len(plan.entries) <= MAX_TOTAL_ENTRY_ASSESSMENTS)
        require(all(p.render_preparation_plan_id != plan.render_preparation_plan_id for p in state.plans))
    guarded.check()
    preflight(manifest)
    require(fence.capture() == capture)
    result = deepcopy(manifest)
    if current != plan:
        result.render_preparation.plans.append(deepcopy(plan))
        result.render_preparation.active_render_preparation_plan_id = plan.render_preparation_plan_id
    preflight(result)
    require_valid(result)
    require(boundary_unchanged(manifest, result))
    preflight(result)
    result_signature = exact_signature(result)
    guarded.check()
    preflight(manifest)
    preflight(result)
    require(fence.capture() == capture)
    require(exact_signature(result) == result_signature)
    return result

def assess_render_preparation(manifest, *, output_profile, spec, narration_storage,
        visual_storage, inspector=None, control=None, **configuration):
    """Visual usability is M68 aggregate relevant-media usability, not entry causes."""
    from ..render_timeline import engine as timeline_engine
    from ..voice_timing import engine as voice_engine
    from ..render_timeline.models import RenderTimelineEligibility
    from ..voice_timing.models import TimingEligibility
    preflight(manifest)
    configuration_snapshot(output_profile, spec, configuration)
    require_valid(manifest)
    control = control if control is not None else CancellationToken()
    fence = ObservationFence(manifest, output_profile, spec, configuration,
        (narration_storage, visual_storage, inspector, control))
    capture = fence.capture()
    guarded = _Control(control, fence)
    narration = _Storage(narration_storage, fence)
    visual = _Storage(visual_storage, fence)
    visual_inspector = _Storage(inspector, fence) if inspector is not None else None
    logical = current_logically_eligible(manifest, output_profile=output_profile, spec=spec, **configuration)
    timing_config = {k: v for k, v in configuration.items() if k != "timeline_spec"}
    eligibility = fence.call(lambda: timeline_engine.current_render_timeline_eligibility,
        manifest, storage=narration, spec=configuration.get("timeline_spec"),
        control=guarded, result_check=lambda r: _observation_result(r, RenderTimelineEligibility), **timing_config)
    voice = fence.call(lambda: voice_engine.current_timing_eligibility, manifest, storage=narration,
        spec=configuration.get("voice_spec"),
        acceptance_policy_id=configuration.get("voice_acceptance_policy_id"),
        acceptance_policy_version=configuration.get("voice_acceptance_policy_version"), control=guarded,
        result_check=lambda r: _observation_result(r, TimingEligibility))
    media = fence.call(lambda: timeline_engine.observe_media_usability, manifest,
        storage=visual, inspector=visual_inspector, acquisition_spec=configuration.get("acquisition_spec"),
        control=guarded, result_check=lambda r: require(type(r) is bool))
    plan = active_plan(manifest)
    deterministic = plan is not None and plan.conclusion == PreparationConclusion.PREPARATION_REQUIREMENTS_SATISFIED
    narration_usable = bool(plan is not None and voice.audio_usability and
        manifest.voice_timing.active_narration_revision_id == plan.narration_binding.narration_revision_id and
        manifest.voice_timing.active_alignment_run_id == plan.narration_binding.alignment_run_id)
    guarded.check()
    preflight(manifest)
    require(fence.capture() == capture)
    return RenderPreparationAssessment(logical, eligibility.eligible, narration_usable, media, deterministic)
