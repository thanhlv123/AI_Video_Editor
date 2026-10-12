"""Filesystem-free historical validation. Current usability belongs to runtime."""
import math
import re
from .codec import check_typed
from .acquisition import *
from .retrieval import metadata_fingerprint, UsageRestriction
from .rights import Rights
from .retrieval_validation import public_identifier, catalog_namespace_valid, public_text
from .selection import SelectionOutcome, output_signature as selection_output


def identifier(value):
    return public_identifier(value, 48) and public_text(value, 48)


def captured_review_valid(selection, review_history, effective):
    from .selection import ReviewStatus
    subjects = {s.shot_selection_id for s in selection.shot_selections}
    tips = {}
    immutable = selection_output(selection)
    def matches():
        projection = [[s.shot_selection_id, tips[s.shot_selection_id].review_id,
                       tips[s.shot_selection_id].status, tips[s.shot_selection_id].locked]
                      if s.shot_selection_id in tips else
                      [s.shot_selection_id, None, ReviewStatus.PENDING, False]
                      for s in selection.shot_selections]
        return (exact_signature([immutable, projection]) == effective
                and not any(r.status == ReviewStatus.REJECTED for r in tips.values()))
    if matches():
        return True
    for review in review_history:
        if review.shot_selection_id in subjects:
            tips[review.shot_selection_id] = review
            if matches():
                return True
    return False


def provider_valid(provider):
    check_typed(AcquisitionProviderSpec, provider)
    return (identifier(provider.provider_id) and catalog_namespace_valid(provider.catalog_namespace)
            and all(identifier(v) for v in (provider.adapter_version,
                provider.permission_policy_id, provider.permission_policy_version)))


def spec_valid(spec):
    try:
        check_typed(AcquisitionSpec, spec)
        return (spec.contract_version == spec.engine_version == spec.storage_policy_version == "1"
            and spec.rendition_policy_id == "largest_dimensions" and spec.rendition_policy_version == "1"
            and spec.inspection_policy_id == "objective_media" and spec.inspection_policy_version == "1"
            and 0 < spec.max_asset_bytes <= MAX_ASSET_BYTES
            and 0 < spec.max_run_bytes <= MAX_TRANSFERRED_BYTES_PER_RUN
            and 0 < spec.max_acquisition_count <= MAX_DISTINCT_ACQUISITIONS_PER_RUN
            and len(spec.providers) <= 16 and all(provider_valid(p) for p in spec.providers)
            and len({(p.provider_id, p.catalog_namespace) for p in spec.providers}) == len(spec.providers))
    except Exception:
        return False


def dimensions_valid(width, height):
    return (type(width) is int and type(height) is int and 0 < width <= 16384
            and 0 < height <= 16384 and width * height <= 100_000_000)


def rendition_valid(facts):
    check_typed(RenditionObservation, facts)
    return (identifier(facts.rendition_id) and dimensions_valid(facts.width, facts.height)
            and facts.media_kind in (VisualMediaKind.VIDEO, VisualMediaKind.IMAGE, VisualMediaKind.GRAPHIC))


def inspection_valid(facts):
    try:
        check_typed(InspectionFacts, facts)
        pairs = {MediaFormat.MP4: MediaCodec.H264, MediaFormat.WEBM: MediaCodec.VP9,
                 MediaFormat.JPEG: MediaCodec.JPEG, MediaFormat.PNG: MediaCodec.PNG}
        video = facts.media_format in (MediaFormat.MP4, MediaFormat.WEBM)
        return (identifier(facts.inspector_id) and identifier(facts.inspector_version)
            and facts.policy_id == "objective_media" and facts.policy_version == "1"
            and pairs.get(facts.media_format) == facts.codec
            and dimensions_valid(facts.width, facts.height)
            and ((video and facts.media_kind == VisualMediaKind.VIDEO
                  and facts.duration_seconds is not None and math.isfinite(facts.duration_seconds)
                  and 0 < facts.duration_seconds <= 86400)
                 or (not video and facts.media_kind in (VisualMediaKind.IMAGE, VisualMediaKind.GRAPHIC)
                     and facts.duration_seconds is None)))
    except Exception:
        return False


