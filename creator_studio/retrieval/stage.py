"""M62 integration with two exact artifacts and offline-only automatic reuse."""
from copy import deepcopy
from ..manifest.retrieval import (upstream_binding, upstream_payload, output_signature,
    exact_signature)
from ..manifest.retrieval_validation import eligible_active_retrieval, diagnostic_code
from ..manifest.visual import output_signature as visual_output_signature
from ..manifest.signatures import dependency_signature
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, Cancelled)
from .engine import build_retrieval, current_plan, effective_spec
from .models import RetrievalError
from .provider import OfflineEmptyProvider


class MediaRetrievalStage:
    stage_id = "media_retrieval"
    stage_version = "1"

    def __init__(self, *, dependencies=(), providers=None, spec=None,
                 required_visual_spec=None, required_semantic_spec=None):
        self.dependencies = tuple(dependencies)
        self.providers = (OfflineEmptyProvider(),) if providers is None else tuple(providers)
        self.spec = deepcopy(spec)
        self.required_visual_spec = deepcopy(required_visual_spec)
        self.required_semantic_spec = deepcopy(required_semantic_spec)

    def _inputs(self, manifest):
        plan = current_plan(manifest, self.required_visual_spec, self.required_semantic_spec)
        spec = effective_spec(self.providers, self.spec)
        return plan, spec

    def signature_inputs(self, manifest):
        try:
            plan, spec = self._inputs(manifest)
            canonical = next(r for r in manifest.content.records
                             if r.content_id == manifest.content.canonical_content_id)
            return dict(upstream_binding_signature=upstream_binding(manifest, plan),
                current_content_fingerprint=exact_signature(canonical),
                retrieval_spec=spec, required_visual_spec=self.required_visual_spec or plan.planning_spec,
                required_semantic_spec=self.required_semantic_spec)
        except RetrievalError as exc:
            return {"unavailable": diagnostic_code(exc.code)}
        except Exception:
            return {"unavailable": "retrieval_spec_invalid"}

    def _diagnostics(self, code):
        return [Diagnostic(code=diagnostic_code(code), stage_id=self.stage_id,
                           message="Media discovery requires attention.")]

    def readiness(self, manifest):
        try:
            self._inputs(manifest)
            return Readiness()
        except RetrievalError as exc:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics(exc.code)))
        except Exception:
            return Readiness(ReadinessKind.NOT_READY,
                             tuple(self._diagnostics("retrieval_spec_invalid")))

    @staticmethod
    def artifacts(manifest, run, plan):
        visual_binding = upstream_payload(manifest, plan)
        visual_binding[1] = visual_output_signature(plan)
        return [Artifact("retrieval/" + run.retrieval_id,
                    exact_signature([run.retrieval_id, output_signature(run),
                        run.retrieval_signature, run.upstream_binding_signature])),
                Artifact("retrieval_visual/" + plan.visual_plan_id,
                         exact_signature(visual_binding))]

    def validate_reuse(self, manifest, previous):
        try:
            plan, spec = self._inputs(manifest)
            states = [s for s in manifest.processing if s.stage == self.stage_id]
            if (len(states) != 1 or states[0].execution != previous
                    or states[0].dependency_signature != previous.dependency_signature
                    or previous.stage_id != self.stage_id or previous.stage_version != self.stage_version
                    or previous.status not in (StageStatus.SUCCEEDED, StageStatus.SKIPPED)
                    or not previous.dependency_signature):
                return False
            # M62 validates configuration/dependency signatures against the current run.
            # Standalone default configuration can additionally be recomputed here.
            if not self.dependencies:
                expected = dependency_signature(self.stage_id, self.stage_version,
                    {"inputs": self.signature_inputs(manifest), "configuration": {}}, {})
                # Nonempty orchestrator configuration is checked by M62, which owns it.
                # Exact retained execution still prevents caller substitution.
                if previous.dependency_signature != expected:
                    return False
            run = eligible_active_retrieval(manifest, spec, self.required_visual_spec,
                                             self.required_semantic_spec)
            if run is None or previous.artifacts != self.artifacts(manifest, run, plan):
                return False
            if not self.providers or any(type(p) is not OfflineEmptyProvider for p in self.providers):
                return False
            # Require production identities as well as production class, not a config hash.
            baseline = effective_spec((OfflineEmptyProvider(),), self.spec)
            if baseline != spec:
                return False
            fresh = deepcopy(manifest)
            fresh.retrieval.runs = []
            fresh.retrieval.active_creator_retrieval_id = None
            expected = build_retrieval(fresh, providers=(OfflineEmptyProvider(),), spec=self.spec,
                required_visual_spec=self.required_visual_spec,
                required_semantic_spec=self.required_semantic_spec).retrieval.runs[0]
            return expected == run
        except Exception:
            return False

    def execute(self, context):
        context.cancellation.check()
        try:
            proposed = build_retrieval(context.manifest, providers=self.providers, spec=self.spec,
                required_visual_spec=self.required_visual_spec,
                required_semantic_spec=self.required_semantic_spec, control=context.cancellation)
            plan, spec = self._inputs(proposed)
            run = eligible_active_retrieval(proposed, spec, self.required_visual_spec,
                                             self.required_semantic_spec)
            if run is None:
                raise RetrievalError("retrieval_output_stale")
            artifacts = self.artifacts(proposed, run, plan)
            context.cancellation.check()
            outcome = StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                artifacts=artifacts, diagnostics=self._diagnostics("retrieval_provider_partial")
                    if run.diagnostics else []), ManifestUpdate(proposed))
            context.cancellation.check()
            return outcome
        except Cancelled:
            raise
        except RetrievalError as exc:
            code = exc.code
        except Exception:
            code = "retrieval_candidate_invalid"
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                                       diagnostics=self._diagnostics(code)))
