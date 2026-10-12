"""M70 closed retained evidence. No runtime audio access or acceptance callbacks."""
from dataclasses import dataclass, field, replace
from enum import Enum
from .codec import to_data
from .semantic import exact_signature

MAX_ASSETS = MAX_REVISIONS = MAX_RUNS = 64
MAX_UNITS = 100000
MAX_TOTAL_UNITS = 500000
MAX_BINDINGS = 200000
MAX_TOTAL_BINDINGS = 1000000
MAX_ISSUES = 100000
MAX_TOTAL_ISSUES = 500000
MAX_BYTES = 1073741824
MAX_SECONDS = 14400
READ_CHUNK = 1048576
RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 88200, 96000)

class NarrationOrigin(str, Enum):
    IMPORTED = "IMPORTED"
    GENERATED = "GENERATED"

class MappingStatus(str, Enum):
    EXACT = "EXACT"
    NORMALIZED_MATCH = "NORMALIZED_MATCH"
    EXPLICIT_VARIANT = "EXPLICIT_VARIANT"
    SOURCE_OMITTED = "SOURCE_OMITTED"
    SPEECH_ADDED = "SPEECH_ADDED"
    MISMATCH = "MISMATCH"
    UNMAPPED = "UNMAPPED"

@dataclass(frozen=True)
class NarrationAsset:
    asset_id: str
    sha256: str
    byte_count: int

@dataclass(frozen=True)
class NarrationRevision:
    revision_id: str
    asset_id: str
    origin: NarrationOrigin
    logical_revision: int
    provenance: str = "UNSPECIFIED"
    predecessor_revision_id: str | None = None
    contract_version: str = "1"

@dataclass(frozen=True)
class AudioInspectionEvidence:
    asset_id: str
    sha256: str
    byte_count: int
    format_tag: int
    channels: int
    bits_per_sample: int
    sample_width: int
    sample_rate: int
    block_align: int
    byte_rate: int
    data_byte_count: int
    frame_count: int
    duration_us: int
    contract_version: str = "1"
    policy_id: str = "PCM_WAV_V1"
    compression: str = "UNCOMPRESSED_PCM"
    origin_policy: str = "PCM_FRAME_ZERO"
    evidence_signature: str = ""

@dataclass(frozen=True)
class AlignmentSpec:
    contract_version: str = "1"
    granularity: str = "LEXICAL"
    time_unit: str = "INTEGER_MICROSECONDS"
    overlap_policy: str = "ORDERED_NO_OVERLAP"
    normalization_policy: str = "NFC_CASEFOLD_EDGE_PUNCT_WS_V1"
    source_coordinates: str = "M64_NORMALIZED_CHAR_HALF_OPEN"
    matching_policy: str = "EXACT_NORMALIZED_OR_EXPLICIT_V1"

@dataclass(frozen=True)
class SourceBinding:
    source_revision_id: str
    semantic_document_id: str
    story_unit_id: str
    start_char: int
    end_char: int
    excerpt_signature: str

@dataclass(frozen=True)
class TimedUnit:
    unit_id: str
    ordinal: int
    start_us: int
    end_us: int
    observed_signature: str
    normalized_signature: str
    mapping_status: MappingStatus
    source_bindings: list[SourceBinding]
    variant_evidence_signature: str | None = None

@dataclass(frozen=True)
class SourceOmission:
    ordinal: int
    source_binding: SourceBinding
    mapping_status: MappingStatus = MappingStatus.SOURCE_OMITTED

@dataclass(frozen=True)
class AcceptanceReceipt:
    acceptance_policy_id: str
    acceptance_policy_version: str
    request_signature: str
    input_signature: str
    output_signature: str
    receipt_id: str = ""
    contract_version: str = "1"

@dataclass(frozen=True)
class AlignmentRun:
    alignment_run_id: str
    narration_revision_id: str
    inspection: AudioInspectionEvidence
    source_revision_id: str
    source_record_fingerprint: str
    semantic_document_id: str
    semantic_generated_binding: str
    semantic_output_binding: str
    spec: AlignmentSpec
    input_signature: str
    units: list[TimedUnit]
    omissions: list[SourceOmission]
    output_signature: str
    request_signature: str
    receipt: AcceptanceReceipt
    contract_version: str = "1"

@dataclass
class VoiceTimingState:
    assets: list[NarrationAsset] = field(default_factory=list)
    revisions: list[NarrationRevision] = field(default_factory=list)
    runs: list[AlignmentRun] = field(default_factory=list)
    active_narration_revision_id: str | None = None
    active_alignment_run_id: str | None = None

def signed(domain, payload):
    return exact_signature(["M70", domain, "1", payload])

def without(value, *names):
    data = to_data(value)
    for name in names:
        data.pop(name)
    return data

def revision_id(revision):
    return "narration_revision:" + signed("revision", without(revision, "revision_id"))

def inspection_signature(evidence):
    return signed("inspection", without(evidence, "evidence_signature"))

def input_signature(run):
    return signed("alignment_input", [run.contract_version, run.narration_revision_id,
        run.inspection, run.source_revision_id, run.source_record_fingerprint,
        run.semantic_document_id, run.semantic_generated_binding,
        run.semantic_output_binding, run.spec])

def unit_id(input_sig, unit):
    return "timing_unit:" + signed("unit", [input_sig, without(unit, "unit_id")])

def output_signature(run):
    return signed("alignment_output", [run.input_signature, run.units, run.omissions])

def request_signature(run, policy_id, policy_version):
    return signed("acceptance_request", [run.input_signature, run.output_signature,
        policy_id, policy_version])

def receipt_id(receipt):
    return "timing_receipt:" + signed("receipt", without(receipt, "receipt_id"))

def run_id(run):
    return "alignment_run:" + signed("run", [run.input_signature,
        run.output_signature, run.request_signature, run.receipt])

def make_receipt(request):
    """Receipt construction utility, NOT an acceptance policy or automatic gate."""
    r = AcceptanceReceipt(request.acceptance_policy_id, request.acceptance_policy_version,
        request.request_signature, request.input_signature, request.output_signature)
    return replace(r, receipt_id=receipt_id(r))
