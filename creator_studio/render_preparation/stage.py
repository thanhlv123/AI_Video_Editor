"""M62 stage adapter; logical preparation artifacts only."""
from ..manifest.render_preparation import signed, ARTIFACT_COUNT
from ..manifest.render_preparation_validation import require
from ..manifest.semantic import exact_signature
from ..manifest.signatures import signature, dependency_signature
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, Cancelled)
from .engine import (preflight, normalize_dependencies, build_render_preparation,
    current_logically_eligible, active_plan, _logical_upstream, configuration_snapshot,
    ObservationFence, _Control, boundary_unchanged)

class RenderPreparationStage:
    stage_id = "render_preparation"
    stage_version = "1"

    def __init__(self, *, output_profile, spec, dependencies=(), **configuration):
        configuration_snapshot(output_profile, spec, configuration)
        self.output_profile, self.spec = output_profile, spec
        self.dependencies = normalize_dependencies(dependencies)
        self.configuration = dict(configuration)
        self._declaration()

    def _declaration(self):
        require(self.stage_id == "render_preparation" and self.stage_version == "1")
        require(type(self.dependencies) is tuple and self.dependencies in ((), ("render_timeline",)))
        config = configuration_snapshot(self.output_profile, self.spec, self.configuration)
        return signed("stage", [self.stage_id, self.stage_version, self.dependencies, config])

    def signature_inputs(self, manifest):
        preflight(manifest)
        timeline = _logical_upstream(manifest, self.configuration)
        return {"binding": [timeline.render_timeline_plan_id, timeline.input_binding_signature,
            timeline.source_usage_signature, timeline.output_signature, self._declaration()]}

    def readiness(self, manifest):
        try:
            self.signature_inputs(manifest)
            return Readiness()
        except Exception:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics()))

    def _diagnostics(self):
        return [Diagnostic(code="render_preparation_invalid", stage_id=self.stage_id,
            message="Render preparation requires attention.")]

    @staticmethod
    def artifacts(manifest, plan):
        preflight(manifest)
        return [Artifact("render_preparation/" + plan.render_preparation_plan_id,
            signed("plan_artifact", [plan.input_binding_signature, plan.output_profile_signature,
                plan.render_policy_signature, plan.preparation_signature, plan.output_signature,
                plan.render_preparation_plan_id])),
            Artifact("render_preparation_timeline/" + plan.timeline_binding.render_timeline_plan_id,
                signed("timeline_artifact", [plan.timeline_binding, plan.narration_binding]))]

    def _upstream(self, manifest):
        result = {}
        for dependency in self.dependencies:
            states = [s for s in manifest.processing if s.stage == dependency]
            require(len(states) == 1 and states[0].execution is not None)
            execution = states[0].execution
            require(execution.stage_id == dependency and execution.stage_version == "1" and
                execution.status in (StageStatus.SUCCEEDED, StageStatus.SKIPPED))
            # Exact active M72 artifacts and M62 dependency evidence must agree.
            from ..render_timeline.stage import RenderTimelineStage
            timeline = _logical_upstream(manifest, self.configuration)
            require(execution.artifacts == RenderTimelineStage.artifacts(manifest, timeline))
            require(states[0].dependency_signature == execution.dependency_signature)
            matches = False
            for dependencies in ((), ("media_acquisition", "edit_planning", "placement_timing")):
                config = {k: v for k, v in self.configuration.items() if k != "timeline_spec"}
                stage = RenderTimelineStage(spec=timeline.spec, dependencies=dependencies, **config)
                upstream = {}
                for name in dependencies:
                    retained = [s for s in manifest.processing if s.stage == name]
                    if len(retained) != 1 or retained[0].execution is None:
                        break
                    record = retained[0].execution
                    require(record.status in (StageStatus.SUCCEEDED, StageStatus.SKIPPED))
                    upstream[name] = signature({"dependency_signature": record.dependency_signature,
                        "artifacts": record.artifacts, "metadata": record.metadata})
                if len(upstream) != len(dependencies):
                    continue
                expected = dependency_signature(stage.stage_id, stage.stage_version,
                    {"inputs": stage.signature_inputs(manifest), "configuration": {}}, upstream)
                matches = matches or execution.dependency_signature == expected
            require(matches)
            result[dependency] = signature({"dependency_signature": execution.dependency_signature,
                "artifacts": execution.artifacts, "metadata": execution.metadata})
        return result

    def validate_reuse(self, manifest, previous):
        try:
            preflight(manifest)
            declaration = self._declaration()
            require(previous is not None and type(previous.artifacts) is list and
                len(previous.artifacts) == ARTIFACT_COUNT)
            states = [s for s in manifest.processing if s.stage == self.stage_id]
            require(len(states) == 1 and states[0].execution == previous and
                states[0].dependency_signature == previous.dependency_signature)
            require(previous.stage_id == self.stage_id and previous.stage_version == self.stage_version and
                previous.status in (StageStatus.SUCCEEDED, StageStatus.SKIPPED))
            plan = active_plan(manifest)
            require(plan is not None and previous.artifacts == self.artifacts(manifest, plan))
            require(previous.dependency_signature == dependency_signature(self.stage_id, self.stage_version,
                {"inputs": self.signature_inputs(manifest), "configuration": {}}, self._upstream(manifest)))
            require(current_logically_eligible(manifest, output_profile=self.output_profile,
                spec=self.spec, **self.configuration))
            preflight(manifest)
            require(declaration == self._declaration())
            return True
        except Exception:
            return False

    def execute(self, context):
        try:
            preflight(context.manifest)
            declaration = self._declaration()
            fence = ObservationFence(context.manifest, self.output_profile, self.spec,
                self.configuration, (context.cancellation,))
            capture = fence.capture()
            control = _Control(context.cancellation, fence)
            control.check()
            self._upstream(context.manifest)
            proposal = build_render_preparation(context.manifest, output_profile=self.output_profile,
                spec=self.spec, dependencies=self.dependencies, control=control, **self.configuration)
            preflight(proposal)
            proposal_signature = exact_signature(proposal)
            result = StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                artifacts=self.artifacts(proposal, active_plan(proposal))), ManifestUpdate(proposal))
            control.check()
            preflight(context.manifest)
            preflight(proposal)
            require(fence.capture() == capture and self._declaration() == declaration)
            require(exact_signature(proposal) == proposal_signature)
            require(boundary_unchanged(context.manifest, proposal))
            return result
        except Cancelled:
            raise
        except Exception:
            return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                diagnostics=self._diagnostics()))