def acquisition_errors(manifest):
    try:
        state = manifest.acquisition
        check_typed(AcquisitionState, state)
        if not (len(state.runs) <= MAX_ACQUISITION_RUNS):
            raise ValueError("acquisition_contract_invalid")
        if not (len(state.materializations) <= MAX_MATERIALIZATIONS and len(state.assets) <= MAX_ASSETS):
            raise ValueError("acquisition_contract_invalid")
        if not (sum(len(r.shot_acquisitions) for r in state.runs) <= MAX_TOTAL_HISTORICAL_SHOT_ACQUISITIONS):
            raise ValueError("acquisition_contract_invalid")
        runs = {r.acquisition_id: r for r in state.runs}
        records = {r.materialization_id: r for r in state.materializations}
        assets = {a.asset_id: a for a in state.assets}
        if not (len(runs) == len(state.runs) and len(records) == len(state.materializations)):
            raise ValueError("acquisition_contract_invalid")
        if not (len(assets) == len(state.assets)):
            raise ValueError("acquisition_contract_invalid")
        if not (state.active_creator_acquisition_id is None or state.active_creator_acquisition_id in runs):
            raise ValueError("acquisition_contract_invalid")
        selections = {r.selection_id: r for r in manifest.selection.runs}
        retrievals = {r.retrieval_id: r for r in manifest.retrieval.runs}
        used_records, used_assets = set(), set()
        for asset in state.assets:
            if not (re.fullmatch(r"[0-9a-f]{64}", asset.sha256)):
                raise ValueError("acquisition_contract_invalid")
            if not (asset.asset_id == "asset:sha256:" + asset.sha256):
                raise ValueError("acquisition_contract_invalid")
            if not (asset.object_key == object_key(asset.sha256)):
                raise ValueError("acquisition_contract_invalid")
            if not (0 < asset.byte_count <= MAX_ASSET_BYTES):
                raise ValueError("acquisition_contract_invalid")
        for record in state.materializations:
            retrieval = retrievals[record.retrieval_id]
            candidate = next(c for c in retrieval.candidates if c.candidate_id == record.candidate_id)
            if not (candidate.usage_restriction != UsageRestriction.REFERENCE_ONLY):
                raise ValueError("acquisition_contract_invalid")
            if not (candidate.provenance_hint.declared_rights != Rights.REFERENCE_ONLY):
                raise ValueError("acquisition_contract_invalid")
            if not (candidate.metadata_fingerprint == metadata_fingerprint(candidate) == record.candidate_metadata_fingerprint):
                raise ValueError("acquisition_contract_invalid")
            if not (provider_valid(record.provider) and record.provider.permits_acquisition):
                raise ValueError("acquisition_contract_invalid")
            if not ((record.provider.provider_id, record.provider.catalog_namespace) == (candidate.provider_id, candidate.catalog_namespace)):
                raise ValueError("acquisition_contract_invalid")
            if not (rendition_valid(record.rendition) and inspection_valid(record.inspection)):
                raise ValueError("acquisition_contract_invalid")
            if not (record.rendition.media_kind == record.inspection.media_kind == candidate.visual_media_kind):
                raise ValueError("acquisition_contract_invalid")
            if not (record.materialization_id == materialization_id(record)):
                raise ValueError("acquisition_contract_invalid")
            if not (record.asset_id in assets):
                raise ValueError("acquisition_contract_invalid")
            used_assets.add(record.asset_id)
        for run in state.runs:
            selection = selections[run.selection_id]
            if not (spec_valid(run.acquisition_spec)):
                raise ValueError("acquisition_contract_invalid")
            if not (run.selection_output_signature == selection_output(selection)):
                raise ValueError("acquisition_contract_invalid")
            if not (re.fullmatch(r"[0-9a-f]{64}", run.effective_selection_output_signature)):
                raise ValueError("acquisition_contract_invalid")
            # Reviews are append-only; captured effective state must be an actual historical prefix.
            if not captured_review_valid(selection, manifest.selection.reviews,
                                         run.effective_selection_output_signature):
                raise ValueError("acquisition_contract_invalid")
            if not (run.acquisition_input_fingerprint == input_fingerprint(run.selection_id,
                run.selection_output_signature, run.effective_selection_output_signature)):
                raise ValueError("acquisition_contract_invalid")
            if not (run.acquisition_signature == acquisition_signature(run.acquisition_input_fingerprint, run.acquisition_spec)):
                raise ValueError("acquisition_contract_invalid")
            if not (run.acquisition_id == run_id(run) and run.output_signature == output_signature(run)):
                raise ValueError("acquisition_contract_invalid")
            if not (len(run.shot_acquisitions) <= MAX_SHOT_ACQUISITIONS_PER_RUN):
                raise ValueError("acquisition_contract_invalid")
            if not ([s.shot_selection_id for s in run.shot_acquisitions] == [s.shot_selection_id for s in selection.shot_selections]):
                raise ValueError("acquisition_contract_invalid")
            referenced = set()
            observations = {}
            for shot, choice in zip(run.shot_acquisitions, selection.shot_selections):
                if choice.outcome == SelectionOutcome.UNRESOLVED:
                    if not (shot.outcome == AcquisitionOutcome.NOT_SELECTED_UPSTREAM):
                        raise ValueError("acquisition_contract_invalid")
                else:
                    if not (shot.outcome != AcquisitionOutcome.NOT_SELECTED_UPSTREAM):
                        raise ValueError("acquisition_contract_invalid")
                if shot.outcome == AcquisitionOutcome.MATERIALIZED:
                    record = records[shot.materialization_id]
                    if not (record.retrieval_id == selection.retrieval_id):
                        raise ValueError("acquisition_contract_invalid")
                    if not (record.candidate_id == choice.selected_candidate.candidate_id):
                        raise ValueError("acquisition_contract_invalid")
                    if not (record.candidate_metadata_fingerprint == choice.selected_candidate.metadata_fingerprint):
                        raise ValueError("acquisition_contract_invalid")
                    if not (record.provider in run.acquisition_spec.providers):
                        raise ValueError("acquisition_contract_invalid")
                    if not (record.inspection.policy_id == run.acquisition_spec.inspection_policy_id):
                        raise ValueError("acquisition_contract_invalid")
                    if not (record.inspection.policy_version == run.acquisition_spec.inspection_policy_version):
                        raise ValueError("acquisition_contract_invalid")
                    if not (assets[record.asset_id].byte_count <= run.acquisition_spec.max_asset_bytes):
                        raise ValueError("acquisition_contract_invalid")
                    observation = (record.retrieval_id, record.candidate_id, record.candidate_metadata_fingerprint,
                                   exact_signature(record.provider))
                    if not (observations.get(observation, record.materialization_id) == record.materialization_id):
                        raise ValueError("acquisition_contract_invalid")
                    observations[observation] = record.materialization_id
                    referenced.add(record.materialization_id)
                    used_records.add(record.materialization_id)
                else:
                    if not (shot.materialization_id is None):
                        raise ValueError("acquisition_contract_invalid")
            if not (len(referenced) <= run.acquisition_spec.max_acquisition_count):
                raise ValueError("acquisition_contract_invalid")
            if not (sum(assets[records[r].asset_id].byte_count for r in referenced) <= run.acquisition_spec.max_run_bytes):
                raise ValueError("acquisition_contract_invalid")
        if not (used_records == set(records) and used_assets == set(assets)):
            raise ValueError("acquisition_contract_invalid")
        return []
    except Exception:
        return ["acquisition_contract_invalid"]
