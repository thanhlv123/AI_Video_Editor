"""Filesystem-free historical validation, independent of current authorization."""
import re
import unicodedata
from .codec import check_typed
from .semantic import exact_signature, generated_payload
from .voice_timing import *

def require(condition):
    if not condition:
        raise ValueError("voice_timing_invalid")

def digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)

def identifier(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is not None)

def source_record_fingerprint(record):
    # M63's optional source locator is location evidence, not semantic identity.
    # Exact current record authorization is additionally fenced at runtime.
    return signed("source_record", without(record, "source_locator"))

def integer(value, low, high):
    require(type(value) is int and low <= value <= high)

def normalize(text):
    # Matching only: retain the exact source coordinates and excerpt digest.
    value = " ".join(unicodedata.normalize("NFC", text).casefold().split())
    while value and unicodedata.category(value[0]).startswith("P"):
        value = value[1:]
    while value and unicodedata.category(value[-1]).startswith("P"):
        value = value[:-1]
    return value.strip()

def validate_spec(spec):
    check_typed(AlignmentSpec, spec)
    require(spec == AlignmentSpec())

def validate_inspection(e):
    check_typed(AudioInspectionEvidence, e)
    digest(e.sha256)
    require(e.asset_id == "asset:sha256:" + e.sha256)
    integer(e.byte_count, 45, MAX_BYTES)
    require((e.contract_version, e.policy_id, e.compression, e.origin_policy) ==
            ("1", "PCM_WAV_V1", "UNCOMPRESSED_PCM", "PCM_FRAME_ZERO"))
    require(e.format_tag == 1 and e.channels in (1, 2) and e.bits_per_sample in (8, 16, 24, 32))
    require(e.sample_rate in RATES and e.sample_width == e.bits_per_sample // 8)
    require(e.block_align == e.channels * e.sample_width)
    require(e.byte_rate == e.sample_rate * e.block_align)
    integer(e.data_byte_count, 1, MAX_BYTES - 44)
    require(e.byte_count == 44 + e.data_byte_count + e.data_byte_count % 2)
    require(e.data_byte_count % e.block_align == 0)
    require(e.frame_count == e.data_byte_count // e.block_align and e.frame_count > 0)
    require(e.frame_count <= MAX_SECONDS * e.sample_rate)
    require(e.duration_us == e.frame_count * 1000000 // e.sample_rate)
    require(e.evidence_signature == inspection_signature(e))

def semantic_evidence(manifest, run):
    source = next(s for s in manifest.semantic.source_revisions
                  if s.source_revision_id == run.source_revision_id)
    document = next(d for d in manifest.semantic.documents
                    if d.semantic_document_id == run.semantic_document_id)
    require(document.source_revision_id == source.source_revision_id)
    require(run.source_record_fingerprint == source_record_fingerprint(source.content))
    require(run.semantic_generated_binding == exact_signature(generated_payload(document)))
    # Review output can change after capture; the captured value is request-bound.
    digest(run.semantic_output_binding)
    return source.content.normalized_text, {u.story_unit_id: u for u in document.story_units}

def validate_binding(binding, run, text, stories):
    check_typed(SourceBinding, binding)
    require(binding.source_revision_id == run.source_revision_id and
            binding.semantic_document_id == run.semantic_document_id)
    integer(binding.start_char, 0, len(text))
    integer(binding.end_char, binding.start_char + 1, len(text))
    excerpt = text[binding.start_char:binding.end_char]
    require(binding.excerpt_signature == exact_signature(excerpt))
    story = stories.get(binding.story_unit_id)
    require(story is not None and any(e.source_span.start <= binding.start_char <
        binding.end_char <= e.source_span.end for e in story.source_excerpts))
    return excerpt

def coverage(run, text, control=None):
    """Non-whitespace source character coverage; never invents missing timing."""
    intervals = sorted((b.start_char, b.end_char) for u in run.units
        if u.mapping_status in (MappingStatus.EXACT, MappingStatus.NORMALIZED_MATCH,
                                MappingStatus.EXPLICIT_VARIANT) for b in u.source_bindings)
    cursor = 0
    for start, end in intervals:
        if control:
            control.check()
        if text[cursor:start].strip():
            return False
        cursor = max(cursor, end)
    return bool(intervals) and not text[cursor:].strip() and not run.omissions and all(
        u.mapping_status in (MappingStatus.EXACT, MappingStatus.NORMALIZED_MATCH,
                            MappingStatus.EXPLICIT_VARIANT) for u in run.units)

def validate_output(manifest, run, control=None):
    validate_spec(run.spec)
    validate_inspection(run.inspection)
    require(run.contract_version == "1")
    require(run.input_signature == input_signature(run))
    require(0 < len(run.units) <= MAX_UNITS and len(run.omissions) <= MAX_ISSUES)
    text, stories = semantic_evidence(manifest, run)
    previous_end = 0
    previous_source_end = 0
    count = 0
    issues = len(run.omissions)
    for ordinal, unit in enumerate(run.units):
        if control:
            control.check()
        check_typed(TimedUnit, unit)
        require(unit.ordinal == ordinal)
        integer(unit.start_us, previous_end, run.inspection.duration_us)
        integer(unit.end_us, unit.start_us + 1, run.inspection.duration_us)
        require(unit.end_us * run.inspection.sample_rate <= run.inspection.frame_count * 1000000)
        previous_end = unit.end_us
        digest(unit.observed_signature)
        digest(unit.normalized_signature)
        require(unit.mapping_status != MappingStatus.SOURCE_OMITTED)
        require(len(unit.source_bindings) <= 8)
        count += len(unit.source_bindings)
        require(count <= MAX_BINDINGS)
        excerpts = []
        for b in unit.source_bindings:
            if control:
                control.check()
            excerpts.append(validate_binding(b, run, text, stories))
            require(b.start_char >= previous_source_end)
            previous_source_end = b.end_char
        status = unit.mapping_status
        matched = status in (MappingStatus.EXACT, MappingStatus.NORMALIZED_MATCH, MappingStatus.EXPLICIT_VARIANT)
        require(not matched or bool(excerpts))
        require(status not in (MappingStatus.SPEECH_ADDED, MappingStatus.UNMAPPED) or not excerpts)
        if status == MappingStatus.EXACT:
            require(unit.observed_signature == exact_signature(" ".join(excerpts)))
        if status == MappingStatus.NORMALIZED_MATCH:
            require(unit.normalized_signature == exact_signature(normalize(" ".join(excerpts))))
        if status == MappingStatus.EXPLICIT_VARIANT:
            digest(unit.variant_evidence_signature)
        else:
            require(unit.variant_evidence_signature is None)
        if status == MappingStatus.MISMATCH:
            require(bool(excerpts))
        issues += status in (MappingStatus.MISMATCH, MappingStatus.UNMAPPED, MappingStatus.SPEECH_ADDED)
        require(issues <= MAX_ISSUES)
        require(unit.unit_id == unit_id(run.input_signature, unit))
    last_end = 0
    mapped = sorted((b.start_char, b.end_char) for u in run.units for b in u.source_bindings)
    mi = 0
    for ordinal, omission in enumerate(run.omissions):
        if control:
            control.check()
        require(omission.ordinal == ordinal and omission.mapping_status == MappingStatus.SOURCE_OMITTED)
        b = omission.source_binding
        validate_binding(b, run, text, stories)
        require(b.start_char >= last_end)
        last_end = b.end_char
        while mi < len(mapped) and mapped[mi][1] <= b.start_char:
            mi += 1
        require(mi == len(mapped) or mapped[mi][0] >= b.end_char)
    require(count + len(run.omissions) <= MAX_BINDINGS)
    require(run.output_signature == output_signature(run))
    return coverage(run, text, control)

def validate_receipt(run):
    r = run.receipt
    check_typed(AcceptanceReceipt, r)
    require(r.contract_version == "1")
    identifier(r.acceptance_policy_id)
    identifier(r.acceptance_policy_version)
    require(run.request_signature == request_signature(run, r.acceptance_policy_id, r.acceptance_policy_version))
    require((r.request_signature, r.input_signature, r.output_signature) ==
            (run.request_signature, run.input_signature, run.output_signature))
    require(r.receipt_id == receipt_id(r))

def preflight_history(state, control=None):
    """Count only known containers/records; strict validation owns malformed types."""
    if control:
        control.check()
    if type(state) is not VoiceTimingState:
        return
    for name, limit in (("assets", MAX_ASSETS), ("revisions", MAX_REVISIONS), ("runs", MAX_RUNS)):
        items = getattr(state, name, None)
        if type(items) in (list, tuple):
            require(len(items) <= limit)
    runs = getattr(state, "runs", None)
    if type(runs) not in (list, tuple):
        return
    totals = [0, 0, 0]
    for run in runs:
        if control:
            control.check()
        if type(run) is not AlignmentRun:
            continue
        units, omissions = getattr(run, "units", None), getattr(run, "omissions", None)
        counts = [0, 0, 0]
        if type(omissions) in (list, tuple):
            counts[1] = counts[2] = len(omissions)
            require(len(omissions) <= MAX_ISSUES)
        if type(units) in (list, tuple):
            counts[0] = len(units)
            require(counts[0] <= MAX_UNITS)
            for i, unit in enumerate(units):
                if control and i % 256 == 0:
                    control.check()
                if type(unit) is not TimedUnit:
                    continue
                bindings = getattr(unit, "source_bindings", None)
                if type(bindings) in (list, tuple):
                    require(len(bindings) <= 8)
                    counts[1] += len(bindings)
                counts[2] += getattr(unit, "mapping_status", None) in (MappingStatus.MISMATCH,
                    MappingStatus.UNMAPPED, MappingStatus.SPEECH_ADDED)
                require(counts[1] <= MAX_BINDINGS and counts[2] <= MAX_ISSUES)
                require(totals[1] + counts[1] <= MAX_TOTAL_BINDINGS and
                        totals[2] + counts[2] <= MAX_TOTAL_ISSUES)
        for i, limit in enumerate((MAX_TOTAL_UNITS, MAX_TOTAL_BINDINGS, MAX_TOTAL_ISSUES)):
            totals[i] += counts[i]
            require(totals[i] <= limit)
        require(counts[1] <= MAX_BINDINGS and counts[2] <= MAX_ISSUES)


def validate_history(manifest, control=None):
    state = manifest.voice_timing
    preflight_history(state, control)
    check_typed(VoiceTimingState, state)
    require(len(state.assets) <= MAX_ASSETS and len(state.revisions) <= MAX_REVISIONS and len(state.runs) <= MAX_RUNS)
    assets, revisions, runs = {}, {}, {}
    for a in state.assets:
        if control:
            control.check()
        digest(a.sha256)
        integer(a.byte_count, 45, MAX_BYTES)
        require(a.asset_id == "asset:sha256:" + a.sha256 and a.asset_id not in assets)
        assets[a.asset_id] = a
    for r in state.revisions:
        if control:
            control.check()
        require(r.contract_version == "1" and r.asset_id in assets and r.revision_id not in revisions)
        integer(r.logical_revision, 1, 2147483647)
        require(r.provenance in ("UNSPECIFIED", "USER_IMPORT", "GENERIC_OUTPUT"))
        require(r.predecessor_revision_id is None or r.predecessor_revision_id in revisions)
        require(r.revision_id == revision_id(r))
        revisions[r.revision_id] = r
    total_units = total_bindings = total_issues = 0
    for run in state.runs:
        if control:
            control.check()
        require(run.narration_revision_id in revisions and run.alignment_run_id not in runs)
        a = assets[revisions[run.narration_revision_id].asset_id]
        require((run.inspection.asset_id, run.inspection.sha256, run.inspection.byte_count) ==
                (a.asset_id, a.sha256, a.byte_count))
        total_units += len(run.units)
        total_bindings += sum(len(u.source_bindings) for u in run.units) + len(run.omissions)
        total_issues += len(run.omissions) + sum(u.mapping_status in
            (MappingStatus.MISMATCH, MappingStatus.UNMAPPED, MappingStatus.SPEECH_ADDED) for u in run.units)
        require(total_units <= MAX_TOTAL_UNITS and total_bindings <= MAX_TOTAL_BINDINGS and total_issues <= MAX_TOTAL_ISSUES)
        validate_output(manifest, run, control)
        validate_receipt(run)
        require(run.alignment_run_id == run_id(run))
        runs[run.alignment_run_id] = run
    require(state.active_narration_revision_id is None or state.active_narration_revision_id in revisions)
    require(state.active_alignment_run_id is None or state.active_alignment_run_id in runs)
    if state.active_alignment_run_id is not None:
        require(runs[state.active_alignment_run_id].narration_revision_id == state.active_narration_revision_id)

def voice_timing_errors(manifest):
    try:
        validate_history(manifest)
        return []
    except (ValueError, TypeError, AttributeError, KeyError, StopIteration):
        return ["voice_timing_invalid"]
