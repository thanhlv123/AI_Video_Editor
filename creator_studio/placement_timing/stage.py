"""M62 stage adapter with captured declarations and exact ordered artifacts."""
from ..manifest.placement_timing import PlacementTimingSpec, signed, exact_signature
from ..manifest.placement_timing_validation import require, identifier, preflight_record
from ..manifest.signatures import dependency_signature, signature
from ..manifest.validation import require_valid
from ..manifest.voice_timing import AlignmentSpec
from ..manifest.voice_timing_validation import validate_spec as validate_voice_spec
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, CancellationToken, Cancelled)
from .models import PlacementTimingError
from .engine import (preflight, preflight_declarations, build_placement_timing,
    current_placement_timing_eligibility, active_plan, logical_inputs, boundary_unchanged,
    normalize_dependencies)

class PlacementTimingStage:
    stage_id = "placement_timing"
    stage_version = "1"

    def __init__(self, *, storage, allocations=(), explicit_boundaries=(), gate=None,
            spec=None, acceptance_policy_id, acceptance_policy_version, voice_spec=None,
            voice_acceptance_policy_id, voice_acceptance_policy_version, dependencies=()):
        normalized_dependencies = normalize_dependencies(dependencies)
        self.dependencies = normalized_dependencies
        self.storage, self.gate = storage, gate
        self.allocations, self.explicit_boundaries = allocations, explicit_boundaries
        self.spec = spec if spec is not None else PlacementTimingSpec()
        self.acceptance_policy_id = acceptance_policy_id
        self.acceptance_policy_version = acceptance_policy_version
        self.voice_spec = voice_spec
        self.voice_acceptance_policy_id = voice_acceptance_policy_id
        self.voice_acceptance_policy_version = voice_acceptance_policy_version
        self._declaration()

    def _declaration(self):
        require(self.stage_id == "placement_timing" and self.stage_version == "1")
        require(type(self.dependencies) is tuple and
            self.dependencies in ((), ("edit_planning", "voice_timing")))
        preflight_declarations(self.allocations, self.explicit_boundaries, CancellationToken())
        for declarations in (self.allocations, self.explicit_boundaries):
            for declaration in declarations:
                preflight_record(declaration, type(declaration))
        preflight_record(self.spec, PlacementTimingSpec)
        require(self.spec == PlacementTimingSpec())
        validate_voice_spec(self.voice_spec if self.voice_spec is not None else AlignmentSpec())
        for value in (self.acceptance_policy_id, self.acceptance_policy_version,
                self.voice_acceptance_policy_id, self.voice_acceptance_policy_version):
            identifier(value)
        return signed("stage", [self.stage_id, self.stage_version, list(self.dependencies),
            self.spec, [signed("allocation_configuration", a) for a in self.allocations],
            [signed("boundary_configuration", b) for b in self.explicit_boundaries],
            self.acceptance_policy_id, self.acceptance_policy_version, self.voice_spec,
            self.voice_acceptance_policy_id, self.voice_acceptance_policy_version])

    def signature_inputs(self, manifest):
        preflight(manifest)
        edit, alignment, lineage = logical_inputs(manifest, CancellationToken())
        return {"binding": [edit.edit_plan_id, edit.output_signature,
            [p.placement_id for p in edit.placements], alignment.alignment_run_id,
            alignment.output_signature, alignment.request_signature, alignment.receipt,
            alignment.narration_revision_id, lineage, self._declaration()]}

    def _eligibility(self, manifest, control=None):
        return current_placement_timing_eligibility(manifest, storage=self.storage,
            spec=self.spec, acceptance_policy_id=self.acceptance_policy_id,
            acceptance_policy_version=self.acceptance_policy_version, voice_spec=self.voice_spec,
            voice_acceptance_policy_id=self.voice_acceptance_policy_id,
            voice_acceptance_policy_version=self.voice_acceptance_policy_version, control=control)

    def readiness(self, manifest):
        try:
            self.signature_inputs(manifest)
            require(not (self.allocations or self.explicit_boundaries) or self.gate is not None)
            return Readiness()
        except Exception:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics()))

    def _diagnostics(self, code="placement_timing_invalid"):
        return [Diagnostic(code=PlacementTimingError(code).code, stage_id=self.stage_id,
            message="Placement timing requires attention.")]

    @staticmethod
    def artifacts(manifest, plan):
        return [Artifact("placement_timing/" + plan.placement_timing_plan_id,
            signed("plan_artifact", [plan.placement_timing_plan_id, plan.input_signature,
                plan.output_signature, plan.declaration_signature, plan.request_signature, plan.receipt])),
            Artifact("placement_timing_edit/" + plan.edit_plan_id,
            signed("edit_artifact", [plan.edit_plan_id, plan.edit_output_signature, plan.placement_ids,
                plan.alignment_run_id, plan.narration_revision_id, plan.lineage]))]

    def _execution_binding(self, manifest):
        return exact_signature([s for s in manifest.processing
            if s.stage in {self.stage_id, *self.dependencies}])

    def validate_reuse(self, manifest, previous):
        try:
            preflight(manifest)
            artifacts = getattr(previous, "artifacts", None)
            require(type(artifacts) is list and len(artifacts) == 2)
            states = [s for s in manifest.processing if s.stage == self.stage_id]
            require(len(states) == 1 and states[0].execution == previous)
            captured = exact_signature(manifest)
            declaration = self._declaration()
            captured_previous = exact_signature(previous)
            plan = active_plan(manifest)
            require(plan is not None and plan.spec == self.spec and
                plan.allocations == list(self.allocations) and
                plan.explicit_boundaries == list(self.explicit_boundaries))
            states = [s for s in manifest.processing if s.stage == self.stage_id]
            require(len(states) == 1 and states[0].execution == previous and
                states[0].dependency_signature == previous.dependency_signature)
            require(previous.stage_id == self.stage_id and previous.stage_version == self.stage_version and
                previous.status in (StageStatus.SUCCEEDED, StageStatus.SKIPPED))
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
            preflight(manifest)
            return exact_signature(manifest) == captured and exact_signature(previous) == captured_previous and self._declaration() == declaration
        except Exception:
            return False

    def execute(self, context):
        control = context.cancellation
        control.check()
        try:
            preflight(context.manifest, control)
            captured_manifest = exact_signature(context.manifest)
            declaration = (self._declaration(), self._execution_binding(context.manifest),
                id(self.storage), id(self.gate))
            def recheck_declaration():
                control.check()
                preflight(context.manifest, control)
                require((self._declaration(), self._execution_binding(context.manifest),
                    id(self.storage), id(self.gate)) == declaration)
            proposal = build_placement_timing(context.manifest, storage=self.storage,
                allocations=self.allocations, explicit_boundaries=self.explicit_boundaries,
                gate=self.gate, spec=self.spec, acceptance_policy_id=self.acceptance_policy_id,
                acceptance_policy_version=self.acceptance_policy_version, voice_spec=self.voice_spec,
                voice_acceptance_policy_id=self.voice_acceptance_policy_id,
                voice_acceptance_policy_version=self.voice_acceptance_policy_version,
                dependencies=self.dependencies, control=control, authorization_recheck=recheck_declaration)
            preflight(proposal)
            captured_proposal = exact_signature(proposal)
            require_valid(proposal)
            require(boundary_unchanged(context.manifest, proposal))
            recheck_declaration()
            plan = active_plan(proposal)
            result = StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                artifacts=self.artifacts(proposal, plan)), ManifestUpdate(proposal))
            recheck_declaration()
            control.check()
            preflight(context.manifest)
            require(exact_signature(context.manifest) == captured_manifest)
            require((self._declaration(), self._execution_binding(context.manifest),
                id(self.storage), id(self.gate)) == declaration)
            preflight(proposal)
            require(exact_signature(proposal) == captured_proposal)
            return result
        except Cancelled:
            raise
        except PlacementTimingError as exc:
            code = exc.code
        except Exception:
            code = "placement_timing_invalid"
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
            diagnostics=self._diagnostics(code)))
