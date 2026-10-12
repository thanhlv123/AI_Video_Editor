"""Pure historical validation and bounded preflight. Never invokes acceptance."""
from dataclasses import replace, fields
from .codec import check_typed
from .placement_timing import *
from .voice_timing import MappingStatus, SourceBinding
from .voice_timing_validation import (semantic_evidence, validate_binding, require,
    source_record_fingerprint, integer, identifier)
from .semantic import generated_payload
from .editing_validation import reconstruct

ACCEPTED_MATCHES = frozenset((MappingStatus.EXACT, MappingStatus.NORMALIZED_MATCH,
    MappingStatus.EXPLICIT_VARIANT))

# Complete persisted scalar inventory. Domain IDs retain their repository prefix
# plus SHA-256 width; equality validators remain responsible for their identity.
_ID_PREFIXES = {
    "placement_id": "edit_placement:", "placement_ids": "edit_placement:",
    "edit_plan_id": "edit:", "alignment_run_id": "alignment_run:",
    "alignment_receipt_id": "timing_receipt:", "narration_revision_id": "narration_revision:",
    "source_revision_id": "semantic_source:", "semantic_document_id": "semantic_document:",
    "story_unit_id": "story_unit:", "unit_id": "timing_unit:",
    "unallocated_unit_ids": "timing_unit:", "declaration_ref": "placement_declaration:",
    "acquisition_id": "acquisition:", "selection_id": "selection:",
    "retrieval_id": "retrieval:", "visual_plan_id": "visual_plan:",
    "placement_timing_plan_id": "placement_timing:",
    "active_placement_timing_plan_id": "placement_timing:", "receipt_id": "placement_receipt:",
}
_DIGESTS = frozenset(("source_record_fingerprint", "semantic_generated_binding",
    "semantic_output_binding", "content_revision_signature", "analysis_signature",
    "retained_chain_signature", "excerpt_signature", "request_signature",
    "input_signature", "output_signature", "declaration_signature", "edit_output_signature",
    "alignment_output_signature", "alignment_request_signature"))
_POLICIES = frozenset(("acceptance_policy_id", "acceptance_policy_version"))
_CLOSED = {"side": BoundarySide, "kind": BoundaryKind,
    "outcome": PlacementTimingOutcome, "diagnostics": TimingDiagnostic}
_SPEC = PlacementTimingSpec()
_SPEC_VALUES = {f.name: getattr(_SPEC, f.name) for f in fields(_SPEC)}
_RECORDS = (PlacementTimingSpec, PlacementTimingLineage, PlacementAllocationDeclaration,
    PlacementBoundaryDeclaration, PlacementBoundaryEvidence, PlacementTimingEntry,
    PlacementTimingPlan, PlacementTimingAcceptanceReceipt, PlacementTimingState)
_RECORD_FIELDS = {cls: frozenset(f.name for f in fields(cls)) for cls in _RECORDS}
# (maximum length, element contract); no recursive projection is built.
_COLLECTIONS = {
    (PlacementTimingState, "plans"): (MAX_PLANS, PlacementTimingPlan),
    (PlacementTimingPlan, "entries"): (MAX_ENTRIES_PER_PLAN, PlacementTimingEntry),
    (PlacementTimingPlan, "allocations"): (MAX_ALLOCATIONS_PER_PLAN, PlacementAllocationDeclaration),
    (PlacementTimingPlan, "explicit_boundaries"): (MAX_BOUNDARIES_PER_PLAN, PlacementBoundaryDeclaration),
    (PlacementTimingPlan, "placement_ids"): (MAX_ENTRIES_PER_PLAN, None),
    (PlacementTimingPlan, "unallocated_unit_ids"): (100000, None),
    (PlacementTimingEntry, "boundaries"): (MAX_BOUNDARY_DECLARATIONS_PER_ENTRY, PlacementBoundaryEvidence),
    (PlacementTimingEntry, "diagnostics"): (MAX_DIAGNOSTICS_PER_ENTRY, None),
}
_NESTED = {(PlacementTimingPlan, "lineage"): PlacementTimingLineage,
    (PlacementTimingPlan, "spec"): PlacementTimingSpec,
    (PlacementTimingPlan, "receipt"): PlacementTimingAcceptanceReceipt}


