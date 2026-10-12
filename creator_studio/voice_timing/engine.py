"""M70 proposals change only voice_timing. No producer or automatic acceptance."""
from copy import deepcopy
from dataclasses import replace, fields
import json
from ..manifest.codec import to_data
from ..manifest.validation import require_valid
from ..manifest.semantic import exact_signature, generated_payload
from ..manifest.semantic_validation import eligible_active_document
from ..manifest.voice_timing import *
from ..manifest.voice_timing_validation import (validate_history, validate_output,
    validate_receipt, validate_spec, identifier, normalize, coverage, require,
    semantic_evidence, source_record_fingerprint, preflight_history)
from ..orchestrator.contracts import CancellationToken, Cancelled
from .inspector import verify_audio
from .models import (Observation, AcceptanceRequest, TimingEligibility, VoiceTimingError)

def boundary_unchanged(original, proposal):
    return all(getattr(original, f.name) == getattr(proposal, f.name)
               for f in fields(original) if f.name != "voice_timing")

def active_revision(manifest):
    return next((r for r in manifest.voice_timing.revisions
        if r.revision_id == manifest.voice_timing.active_narration_revision_id), None)

def active_run(manifest):
    return next((r for r in manifest.voice_timing.runs
        if r.alignment_run_id == manifest.voice_timing.active_alignment_run_id), None)

def semantic_binding(manifest):
    document = eligible_active_document(manifest)
    if document is None:
        raise VoiceTimingError("voice_timing_stale")
    source = next(s for s in manifest.semantic.source_revisions
                  if s.source_revision_id == document.source_revision_id)
    return (source.source_revision_id, source_record_fingerprint(source.content),
        document.semantic_document_id, exact_signature(generated_payload(document)),
        document.output_signature)

def source_binding(manifest, start_char, end_char, story_unit_id):
    """Explicit offsets only; never searches for a normalized-equal occurrence."""
    binding = semantic_binding(manifest)
    source = next(s for s in manifest.semantic.source_revisions if s.source_revision_id == binding[0])
    require(type(start_char) is int and type(end_char) is int and
            0 <= start_char < end_char <= len(source.content.normalized_text))
    return SourceBinding(binding[0], binding[2], story_unit_id, start_char, end_char,
        exact_signature(source.content.normalized_text[start_char:end_char]))

def register_narration(manifest, asset, *, storage, origin=NarrationOrigin.IMPORTED,
        logical_revision, provenance="UNSPECIFIED", predecessor_revision_id=None, control=None):
    """Append an explicit logical revision; no timing authority is created."""
    control = control or CancellationToken()
    try:
        control.check()
        preflight_history(manifest.voice_timing, control)
        require_valid(manifest)
        captured = exact_signature(manifest)
        asset = deepcopy(asset)
        inspection = verify_audio(storage, asset, control=control)
        revision = NarrationRevision("", asset.asset_id, origin, logical_revision,
                                     provenance, predecessor_revision_id)
        revision = replace(revision, revision_id=revision_id(revision))
        proposal = deepcopy(manifest)
        state = proposal.voice_timing
        retained = next((a for a in state.assets if a.asset_id == asset.asset_id), None)
        require(retained is None or retained == asset)
        if retained is None:
            state.assets.append(asset)
        require(all(r.revision_id != revision.revision_id for r in state.revisions))
        state.revisions.append(revision)
        state.active_narration_revision_id = revision.revision_id
        state.active_alignment_run_id = None
        validate_history(proposal, control)
        require_valid(proposal)
        control.check()
        verify_audio(storage, asset, expected_inspection=inspection, control=control)
        require(exact_signature(manifest) == captured and boundary_unchanged(manifest, proposal))
        control.check()
        return proposal
    except Cancelled:
        raise
    except VoiceTimingError:
        raise
    except Exception:
        raise VoiceTimingError() from None

