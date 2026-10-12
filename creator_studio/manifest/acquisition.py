"""M68 immutable byte observations; deliberately separate from canonical media."""
from dataclasses import dataclass, field, replace
from enum import Enum
from .codec import to_data
from .semantic import exact_signature
from .retrieval import VisualMediaKind

MAX_ACQUISITION_RUNS = 64
MAX_SHOT_ACQUISITIONS_PER_RUN = 4096
MAX_TOTAL_HISTORICAL_SHOT_ACQUISITIONS = 65536
MAX_MATERIALIZATIONS = 16384
MAX_ASSETS = 16384
MAX_DIAGNOSTICS = 16
MAX_ASSET_BYTES = 512 * 1024 * 1024
MAX_TRANSFERRED_BYTES_PER_RUN = 2 * 1024 * 1024 * 1024
MAX_DISTINCT_ACQUISITIONS_PER_RUN = 256
MAX_TRANSFER_CHUNK = 1024 * 1024


class AcquisitionOutcome(str, Enum):
    MATERIALIZED = "MATERIALIZED"
    NOT_SELECTED_UPSTREAM = "NOT_SELECTED_UPSTREAM"
    UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"
    RIGHTS_BLOCKED = "RIGHTS_BLOCKED"


class MediaFormat(str, Enum):
    MP4 = "MP4"
    WEBM = "WEBM"
    JPEG = "JPEG"
    PNG = "PNG"


class MediaCodec(str, Enum):
    H264 = "H264"
    VP9 = "VP9"
    JPEG = "JPEG"
    PNG = "PNG"


@dataclass(frozen=True)
class AcquisitionProviderSpec:
    provider_id: str
    catalog_namespace: str
    adapter_version: str = "1"
    permission_policy_id: str = "explicit"
    permission_policy_version: str = "1"
    permits_acquisition: bool = False


@dataclass(frozen=True)
class AcquisitionSpec:
    contract_version: str = "1"
    engine_version: str = "1"
    providers: list[AcquisitionProviderSpec] = field(default_factory=list)
    rendition_policy_id: str = "largest_dimensions"
    rendition_policy_version: str = "1"
    inspection_policy_id: str = "objective_media"
    inspection_policy_version: str = "1"
    storage_policy_version: str = "1"
    max_asset_bytes: int = MAX_ASSET_BYTES
    max_run_bytes: int = MAX_TRANSFERRED_BYTES_PER_RUN
    max_acquisition_count: int = MAX_DISTINCT_ACQUISITIONS_PER_RUN


@dataclass(frozen=True)
class RenditionObservation:
    rendition_id: str
    media_kind: VisualMediaKind
    width: int
    height: int


@dataclass(frozen=True)
class InspectionFacts:
    inspector_id: str
    inspector_version: str
    media_kind: VisualMediaKind
    media_format: MediaFormat
    codec: MediaCodec
    width: int
    height: int
    duration_seconds: float | None
    policy_id: str = "objective_media"
    policy_version: str = "1"


@dataclass(frozen=True)
class MaterializedAsset:
    asset_id: str
    sha256: str
    byte_count: int
    object_key: str


@dataclass(frozen=True)
class MaterializationRecord:
    materialization_id: str
    retrieval_id: str
    candidate_id: str
    candidate_metadata_fingerprint: str
    provider: AcquisitionProviderSpec
    rendition: RenditionObservation
    inspection: InspectionFacts
    asset_id: str


@dataclass(frozen=True)
class ShotAcquisition:
    shot_selection_id: str
    outcome: AcquisitionOutcome
    materialization_id: str | None = None


@dataclass(frozen=True)
class AcquisitionRun:
    acquisition_id: str
    selection_id: str
    selection_output_signature: str
    effective_selection_output_signature: str
    acquisition_spec: AcquisitionSpec
    acquisition_input_fingerprint: str
    acquisition_signature: str
    shot_acquisitions: list[ShotAcquisition]
    output_signature: str


@dataclass
class AcquisitionState:
    runs: list[AcquisitionRun] = field(default_factory=list)
    materializations: list[MaterializationRecord] = field(default_factory=list)
    assets: list[MaterializedAsset] = field(default_factory=list)
    active_creator_acquisition_id: str | None = None


def object_key(digest):
    return f"objects/sha256/{digest[:2]}/{digest}.blob"


def materialization_id(record):
    data = to_data(record)
    data.pop("materialization_id")
    return "materialization:" + exact_signature(data)


def input_fingerprint(selection_id, immutable, effective):
    return exact_signature([selection_id, immutable, effective])


def acquisition_signature(fingerprint, spec):
    return exact_signature([fingerprint, spec])


def run_id(run):
    return "acquisition:" + exact_signature([run.acquisition_signature, run.shot_acquisitions])


def output_signature(run):
    data = to_data(run)
    data.pop("output_signature")
    return exact_signature(data)


def assign_identity(run):
    run = replace(run, acquisition_id=run_id(run))
    return replace(run, output_signature=output_signature(run))


def complete(run):
    return all(s.outcome == AcquisitionOutcome.MATERIALIZED for s in run.shot_acquisitions)