def preflight_scalar(name, value):
    """Check length before regex, enum lookup, escaping or hashing; defer types."""
    if isinstance(value, Enum):
        value = value.value
    if type(value) is not str:
        return
    if name in _ID_PREFIXES:
        require(len(value) <= len(_ID_PREFIXES[name]) + 64)
    elif name in _DIGESTS:
        require(len(value) in (0, 64))  # empty only during unsigned construction
        require(not value or all(c in "0123456789abcdef" for c in value))
    elif name in _POLICIES:
        require(len(value) <= 64)
        identifier(value)
    elif name in _CLOSED:
        require(len(value) <= max(len(e.value) for e in _CLOSED[name]))
        require(value in _CLOSED[name]._value2member_map_)
    elif name in _SPEC_VALUES:
        require(len(value) <= len(_SPEC_VALUES[name]))
        require(value == _SPEC_VALUES[name])
    else:
        # Wrong-type scalars are not exempt from capacity checks. Strict typing
        # still rejects them; numeric fields cannot become giant JSON integers.
        require(len(value) <= 256)


def _get(record, name, raw):
    return record.get(name) if raw else getattr(record, name, None)


def _preflight_malformed(value, depth=0, remaining=None):
    """Capacity-only guard for wrong shapes/unknown raw fields; never repair them."""
    remaining = [MAX_TOTAL_ALLOCATIONS] if remaining is None else remaining
    remaining[0] -= 1
    require(remaining[0] >= 0 and depth <= 32)
    preflight_scalar("malformed", value)
    if type(value) is int:
        require(value.bit_length() <= 64)
    if type(value) in (dict, list, tuple):
        require(len(value) <= MAX_TOTAL_ALLOCATIONS)
        if type(value) is dict:
            for key, item in value.items():
                _preflight_malformed(key, depth + 1, remaining)
                _preflight_malformed(item, depth + 1, remaining)
        else:
            for item in value:
                _preflight_malformed(item, depth + 1, remaining)


def preflight_record(record, cls, *, raw=False, control=None):
    """Walk only the fixed contract depth, tolerating ordinary malformed shapes."""
    if (type(record) is not dict if raw else type(record) is not cls):
        _preflight_malformed(record)
        return
    if raw:
        names = _RECORD_FIELDS[cls]
        # Constant-time capacity rejection before traversing unknown members.
        require(len(record) <= len(names))
        for key, item in record.items():
            if key not in names:
                _preflight_malformed(key)
                _preflight_malformed(item)
    for f in fields(cls):
        value = _get(record, f.name, raw)
        collection = _COLLECTIONS.get((cls, f.name))
        nested = _NESTED.get((cls, f.name))
        if collection and type(value) in (list, tuple):
            limit, element = collection
            require(len(value) <= limit)
            for item in value:
                if control:
                    control.check()
                if element:
                    preflight_record(item, element, raw=raw, control=control)
                else:
                    preflight_scalar(f.name, item)
                    if type(item) in (dict, list, tuple):
                        _preflight_malformed(item)
        elif nested:
            preflight_record(value, nested, raw=raw, control=control)
        else:
            preflight_scalar(f.name, value)
            if type(value) in (dict, list, tuple):
                _preflight_malformed(value)
            if type(value) is int:
                require(value.bit_length() <= 64)


def _preflight_state(state, *, raw=False, control=None):
    if control:
        control.check()
    preflight_record(state, PlacementTimingState, raw=raw, control=control)
    if (type(state) is not dict if raw else type(state) is not PlacementTimingState):
        return
    plans = _get(state, "plans", raw)
    if type(plans) not in (list, tuple):
        return
    totals = [0, 0, 0]
    for plan in plans:
        if (type(plan) is not dict if raw else type(plan) is not PlacementTimingPlan):
            continue
        for i, (name, total_limit, per_entry) in enumerate((
                ("entries", MAX_TOTAL_ENTRIES, None),
                ("allocations", MAX_TOTAL_ALLOCATIONS, MAX_ALLOCATIONS_PER_ENTRY),
                ("explicit_boundaries", MAX_TOTAL_BOUNDARIES, MAX_BOUNDARY_DECLARATIONS_PER_ENTRY))):
            items = _get(plan, name, raw)
            if type(items) not in (list, tuple):
                continue
            totals[i] += len(items)
            require(totals[i] <= total_limit)
            if per_entry is not None:
                counts = {}
                for item in items:
                    pid = (item.get("placement_id") if type(item) is dict else None) if raw else getattr(item, "placement_id", None)
                    if type(pid) is str:
                        # Scalar preflight already ran before dictionary hashing.
                        counts[pid] = counts.get(pid, 0) + 1
                        require(counts[pid] <= per_entry)


def preflight_document(state):
    """Raw additive migration guard before deepcopy; malformed types stay strict."""
    _preflight_state(state, raw=True)


def preflight_history(state, control=None):
    """Complete shallow field/count guard before recursive typing/hash/copies."""
    _preflight_state(state, control=control)