def preflight_observations(observations, omissions, control=None):
    require(type(observations) in (list, tuple) and type(omissions) in (list, tuple))
    if control:
        control.check()
    require(len(observations) <= MAX_UNITS and len(omissions) <= MAX_ISSUES)
    bindings = issues = len(omissions)
    for i, observation in enumerate(observations):
        if control and i % 256 == 0:
            control.check()
        require(type(observation) is Observation and type(observation.source_bindings) is tuple)
        require(len(observation.source_bindings) <= 8)
        bindings += len(observation.source_bindings)
        issues += observation.mapping_status in (MappingStatus.MISMATCH,
            MappingStatus.UNMAPPED, MappingStatus.SPEECH_ADDED)
        require(bindings <= MAX_BINDINGS and issues <= MAX_ISSUES)


def observation_signature(observations, omissions, control=None):
    preflight_observations(observations, omissions, control)
    # Runtime tuple annotations are not supported by the unchanged manifest codec.
    # Convert explicitly, after bounded capture; never serialize a runtime repr.
    require(len(observations) <= MAX_UNITS and len(omissions) <= MAX_ISSUES)
    payload = []
    for o in observations:
        if control:
            control.check()
        require(type(o) is Observation and type(o.source_bindings) is tuple and len(o.source_bindings) <= 8)
        require(type(o.observed_text) is str and 0 < len(o.observed_text) <= 4096)
        payload.append([o.ordinal, o.start_us, o.end_us, o.observed_text, o.mapping_status,
            list(o.source_bindings), o.variant_evidence_signature, o.granularity])
    return signed("runtime_observations", [payload, list(omissions)])

def request_for(run, policy_id, policy_version):
    payload = json.dumps(to_data([run.units, run.omissions]), ensure_ascii=True,
        sort_keys=True, separators=(",", ":"), allow_nan=False)
    return AcceptanceRequest("1", run.request_signature, run.narration_revision_id,
        run.inspection.asset_id, run.inspection.sha256, run.inspection.byte_count,
        run.inspection, run.source_revision_id, run.source_record_fingerprint,
        run.semantic_document_id, run.semantic_generated_binding, run.semantic_output_binding,
        tuple(b for u in run.units for b in u.source_bindings) +
        tuple(o.source_binding for o in run.omissions), run.spec,
        signed("spec", run.spec), run.input_signature, run.output_signature,
        payload, policy_id, policy_version)

