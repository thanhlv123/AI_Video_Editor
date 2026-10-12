"""M62 adapter with exact reviewed artifacts and observation-only reuse."""
from copy import deepcopy
from ..manifest.selection import (SelectionSpec, SelectionSource, output_signature,
    effective_output_signature, exact_signature)
from ..manifest.selection_validation import eligible_active_selection, spec_valid
from ..manifest.retrieval import output_signature as retrieval_output
from ..manifest.signatures import dependency_signature, signature
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, Cancelled)
from .engine import build_selection, current_retrieval, automatic_projection, boundary_unchanged
from .models import SelectionError


class MediaSelectionStage:
    stage_id = "media_selection"
    stage_version = "1"

    def __init__(self, *, dependencies=(), spec=None, required_retrieval_spec=None,
                 required_visual_spec=None, required_semantic_spec=None):
        self.dependencies = tuple(dependencies)
        self.spec = deepcopy(spec) if spec is not None else SelectionSpec()
        self.required_retrieval_spec = deepcopy(required_retrieval_spec)
        self.required_visual_spec = deepcopy(required_visual_spec)
        self.required_semantic_spec = deepcopy(required_semantic_spec)

    def _inputs(self, manifest):
        if not spec_valid(self.spec):
            raise SelectionError("selection_spec_invalid")
        return current_retrieval(manifest, self.required_retrieval_spec,
                                 self.required_visual_spec, self.required_semantic_spec)

    def signature_inputs(self, manifest):
        try:
            retrieval = self._inputs(manifest)
            return dict(retrieval_id=retrieval.retrieval_id,
                retrieval_output_signature=retrieval_output(retrieval), selection_spec=self.spec,
                required_retrieval_spec=self.required_retrieval_spec or retrieval.retrieval_spec,
                required_visual_spec=self.required_visual_spec,
                required_semantic_spec=self.required_semantic_spec)
        except SelectionError as exc:
            return {"unavailable": exc.code}
        except Exception:
            return {"unavailable": "selection_contract_invalid"}

    def _diagnostics(self, code):
        return [Diagnostic(code=SelectionError(code).code, stage_id=self.stage_id,
                           message="Logical media selection requires attention.")]

    def readiness(self, manifest):
        try:
            self._inputs(manifest)
            return Readiness()
        except SelectionError as exc:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics(exc.code)))
        except Exception:
            return Readiness(ReadinessKind.NOT_READY,
                             tuple(self._diagnostics("selection_contract_invalid")))

    @staticmethod
    def artifacts(manifest, run, retrieval):
        return [Artifact("selection/" + run.selection_id,
            exact_signature([run.selection_id, output_signature(run),
                effective_output_signature(manifest.selection, run), run.selection_signature])),
            Artifact("selection_retrieval/" + retrieval.retrieval_id,
                exact_signature([retrieval.retrieval_id, retrieval_output(retrieval),
                    retrieval.retrieval_signature, retrieval.upstream_binding_signature]))]

    def validate_reuse(self, manifest, previous):
        try:
            retrieval = self._inputs(manifest)
            run = eligible_active_selection(manifest, self.spec, self.required_retrieval_spec,
                                            self.required_visual_spec, self.required_semantic_spec)
            states = [s for s in manifest.processing if s.stage == self.stage_id]
            if (run is None or len(states) != 1 or states[0].execution != previous
                    or states[0].dependency_signature != previous.dependency_signature
                    or previous.stage_id != self.stage_id or previous.stage_version != self.stage_version
                    or previous.status not in (StageStatus.SUCCEEDED, StageStatus.SKIPPED)
                    or not previous.dependency_signature
                    or previous.artifacts != self.artifacts(manifest, run, retrieval)
                    or any(s.source != SelectionSource.AUTOMATIC for s in run.shot_selections)):
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
            # Conservatively reuse only the reconstructible empty M62 configuration.
            if previous.dependency_signature != dependency_signature(
                    self.stage_id, self.stage_version,
                    {"inputs": self.signature_inputs(manifest), "configuration": {}}, upstream):
                return False
            return automatic_projection(manifest, retrieval, self.spec) == run
        except Exception:
            return False

    def execute(self, context):
        context.cancellation.check()
        try:
            proposed = build_selection(context.manifest, spec=self.spec,
                required_retrieval_spec=self.required_retrieval_spec,
                required_visual_spec=self.required_visual_spec,
                required_semantic_spec=self.required_semantic_spec, control=context.cancellation)
            retrieval = self._inputs(proposed)
            run = eligible_active_selection(proposed, self.spec, self.required_retrieval_spec,
                                            self.required_visual_spec, self.required_semantic_spec)
            if run is None or not boundary_unchanged(context.manifest, proposed):
                raise SelectionError("selection_boundary_invalid")
            artifacts = self.artifacts(proposed, run, retrieval)
            context.cancellation.check()
            outcome = StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                                               artifacts=artifacts), ManifestUpdate(proposed))
            context.cancellation.check()
            return outcome
        except Cancelled:
            raise
        except SelectionError as exc:
            code = exc.code
        except Exception:
            code = "selection_contract_invalid"
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                                       diagnostics=self._diagnostics(code)))