def retained_chain(manifest, edit, alignment):
    acquisition = next(r for r in manifest.acquisition.runs if r.acquisition_id == edit.acquisition_id)
    require(edit == reconstruct(manifest, acquisition, edit.edit_spec))
    selection = next(r for r in manifest.selection.runs if r.selection_id == acquisition.selection_id)
    retrieval = next(r for r in manifest.retrieval.runs if r.retrieval_id == selection.retrieval_id)
    visual = next(p for p in manifest.visual_planning.plans if p.visual_plan_id == retrieval.visual_plan_id)
    document = next(d for d in manifest.semantic.documents if d.semantic_document_id == visual.semantic_document_id)
    source = next(s for s in manifest.semantic.source_revisions if s.source_revision_id == document.source_revision_id)
    # Use M65's captured semantic output, never today's mutable review output.
    require((alignment.source_revision_id, alignment.semantic_document_id,
        alignment.source_record_fingerprint, alignment.semantic_generated_binding,
        alignment.semantic_output_binding) == (source.source_revision_id,
        document.semantic_document_id, source_record_fingerprint(source.content),
        exact_signature(generated_payload(document)), visual.semantic_output_signature))
    require(retrieval.upstream_binding_signature == exact_signature([
        visual.visual_plan_id, retrieval.visual_plan_output_signature,
        document.semantic_document_id, visual.semantic_output_signature,
        document.analysis_signature, document.content_revision_signature,
        source.source_revision_id, exact_signature(source.content)]))
    return PlacementTimingLineage(acquisition.acquisition_id, selection.selection_id,
        retrieval.retrieval_id, visual.visual_plan_id, source.source_revision_id,
        alignment.source_record_fingerprint, document.semantic_document_id,
        alignment.semantic_generated_binding, visual.semantic_output_signature,
        document.content_revision_signature, document.analysis_signature,
        signed("retained_chain", [edit.upstream_binding_signature,
            acquisition.output_signature, selection.output_signature,
            retrieval.output_signature, retrieval.upstream_binding_signature,
            retrieval.visual_plan_output_signature, visual.semantic_input_fingerprint]))

def allocation_binding(a):
    return SourceBinding(a.source_revision_id, a.semantic_document_id,
        a.story_unit_id, a.start_char, a.end_char, a.excerpt_signature)

def intersects(a, b):
    return (a.source_revision_id == b.source_revision_id and
        a.semantic_document_id == b.semantic_document_id and
        a.story_unit_id == b.story_unit_id and
        a.start_char < b.end_char and b.start_char < a.end_char)

def contains(a, b):
    return intersects(a, b) and a.start_char <= b.start_char < b.end_char <= a.end_char

def validate_declarations(manifest, plan, alignment, control=None):
    text, stories = semantic_evidence(manifest, alignment)
    ids = set(plan.placement_ids)
    refs, sides = set(), set()
    placement_allocations = {}
    for a in plan.allocations:
        if control:
            control.check()
        check_typed(PlacementAllocationDeclaration, a)
        require(a.placement_id in ids and a.declaration_ref == declaration_ref(a)
            and a.declaration_ref not in refs)
        refs.add(a.declaration_ref)
        validate_binding(allocation_binding(a), alignment, text, stories)
        previous = placement_allocations.setdefault(a.placement_id, [])
        require(not any(intersects(a, b) for b in previous))
        previous.append(a)
    for b in plan.explicit_boundaries:
        if control:
            control.check()
        check_typed(PlacementBoundaryDeclaration, b)
        require(b.placement_id in ids and b.declaration_ref == declaration_ref(b)
            and b.declaration_ref not in refs and (b.placement_id, b.side) not in sides)
        integer(b.time_us, 0, plan.narration_duration_us)
        refs.add(b.declaration_ref)
        sides.add((b.placement_id, b.side))
    return text

