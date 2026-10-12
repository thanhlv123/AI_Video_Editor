"""Untrusted runtime observations and deeply immutable acceptance requests."""
from dataclasses import dataclass
from typing import Protocol
from ..manifest.voice_timing import (AudioInspectionEvidence, AlignmentSpec,
    SourceBinding, MappingStatus, AcceptanceReceipt)

class VoiceTimingError(ValueError):
    CODES = frozenset(("voice_timing_invalid", "voice_timing_stale", "voice_audio_unusable",
        "voice_gate_required", "voice_gate_failed", "voice_receipt_invalid"))

    def __init__(self, code="voice_timing_invalid"):
        self.code = code if code in self.CODES else "voice_timing_invalid"
        super().__init__(self.code)

@dataclass(frozen=True)
class Observation:
    ordinal: int
    start_us: int
    end_us: int
    observed_text: str
    mapping_status: MappingStatus
    source_bindings: tuple[SourceBinding, ...] = ()
    variant_evidence_signature: str | None = None
    granularity: str = "LEXICAL"

@dataclass(frozen=True)
class AcceptanceRequest:
    contract_version: str
    request_signature: str
    narration_revision_id: str
    asset_id: str
    sha256: str
    byte_count: int
    inspection: AudioInspectionEvidence
    source_revision_id: str
    source_record_fingerprint: str
    semantic_document_id: str
    semantic_generated_binding: str
    semantic_output_binding: str
    source_bindings: tuple[SourceBinding, ...]
    spec: AlignmentSpec
    spec_signature: str
    input_signature: str
    output_signature: str
    # Canonical complete validated output, immutable, without raw transcript.
    output_payload_json: str
    acceptance_policy_id: str
    acceptance_policy_version: str

class TimingAcceptanceGate(Protocol):
    def accept(self, request: AcceptanceRequest) -> AcceptanceReceipt: ...

@dataclass(frozen=True)
class TimingEligibility:
    historical_validity: bool
    audio_usability: bool
    current_semantic_binding: bool
    current_alignment_spec: bool
    current_acceptance_policy: bool
    active_narration_pointer: bool
    active_alignment_pointer: bool
    complete_coverage: bool

    @property
    def eligible(self):
        return all((self.historical_validity, self.audio_usability,
            self.current_semantic_binding, self.current_alignment_spec,
            self.current_acceptance_policy, self.active_narration_pointer,
            self.active_alignment_pointer))
