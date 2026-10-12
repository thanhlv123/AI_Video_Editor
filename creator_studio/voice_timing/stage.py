"""M62-compatible explicit registration, active-only reuse, two ordered artifacts."""
from dataclasses import replace
from ..manifest.voice_timing import (AlignmentSpec, TimedUnit, exact_signature,
    unit_id, signed)
from ..manifest.voice_timing_validation import normalize, require, validate_spec, identifier, preflight_history
from ..manifest.signatures import dependency_signature, signature
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, Cancelled)
from .engine import (build_voice_timing, current_timing_eligibility, active_revision,
    active_run, semantic_binding, observation_signature)
from .models import VoiceTimingError

class VoiceTimingStage:
    stage_id = "voice_timing"
    stage_version = "1"

    def __init__(self, *, storage, observations, gate=None, spec=None,
            acceptance_policy_id, acceptance_policy_version, omissions=(), dependencies=()):
        normalized_dependencies = tuple(dependencies)
        if normalized_dependencies not in ((), ("semantic_story",)):
            raise VoiceTimingError()
        self.dependencies = normalized_dependencies
        self.storage, self.observations, self.gate = storage, observations, gate
        self.spec = spec if spec is not None else AlignmentSpec()
        self.acceptance_policy_id = acceptance_policy_id
        self.acceptance_policy_version = acceptance_policy_version
        self.omissions = omissions
        self._declaration()

    def _declaration(self):
        require(type(self.dependencies) is tuple and self.dependencies in ((), ("semantic_story",)))
        validate_spec(self.spec)
        identifier(self.acceptance_policy_id)
        identifier(self.acceptance_policy_version)
        return exact_signature([self.stage_id, self.stage_version, list(self.dependencies),
            self.spec, self.acceptance_policy_id, self.acceptance_policy_version,
            observation_signature(self.observations, self.omissions)])

    def signature_inputs(self, manifest):
        try:
            revision = active_revision(manifest)
            require(revision is not None)
            return {"binding": [revision, semantic_binding(manifest), self._declaration()]}
        except Exception:
            return {"unavailable": "voice_timing_stale"}

    def readiness(self, manifest):
        try:
            self._declaration()
            require(self.gate is not None and active_revision(manifest) is not None)
            semantic_binding(manifest)
            return Readiness()
        except Exception:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics("voice_timing_stale")))

    def _diagnostics(self, code):
        return [Diagnostic(code=VoiceTimingError(code).code, stage_id=self.stage_id,
            message="Voice timing requires attention.")]

    @staticmethod
    def artifacts(manifest, run):
        revision = next(r for r in manifest.voice_timing.revisions if r.revision_id == run.narration_revision_id)
        return [Artifact("voice_timing/" + run.alignment_run_id,
            signed("timing_artifact", [run.alignment_run_id, run.output_signature, run.request_signature, run.receipt])),
            Artifact("voice_source/" + revision.revision_id,
            signed("source_artifact", [revision, run.inspection]))]

    def _execution_binding(self, manifest):
        subjects = {self.stage_id, *self.dependencies}
        return exact_signature([s for s in manifest.processing if s.stage in subjects])

    def _observations_match(self, run):
        if len(self.observations) != len(run.units) or list(self.omissions) != run.omissions:
            return False
        for o, u in zip(self.observations, run.units):
            expected = TimedUnit("", o.ordinal, o.start_us, o.end_us,
                exact_signature(o.observed_text), exact_signature(normalize(o.observed_text)),
                o.mapping_status, list(o.source_bindings), o.variant_evidence_signature)
            expected = replace(expected, unit_id=unit_id(run.input_signature, expected))
            if expected != u or o.granularity != run.spec.granularity:
                return False
        return True

    def validate_reuse(self, manifest, previous):
        try:
            preflight_history(manifest.voice_timing)
            captured = exact_signature(manifest)
            declaration = exact_signature(self._declaration())
            captured_previous = exact_signature(previous)
            require(self.gate is not None)
            run = active_run(manifest)
            require(run is not None and self._observations_match(run))
            states = [s for s in manifest.processing if s.stage == self.stage_id]
            require(len(states) == 1 and states[0].execution == previous and
                states[0].dependency_signature == previous.dependency_signature)
            require(previous.stage_id == self.stage_id and previous.stage_version == self.stage_version and
                previous.status in (StageStatus.SUCCEEDED, StageStatus.SKIPPED))
            require(previous.artifacts == self.artifacts(manifest, run))
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
            require(current_timing_eligibility(manifest, storage=self.storage, spec=self.spec,
                acceptance_policy_id=self.acceptance_policy_id,
                acceptance_policy_version=self.acceptance_policy_version).eligible)
            return (exact_signature(manifest) == captured and exact_signature(previous) == captured_previous
                and exact_signature(self._declaration()) == declaration)
        except Exception:
            return False

    def execute(self, context):
        control = context.cancellation
        control.check()
        try:
            # Only scalar signatures/identities are retained: no mutable aliases.
            declaration = (self._declaration(), self._execution_binding(context.manifest),
                id(self.storage), id(self.gate))
            def recheck_declaration():
                require((self._declaration(), self._execution_binding(context.manifest),
                    id(self.storage), id(self.gate)) == declaration)

            captured = exact_signature(self.signature_inputs(context.manifest))
            proposal = build_voice_timing(context.manifest, storage=self.storage,
                observations=self.observations, omissions=self.omissions, gate=self.gate,
                spec=self.spec, acceptance_policy_id=self.acceptance_policy_id,
                acceptance_policy_version=self.acceptance_policy_version, control=control,
                authorization_recheck=recheck_declaration)
            control.check()
            recheck_declaration()
            require(exact_signature(self.signature_inputs(context.manifest)) == captured)
            run = active_run(proposal)
            outcome = StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                artifacts=self.artifacts(proposal, run)), ManifestUpdate(proposal))
            recheck_declaration()
            return outcome
        except Cancelled:
            raise
        except VoiceTimingError as exc:
            code = exc.code
        except Exception:
            code = "voice_timing_invalid"
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
            diagnostics=self._diagnostics(code)))