def lexical_envelope(allocations, alignment, text, control=None):
    """Return exact per-side evidence, or closed blockers; never interpolate."""
    if not allocations:
        return {}, PlacementTimingOutcome.UNRESOLVED, [TimingDiagnostic.NO_AUTHORITY], []
    supporting = []
    diagnostics = []
    for omission in alignment.omissions:
        if control:
            control.check()
        if any(intersects(a, omission.source_binding) for a in allocations):
            diagnostics.append(TimingDiagnostic.SOURCE_OMITTED)
    for i, unit in enumerate(alignment.units):
        if control:
            control.check()
        if any(intersects(a, b) for a in allocations for b in unit.source_bindings):
            supporting.append((i, unit))
    if not supporting:
        return {}, (PlacementTimingOutcome.SOURCE_OMITTED if diagnostics else
            PlacementTimingOutcome.NO_SEMANTIC_TIMING), list(dict.fromkeys(diagnostics or
            [TimingDiagnostic.NO_SUPPORT])), []
    first, last = supporting[0][0], supporting[-1][0]
    covered = []
    partial_sides = set()
    for index, unit in enumerate(alignment.units[first:last + 1], first):
        if control:
            control.check()
        if unit.mapping_status == MappingStatus.SPEECH_ADDED:
            diagnostics.append(TimingDiagnostic.SPEECH_ADDED)
        elif unit.mapping_status == MappingStatus.MISMATCH:
            diagnostics.append(TimingDiagnostic.MISMATCH)
        elif unit.mapping_status == MappingStatus.UNMAPPED:
            diagnostics.append(TimingDiagnostic.UNMAPPED)
        elif unit.mapping_status not in ACCEPTED_MATCHES:
            diagnostics.append(TimingDiagnostic.UNRELATED_UNIT)
        elif not unit.source_bindings or not all(any(intersects(a, b) for a in allocations)
                for b in unit.source_bindings):
            diagnostics.append(TimingDiagnostic.UNRELATED_UNIT)
        else:
            for b in unit.source_bindings:
                matching = [a for a in allocations if intersects(a, b)]
                for a in matching:
                    if not contains(a, b):
                        if index == first and b.start_char < a.start_char:
                            partial_sides.add(BoundarySide.START)
                        elif b.start_char < a.start_char:
                            diagnostics.append(TimingDiagnostic.UNRELATED_UNIT)
                        if index == last and a.end_char < b.end_char:
                            partial_sides.add(BoundarySide.END)
                        elif a.end_char < b.end_char:
                            diagnostics.append(TimingDiagnostic.UNRELATED_UNIT)
                    covered.append(replace(b, start_char=max(a.start_char, b.start_char),
                        end_char=min(a.end_char, b.end_char)))
    for a in allocations:
        if control:
            control.check()
        cursor = a.start_char
        for b in sorted((b for b in covered if contains(a, b)), key=lambda b: b.start_char):
            if text[cursor:b.start_char].strip():
                diagnostics.append(TimingDiagnostic.PARTIAL_COVERAGE)
            cursor = max(cursor, b.end_char)
        if text[cursor:a.end_char].strip():
            diagnostics.append(TimingDiagnostic.PARTIAL_COVERAGE)
    diagnostics = list(dict.fromkeys(diagnostics))
    outcome = PlacementTimingOutcome.AMBIGUOUS_BOUNDARY
    priorities = ((TimingDiagnostic.SOURCE_OMITTED, PlacementTimingOutcome.SOURCE_OMITTED),
        (TimingDiagnostic.MISMATCH, PlacementTimingOutcome.MISMATCH_BLOCKED),
        (TimingDiagnostic.UNMAPPED, PlacementTimingOutcome.UNMAPPED_BLOCKED),
        (TimingDiagnostic.PARTIAL_COVERAGE, PlacementTimingOutcome.PARTIAL_COVERAGE))
    for diagnostic, selected in priorities:
        if diagnostic in diagnostics:
            outcome = selected
            break
    if diagnostics:
        return {}, outcome, diagnostics, []
    start, end = supporting[0][1], supporting[-1][1]
    # Only allocation edges coincident with retained lexical edges may derive.
    edges = {}
    for side, unit, kind in ((BoundarySide.START, start, BoundaryKind.M70_UNIT_START),
            (BoundarySide.END, end, BoundaryKind.M70_UNIT_END)):
        if control:
            control.check()
        candidates = [a for a in allocations if any(intersects(a, b) and (
            (side == BoundarySide.START and a.start_char <= b.start_char and
                not text[a.start_char:b.start_char].strip()) or
            (side == BoundarySide.END and b.end_char <= a.end_char and
                not text[b.end_char:a.end_char].strip())) for b in unit.source_bindings)]
        if len(candidates) == 1 and side not in partial_sides:
            edges[side] = (unit.start_us if side == BoundarySide.START else unit.end_us,
                PlacementBoundaryEvidence(side, kind, candidates[0].declaration_ref, unit.unit_id))
    return edges, outcome, ([] if len(edges) == 2 else [TimingDiagnostic.INDIVISIBLE_EDGE]), [u.unit_id for _, u in supporting]

