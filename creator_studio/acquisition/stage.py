"""M62 integration: exact two artifacts and observation-only active reuse."""
from copy import deepcopy
from ..manifest.acquisition import AcquisitionSpec, exact_signature
from ..manifest.selection import output_signature as selection_output
from ..manifest.signatures import dependency_signature, signature
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, Cancelled)
from .engine import build_acquisition, current_inputs, current_usability, boundary_unchanged
from .inspector import UnavailableInspector
from .models import AcquisitionError


class MediaAcquisitionStage:
    stage_id = "media_acquisition"
    stage_version = "1"

    def __init__(self, *, storage, providers=(), inspector=None, spec=None, dependencies=()):
        if tuple(dependencies) not in ((), ("media_selection",)):
            raise AcquisitionError("acquisition_validation_failed")
        self.dependencies = tuple(dependencies)
        self.storage, self.providers = storage, tuple(providers)
        self.inspector = inspector or UnavailableInspector()
        self.spec = deepcopy(spec) if spec is not None else AcquisitionSpec()

    def signature_inputs(self, manifest):
        try:
            selection, _, _ = current_inputs(manifest, self.spec)
            from ..manifest.selection import effective_output_signature
            return {"selection_id": selection.selection_id,
                "selection_output_signature": selection_output(selection),
                "effective_selection_output_signature": effective_output_signature(manifest.selection, selection),
                "acquisition_spec": self.spec}
        except Exception:
            return {"unavailable": "acquisition_validation_failed"}

    def _diagnostics(self, code):
        return [Diagnostic(code=AcquisitionError(code).code, stage_id=self.stage_id,
                           message="Media acquisition requires attention.")]

    def readiness(self, manifest):
        try:
            current_inputs(manifest, self.spec)
            return Readiness()
        except Exception:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics("acquisition_validation_failed")))

    @staticmethod
    def artifacts(manifest, run, selection):
        records = {r.materialization_id: r for r in manifest.acquisition.materializations}
        assets = {a.asset_id: a for a in manifest.acquisition.assets}
        evidence = [[records[s.materialization_id], assets[records[s.materialization_id].asset_id]]
                    for s in run.shot_acquisitions if s.materialization_id]
        return [Artifact("acquisition/" + run.acquisition_id,
            exact_signature([run.acquisition_id, run.output_signature, run.acquisition_signature, evidence])),
            Artifact("acquisition_selection/" + selection.selection_id,
                exact_signature([selection.selection_id, selection_output(selection),
                    run.effective_selection_output_signature, selection.selection_signature]))]

    def validate_reuse(self, manifest, previous):
        try:
            selection, _, _ = current_inputs(manifest, self.spec)
            states = [s for s in manifest.processing if s.stage == self.stage_id]
            run = next(r for r in manifest.acquisition.runs
                       if r.acquisition_id == manifest.acquisition.active_creator_acquisition_id)
            if (len(states) != 1 or states[0].execution != previous
                    or states[0].dependency_signature != previous.dependency_signature
                    or previous.stage_id != self.stage_id or previous.stage_version != self.stage_version
                    or previous.status not in (StageStatus.SUCCEEDED, StageStatus.SKIPPED)
                    or previous.artifacts != self.artifacts(manifest, run, selection)):
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
            return current_usability(manifest, storage=self.storage, inspector=self.inspector, spec=self.spec)
        except Exception:
            return False

    def execute(self, context):
        context.cancellation.check()
        try:
            proposal = build_acquisition(context.manifest, storage=self.storage, providers=self.providers,
                inspector=self.inspector, spec=self.spec, control=context.cancellation)
            selection, _, _ = current_inputs(proposal, self.spec)
            run = next(r for r in proposal.acquisition.runs
                       if r.acquisition_id == proposal.acquisition.active_creator_acquisition_id)
            if not boundary_unchanged(context.manifest, proposal):
                raise AcquisitionError("acquisition_boundary_invalid")
            result = StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                artifacts=self.artifacts(proposal, run, selection)), ManifestUpdate(proposal))
            context.cancellation.check()
            return result
        except Cancelled:
            raise
        except AcquisitionError as exc:
            code = AcquisitionError(exc.code).code
        except Exception:
            code = "acquisition_validation_failed"
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                                       diagnostics=self._diagnostics(code)))