def build_voice_timing(manifest, *, storage, observations, gate=None, spec=None,
        acceptance_policy_id, acceptance_policy_version, omissions=(), control=None,
        authorization_recheck=None):
    control = control or CancellationToken()
    try:
        control.check()
        if gate is None:
            raise VoiceTimingError("voice_gate_required")
        preflight_history(manifest.voice_timing, control)
        require_valid(manifest)
        # Capture mutable runtime inputs before invoking external code.
        captured_manifest = exact_signature(manifest)
        spec = spec if spec is not None else AlignmentSpec()
        validate_spec(spec)
        identifier(acceptance_policy_id)
        identifier(acceptance_policy_version)
        require(type(observations) in (list, tuple) and type(omissions) in (list, tuple))
        preflight_observations(observations, omissions, control)
        captured_observations = observation_signature(observations, omissions, control)
        captured_spec = exact_signature(spec)
        source = semantic_binding(manifest)
        revision = active_revision(manifest)
        require(revision is not None)
        asset = next(a for a in manifest.voice_timing.assets if a.asset_id == revision.asset_id)
        def recheck():
            control.check()
            preflight_history(manifest.voice_timing, control)
            require(exact_signature(manifest) == captured_manifest)
            require(semantic_binding(manifest) == source and active_revision(manifest) == revision)
            require(exact_signature(spec) == captured_spec)
            require(observation_signature(observations, omissions, control) == captured_observations)
            if authorization_recheck is not None:
                authorization_recheck()

        inspection = verify_audio(storage, asset, control=control)
        empty_receipt = AcceptanceReceipt(acceptance_policy_id, acceptance_policy_version, "", "", "")
        run = AlignmentRun("", revision.revision_id, inspection, *source,
            deepcopy(spec), "", [], deepcopy(list(omissions)), "", "", empty_receipt)
        run = replace(run, input_signature=input_signature(run))
        units = []
        for observation in observations:
            control.check()
            require(observation.granularity == spec.granularity)
            if observation.mapping_status == MappingStatus.NORMALIZED_MATCH:
                require(bool(normalize(observation.observed_text)))
            unit = TimedUnit("", observation.ordinal, observation.start_us, observation.end_us,
                exact_signature(observation.observed_text), exact_signature(normalize(observation.observed_text)),
                observation.mapping_status, deepcopy(list(observation.source_bindings)),
                observation.variant_evidence_signature)
            units.append(replace(unit, unit_id=unit_id(run.input_signature, unit)))
        run = replace(run, units=units)
        run = replace(run, output_signature=output_signature(run))
        run = replace(run, request_signature=request_signature(run, acceptance_policy_id, acceptance_policy_version))
        validate_output(manifest, run, control)
        request = request_for(run, acceptance_policy_id, acceptance_policy_version)
        recheck()
        try:
            receipt = gate.accept(request)
        except Cancelled:
            raise
        except Exception:
            raise VoiceTimingError("voice_gate_failed") from None
        control.check()
        run = replace(run, receipt=deepcopy(receipt))
        try:
            validate_receipt(run)
        except Exception:
            raise VoiceTimingError("voice_receipt_invalid") from None
        run = replace(run, alignment_run_id=run_id(run))

        recheck()
        verify_audio(storage, asset, expected_inspection=inspection, control=control)
        proposal = deepcopy(manifest)
        # Identical accepted evidence is idempotent; never scans history for reuse.
        if all(r.alignment_run_id != run.alignment_run_id for r in proposal.voice_timing.runs):
            proposal.voice_timing.runs.append(run)
        else:
            require(active_run(proposal) == run)
        proposal.voice_timing.active_alignment_run_id = run.alignment_run_id
        validate_history(proposal, control)
        control.check()
        require_valid(proposal)
        require(boundary_unchanged(manifest, proposal))
        recheck()
        verify_audio(storage, asset, expected_inspection=inspection, control=control)
        recheck()
        return proposal
    except Cancelled:
        raise
    except VoiceTimingError:
        raise
    except Exception:
        raise VoiceTimingError() from None

def current_timing_eligibility(manifest, *, storage, spec=None,
        acceptance_policy_id, acceptance_policy_version, control=None):
    control = control or CancellationToken()
    control.check()
    preflight_history(manifest.voice_timing, control)
    captured_manifest = exact_signature(manifest)
    try:
        validate_history(manifest, control)
        historical = True
    except (ValueError, TypeError, AttributeError, StopIteration, KeyError):
        historical = False
    revision, run = active_revision(manifest), active_run(manifest)
    audio = semantic = complete = False
    if historical and revision is not None:
        asset = next(a for a in manifest.voice_timing.assets if a.asset_id == revision.asset_id)
        try:
            verify_audio(storage, asset, expected_inspection=run.inspection if run else None, control=control)
            audio = True
        except VoiceTimingError:
            pass
    if historical and run is not None:
        try:
            semantic = semantic_binding(manifest) == (run.source_revision_id,
                run.source_record_fingerprint, run.semantic_document_id,
                run.semantic_generated_binding, run.semantic_output_binding)
            text, _ = semantic_evidence(manifest, run)
            complete = coverage(run, text, control)
        except (ValueError, StopIteration):
            pass
    control.check()
    if exact_signature(manifest) != captured_manifest:
        raise VoiceTimingError("voice_timing_stale")
    return TimingEligibility(historical, audio, semantic,
        run is not None and run.spec == (spec if spec is not None else AlignmentSpec()),
        run is not None and (run.receipt.acceptance_policy_id, run.receipt.acceptance_policy_version) ==
            (acceptance_policy_id, acceptance_policy_version), revision is not None,
        run is not None and revision is not None and run.narration_revision_id == revision.revision_id, complete)