def derive_entries(plan, alignment, text, control=None):
    entries, used = [], set()
    previous_end = 0
    for pid in plan.placement_ids:
        if control:
            control.check()
        allocations = [a for a in plan.allocations if a.placement_id == pid]
        explicit = [b for b in plan.explicit_boundaries if b.placement_id == pid]
        edges, outcome, diagnostics, unit_ids = lexical_envelope(allocations, alignment, text, control)
        for b in explicit:
            # A caller must not declare competing sources for the same side.
            require(b.side not in edges)
            edges[b.side] = (b.time_us, PlacementBoundaryEvidence(b.side,
                BoundaryKind.ACCEPTED_EXPLICIT_TIME, b.declaration_ref))
        if len(edges) == 2:
            start, end = edges[BoundarySide.START][0], edges[BoundarySide.END][0]
            integer(start, 0, alignment.inspection.duration_us)
            integer(end, start + 1, alignment.inspection.duration_us)
            if start < previous_end:
                outcome, diagnostics = PlacementTimingOutcome.ORDER_CONFLICT, [TimingDiagnostic.ORDER_CONFLICT]
            else:
                entries.append(PlacementTimingEntry(pid, PlacementTimingOutcome.TIMED, start, end,
                    [edges[BoundarySide.START][1], edges[BoundarySide.END][1]]))
                previous_end = end
                used.update(unit_ids)
                continue
        entries.append(PlacementTimingEntry(pid, outcome, diagnostics=diagnostics))
    # Bounded summary of retained units with no derived allocation support.
    return entries, [u.unit_id for u in alignment.units if u.unit_id not in used]

def validate_receipt(plan):
    r = plan.receipt
    require(r is not None)
    require(type(r) is PlacementTimingAcceptanceReceipt and all(
        type(getattr(r, f, None)) is str and len(getattr(r, f)) <= 128
        for f in r.__dataclass_fields__))
    check_typed(PlacementTimingAcceptanceReceipt, r)
    require(r.contract_version == "1" and r.receipt_id == receipt_id(r))
    require((r.acceptance_policy_id, r.acceptance_policy_version, r.request_signature,
        r.input_signature, r.output_signature, r.declaration_signature) ==
        (plan.acceptance_policy_id, plan.acceptance_policy_version, plan.request_signature,
        plan.input_signature, plan.output_signature, plan.declaration_signature))

def validate_plan(manifest, plan, control=None, provisional=False):
    preflight_history(PlacementTimingState([plan]), control)
    check_typed(PlacementTimingPlan, plan)
    if plan.allocations or plan.explicit_boundaries:
        canonical_payload(plan, include_request=True)
    require(plan.spec == PlacementTimingSpec())
    identifier(plan.acceptance_policy_id)
    identifier(plan.acceptance_policy_version)
    edit = next(p for p in manifest.editing.plans if p.edit_plan_id == plan.edit_plan_id)
    alignment = next(r for r in manifest.voice_timing.runs if r.alignment_run_id == plan.alignment_run_id)
    require(plan.edit_output_signature == edit.output_signature and
        plan.placement_ids == [p.placement_id for p in edit.placements])
    require((plan.alignment_output_signature, plan.alignment_request_signature,
        plan.alignment_receipt_id, plan.narration_revision_id, plan.narration_duration_us) ==
        (alignment.output_signature, alignment.request_signature, alignment.receipt.receipt_id,
        alignment.narration_revision_id, alignment.inspection.duration_us))
    require(plan.lineage == retained_chain(manifest, edit, alignment))
    text = validate_declarations(manifest, plan, alignment, control)
    require((plan.entries, plan.unallocated_unit_ids) == derive_entries(plan, alignment, text, control))
    require(plan.declaration_signature == declaration_signature(plan))
    require(plan.input_signature == input_signature(plan) and plan.output_signature == output_signature(plan))
    if plan.allocations or plan.explicit_boundaries:
        require(plan.request_signature == request_signature(plan))
        if not provisional:
            validate_receipt(plan)
    else:
        require(plan.request_signature is None and plan.receipt is None and
            all(e.outcome != PlacementTimingOutcome.TIMED and e.start_us is None and
                e.end_us is None and not e.boundaries for e in plan.entries))
    if not provisional:
        require(plan.placement_timing_plan_id == plan_id(plan))

def validate_history(manifest, control=None):
    state = manifest.placement_timing
    preflight_history(state, control)
    check_typed(PlacementTimingState, state)
    ids = set()
    for plan in state.plans:
        if control:
            control.check()
        require(plan.placement_timing_plan_id not in ids)
        ids.add(plan.placement_timing_plan_id)
        validate_plan(manifest, plan, control)
    require(state.active_placement_timing_plan_id is None or state.active_placement_timing_plan_id in ids)

def placement_timing_errors(manifest):
    try:
        validate_history(manifest)
        return []
    except Exception:
        return ["placement_timing_invalid"]
