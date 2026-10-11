"""Configurable M62 stage with exact source binding and conservative reuse."""
from copy import deepcopy
from ..manifest.semantic import exact_signature
from ..manifest.visual import (Purpose, semantic_input_fingerprint, generated_payload,
                               output_signature)
from ..manifest.visual_validation import eligible_active_plan
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, Cancelled)
from .planner import OfflineStructuralPlanner
from .engine import current_document, effective_spec, build_visual_plan, VisualError


def source_binding(manifest, document):
    source = next(s for s in manifest.semantic.source_revisions
                  if s.source_revision_id == document.source_revision_id)
    return exact_signature(source.content)


class VisualDirectorStage:
    stage_id = "visual_director"
    stage_version = "1"

    def __init__(self, *, dependencies=(), planner=None, options=None,
                 required_semantic_spec=None):
        self.dependencies = tuple(dependencies)
        self.planner = planner or OfflineStructuralPlanner()
        self.options = deepcopy(options)
        self.required_semantic_spec = deepcopy(required_semantic_spec)

    def signature_inputs(self, manifest):
        try:
            d = current_document(manifest, self.required_semantic_spec)
            return {"semantic_input_fingerprint": semantic_input_fingerprint(d),
                    "semantic_source_binding": source_binding(manifest, d),
                    "planning_spec": effective_spec(self.planner, self.options),
                    "required_semantic_spec": self.required_semantic_spec or d.analysis_spec,
                    "purpose": Purpose.CREATOR_STORY}
        except VisualError as exc:
            return {"unavailable": exc.code}

    def _diagnostics(self, code):
        return [Diagnostic(code=code, stage_id=self.stage_id,
                           message="Visual planning requires attention.")]

    def readiness(self, manifest):
        try:
            current_document(manifest, self.required_semantic_spec)
            effective_spec(self.planner, self.options)
            return Readiness()
        except VisualError as exc:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics(exc.code)))
        except Exception:
            return Readiness(ReadinessKind.NOT_READY,
                             tuple(self._diagnostics("visual_spec_invalid")))

    @staticmethod
    def artifacts(manifest, plan, document):
        binding = source_binding(manifest, document)
        return [Artifact("visual/" + plan.visual_plan_id,
                    exact_signature([plan.visual_plan_id, output_signature(plan),
                        plan.planning_signature, plan.semantic_input_fingerprint, binding])),
                Artifact("visual_semantic/" + document.semantic_document_id,
                    exact_signature([document.semantic_document_id, document.output_signature,
                        document.analysis_signature, document.content_revision_signature,
                        [u.story_unit_id for u in document.story_units],
                        document.source_revision_id, binding])),
                Artifact("semantic_source/" + document.source_revision_id, binding)]

    def validate_reuse(self, manifest, previous):
        """M62 first checks the current dependency/configuration signature.

        Also require the exact retained execution here; callers cannot substitute
        a different dependency signature or execution identity into this hook.
        """
        try:
            d = current_document(manifest, self.required_semantic_spec)
            records = [s for s in manifest.processing if s.stage == self.stage_id]
            if (len(records) != 1 or records[0].execution != previous
                    or records[0].dependency_signature != previous.dependency_signature
                    or previous.stage_id != self.stage_id
                    or previous.stage_version != self.stage_version
                    or previous.status not in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
                    or not previous.dependency_signature):
                return False
            spec = effective_spec(self.planner, self.options)
            p = eligible_active_plan(manifest, spec, self.required_semantic_spec)
            if p is None or previous.artifacts != self.artifacts(manifest, p, d):
                return False
            if type(self.planner) is not OfflineStructuralPlanner:
                return False
            fresh = deepcopy(manifest)
            fresh.visual_planning.plans = []
            fresh.visual_planning.active_creator_plan_id = None
            expected = build_visual_plan(fresh, planner=self.planner, options=self.options,
                                        required_semantic_spec=self.required_semantic_spec)
            return generated_payload(expected.visual_planning.plans[0]) == generated_payload(p)
        except Exception:
            return False

    def execute(self, context):
        context.cancellation.check()
        try:
            proposed = build_visual_plan(context.manifest, planner=self.planner,
                options=self.options, required_semantic_spec=self.required_semantic_spec,
                control=context.cancellation)
            d = current_document(proposed, self.required_semantic_spec)
            p = eligible_active_plan(proposed, effective_spec(self.planner, self.options),
                                     self.required_semantic_spec)
            if p is None:
                raise VisualError("visual_output_stale")
            artifacts = self.artifacts(proposed, p, d)
            context.cancellation.check()
        except Cancelled:
            raise
        except VisualError as exc:
            return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                                            diagnostics=self._diagnostics(exc.code)))
        except Exception:
            return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                                diagnostics=self._diagnostics("visual_plan_invalid")))
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                            artifacts=artifacts), ManifestUpdate(proposed))
