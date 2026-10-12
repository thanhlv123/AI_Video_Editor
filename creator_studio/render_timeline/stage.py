"""M62 adapter with active-only reuse and exactly two ordered artifacts."""
from ..manifest.render_timeline import RenderTimelineSpec, signed
from ..manifest.render_timeline_validation import require, bounded_value
from ..manifest.semantic import exact_signature
from ..manifest.signatures import signature, dependency_signature
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, Cancelled)
from .engine import (preflight, normalize_dependencies, build_render_timeline,
    active_plan, active_timing, logical_inputs, current_render_timeline_eligibility,
    boundary_unchanged, CancellationToken)
from .engine import configuration_snapshot, _FencedControl, narration_storage_fence

class RenderTimelineStage:
    stage_id = "render_timeline"
    stage_version = "1"

    def __init__(self, *, spec=None, dependencies=(), **timing_configuration):
        self.dependencies = normalize_dependencies(dependencies)
        self.spec = spec or RenderTimelineSpec()
        self.timing_configuration = dict(timing_configuration)
        configuration_snapshot(self.spec, self.timing_configuration)
        self._declaration()

    def _declaration(self):
        configuration_snapshot(self.spec, self.timing_configuration)
        require(self.stage_id == "render_timeline" and self.stage_version == "1")
        require(type(self.dependencies) is tuple and self.dependencies in
            ((), ("media_acquisition", "edit_planning", "placement_timing")))
        bounded_value(self.spec)
        require(self.spec == RenderTimelineSpec())
        config = {k: v for k, v in self.timing_configuration.items() if k != "storage"}
        bounded_value(config)
        return signed("stage", [self.stage_id, self.stage_version, self.dependencies, self.spec, config])

    def signature_inputs(self, manifest):
        preflight(manifest)
        edit, _, _ = logical_inputs(manifest, CancellationToken())
        timing = active_timing(manifest)
        require(timing is not None)
        return {"binding": [edit.acquisition_id, edit.edit_plan_id, edit.output_signature,
            timing.placement_timing_plan_id, signed("timing_evidence", timing), self._declaration()]}

    def _eligibility(self, manifest, control=None):
        return current_render_timeline_eligibility(manifest, spec=self.spec, control=control,
            **self.timing_configuration)

    def readiness(self, manifest):
        try:
            self.signature_inputs(manifest)
            return Readiness()
        except Exception:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics()))

    def _diagnostics(self):
        return [Diagnostic(code="render_timeline_invalid", stage_id=self.stage_id,
            message="Render timeline requires attention.")]

    @staticmethod
    def artifacts(manifest, plan):
        return [Artifact("render_timeline/" + plan.render_timeline_plan_id,
            signed("plan_artifact", [plan.render_timeline_plan_id, plan.input_binding_signature,
                plan.source_usage_signature, plan.output_signature])),
            Artifact("render_timeline_timing/" + plan.placement_timing_plan_id,
            signed("timing_artifact", [plan.placement_timing_plan_id,
                plan.timing_evidence_signature, plan.media_binding_signature]))]

    def _execution_binding(self, manifest):
        return exact_signature([s for s in manifest.processing if s.stage in
            {self.stage_id, *self.dependencies}])

    def _capture(self, manifest):
        return (self._declaration(), narration_storage_fence(self.timing_configuration),
            self._execution_binding(manifest))

    def validate_reuse(self, manifest, previous):
        try:
            preflight(manifest)
            require(type(previous.artifacts) is list and len(previous.artifacts) == 2)
            configuration = configuration_snapshot(self.spec, self.timing_configuration)
            capture = (exact_signature(manifest), exact_signature(previous), self._capture(manifest))
            states = [s for s in manifest.processing if s.stage == self.stage_id]
            require(len(states) == 1 and states[0].execution == previous and
                states[0].dependency_signature == previous.dependency_signature)
            require(previous.stage_id == self.stage_id and previous.stage_version == self.stage_version and
                previous.status in (StageStatus.SUCCEEDED, StageStatus.SKIPPED))
            plan = active_plan(manifest)
            require(plan is not None and plan.spec == self.spec)
            require(previous.artifacts == self.artifacts(manifest, plan))
            upstream = {}
            for dependency in self.dependencies:
                retained = [s for s in manifest.processing if s.stage == dependency]
                require(len(retained) == 1 and retained[0].execution is not None)
                execution = retained[0].execution
                require(execution.status in (StageStatus.SUCCEEDED, StageStatus.SKIPPED))
                upstream[dependency] = signature({"dependency_signature": execution.dependency_signature,
                    "artifacts": execution.artifacts, "metadata": execution.metadata})
            require(previous.dependency_signature == dependency_signature(self.stage_id, self.stage_version,
                {"inputs": self.signature_inputs(manifest), "configuration": {}}, upstream))
            require(self._eligibility(manifest).eligible)
            require(configuration_snapshot(self.spec, self.timing_configuration) == configuration)
            preflight(manifest)
            return capture == (exact_signature(manifest), exact_signature(previous), self._capture(manifest))
        except Exception:
            return False

    def execute(self, context):
        control = _FencedControl(context.cancellation, context.manifest)
        control.check()
        try:
            preflight(context.manifest, control)
            configuration = configuration_snapshot(self.spec, self.timing_configuration)
            capture = (exact_signature(context.manifest), self._capture(context.manifest))
            proposal = build_render_timeline(context.manifest, spec=self.spec,
                dependencies=self.dependencies, control=control, **self.timing_configuration)
            require(configuration_snapshot(self.spec, self.timing_configuration) == configuration)
            preflight(context.manifest)
            preflight(proposal)
            proposal_signature = exact_signature(proposal)
            control.check()
            preflight(context.manifest, control)
            require(configuration_snapshot(self.spec, self.timing_configuration) == configuration)
            preflight(context.manifest)
            preflight(proposal)
            require(capture == (exact_signature(context.manifest), self._capture(context.manifest)))
            require(boundary_unchanged(context.manifest, proposal))
            result = StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                artifacts=self.artifacts(proposal, active_plan(proposal))), ManifestUpdate(proposal))
            control.check()
            require(configuration_snapshot(self.spec, self.timing_configuration) == configuration)
            preflight(context.manifest)
            preflight(proposal)
            require(capture == (exact_signature(context.manifest), self._capture(context.manifest)))
            require(exact_signature(proposal) == proposal_signature)
            return result
        except Cancelled:
            raise
        except Exception:
            return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                diagnostics=self._diagnostics()))
