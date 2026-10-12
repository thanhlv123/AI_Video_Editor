"""Standalone or acquisition-dependent M62 stage; exactly two ordered artifacts."""
from copy import deepcopy
from ..manifest.editing import EditSpec, exact_signature
from ..manifest.acquisition import AcquisitionSpec
from ..manifest.editing_validation import reconstruct
from ..manifest.signatures import dependency_signature, signature
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, Cancelled)
from .engine import (build_edit_plan, current_inputs, current_edit_eligibility,
    authorization, evidence, boundary_unchanged)
from .models import EditingError

class EditPlanningStage:
    stage_id = "edit_planning"
    stage_version = "1"

    def __init__(self, *, storage, inspector=None, acquisition_spec=None, spec=None, dependencies=()):
        normalized_dependencies = tuple(dependencies)
        if normalized_dependencies not in ((), ("media_acquisition",)):
            raise EditingError()
        self.dependencies = normalized_dependencies
        self.storage, self.inspector = storage, inspector
        self.acquisition_spec = deepcopy(acquisition_spec) if acquisition_spec is not None else AcquisitionSpec()
        self.spec = deepcopy(spec) if spec is not None else EditSpec()

    def signature_inputs(self, manifest):
        try:
            return {"authorization": authorization(manifest, self.acquisition_spec, self.spec)}
        except Exception:
            return {"unavailable": "editing_stale"}

    def _diagnostics(self, code):
        return [Diagnostic(code=EditingError(code).code, stage_id=self.stage_id,
                           message="Edit planning requires attention.")]

    def readiness(self, manifest):
        try:
            run = current_inputs(manifest, self.acquisition_spec)
            reconstruct(manifest, run, self.spec)
            return Readiness()
        except Exception:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics("editing_stale")))

    @staticmethod
    def artifacts(manifest, plan):
        run = next(r for r in manifest.acquisition.runs if r.acquisition_id == plan.acquisition_id)
        return [Artifact("edit/" + plan.edit_plan_id,
                    exact_signature([plan.edit_plan_id, plan.output_signature, plan.edit_signature])),
                Artifact("edit_acquisition/" + run.acquisition_id,
                    exact_signature([run.acquisition_id, run.output_signature,
                        run.selection_output_signature, run.effective_selection_output_signature,
                        evidence(manifest, run)]))]

    def _execution_binding(self, manifest):
        subjects = {self.stage_id, *self.dependencies}
        return exact_signature([self.dependencies, [s for s in manifest.processing if s.stage in subjects]])

    def validate_reuse(self, manifest, previous):
        try:
            captured = authorization(manifest, self.acquisition_spec, self.spec)
            captured_execution = exact_signature(previous)
            captured_states = self._execution_binding(manifest)
            run = current_inputs(manifest, self.acquisition_spec)
            expected = reconstruct(manifest, run, self.spec)
            plan = next(p for p in manifest.editing.plans
                        if p.edit_plan_id == manifest.editing.active_creator_edit_plan_id)
            states = [s for s in manifest.processing if s.stage == self.stage_id]
            if (plan != expected or len(states) != 1 or states[0].execution != previous
                    or states[0].dependency_signature != previous.dependency_signature
                    or previous.stage_id != self.stage_id or previous.stage_version != self.stage_version
                    or previous.status not in (StageStatus.SUCCEEDED, StageStatus.SKIPPED)
                    or previous.artifacts != self.artifacts(manifest, plan)):
                return False
            upstream = {}
            for dependency in self.dependencies:
                retained = [s for s in manifest.processing if s.stage == dependency]
                if (len(retained) != 1 or retained[0].execution is None
                        or retained[0].execution.status not in (StageStatus.SUCCEEDED, StageStatus.SKIPPED)):
                    return False
                execution = retained[0].execution
                upstream[dependency] = signature({"dependency_signature": execution.dependency_signature,
                    "artifacts": execution.artifacts, "metadata": execution.metadata})
            if previous.dependency_signature != dependency_signature(self.stage_id, self.stage_version,
                    {"inputs": self.signature_inputs(manifest), "configuration": {}}, upstream):
                return False
            current_edit_eligibility(manifest, storage=self.storage, inspector=self.inspector,
                acquisition_spec=self.acquisition_spec, spec=self.spec)
            return (authorization(manifest, self.acquisition_spec, self.spec) == captured
                    and self._execution_binding(manifest) == captured_states
                    and manifest.editing.active_creator_edit_plan_id == plan.edit_plan_id
                    and exact_signature(previous) == captured_execution
                    and states[0].execution == previous
                    and previous.artifacts == self.artifacts(manifest, plan))
        except Exception:
            return False

    def execute(self, context):
        control = context.cancellation
        control.check()
        try:
            captured = authorization(context.manifest, self.acquisition_spec, self.spec)
            proposal = build_edit_plan(context.manifest, storage=self.storage, inspector=self.inspector,
                acquisition_spec=self.acquisition_spec, spec=self.spec, control=control,
                dependencies=self.dependencies)
            plan = next(p for p in proposal.editing.plans
                        if p.edit_plan_id == proposal.editing.active_creator_edit_plan_id)
            result = StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                artifacts=self.artifacts(proposal, plan)), ManifestUpdate(proposal))
            control.check()
            if (authorization(context.manifest, self.acquisition_spec, self.spec) != captured
                    or not boundary_unchanged(context.manifest, proposal)):
                raise EditingError("editing_stale")
            return result
        except Cancelled:
            raise
        except EditingError as exc:
            code = exc.code
        except Exception:
            code = "editing_validation_failed"
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
            diagnostics=self._diagnostics(code)))
