"""Strict streaming RIFF subset. Hash and inspection describe the same read."""
from dataclasses import replace
import hashlib
import struct
from ..manifest.voice_timing import (NarrationAsset, AudioInspectionEvidence,
    MAX_BYTES, MAX_SECONDS, READ_CHUNK, RATES, inspection_signature)
from ..manifest.voice_timing_validation import validate_inspection
from ..orchestrator.contracts import CancellationToken, Cancelled
from .models import VoiceTimingError

def inspect_stream(stream, *, control=None):
    control = control or CancellationToken()
    digest = hashlib.sha256()
    total = 0

    def read_exact(size):
        nonlocal total
        # Only headers or a single bounded payload chunk enter this function.
        if not 0 <= size <= READ_CHUNK or total + size > MAX_BYTES:
            raise VoiceTimingError("voice_audio_unusable")
        parts = []
        remaining = size
        while remaining:
            control.check()
            data = stream.read(remaining)
            if type(data) is not bytes or not data or len(data) > remaining:
                raise VoiceTimingError("voice_audio_unusable")
            digest.update(data)
            total += len(data)
            remaining -= len(data)
            parts.append(data)
            control.check()
        return b"".join(parts)

    try:
        control.check()
        riff, declared, wave = struct.unpack("<4sI4s", read_exact(12))
        if riff != b"RIFF" or wave != b"WAVE" or not 37 <= declared <= MAX_BYTES - 8:
            raise ValueError()
        fmt, length = struct.unpack("<4sI", read_exact(8))
        if fmt != b"fmt " or length != 16:
            raise ValueError()
        tag, channels, rate, byte_rate, align, bits = struct.unpack("<HHIIHH", read_exact(16))
        if tag != 1 or channels not in (1, 2) or rate not in RATES or bits not in (8, 16, 24, 32):
            raise ValueError()
        width = bits // 8
        if align != channels * width or byte_rate != rate * align:
            raise ValueError()
        kind, size = struct.unpack("<4sI", read_exact(8))
        if kind != b"data" or size == 0 or size % align or 44 + size + size % 2 != declared + 8:
            raise ValueError()
        frames = size // align
        if frames > MAX_SECONDS * rate:
            raise ValueError()
        remaining = size
        while remaining:
            control.check()
            chunk = min(remaining, READ_CHUNK)
            read_exact(chunk)
            remaining -= chunk
        if size % 2 and read_exact(1) != b"\x00":
            raise ValueError()
        control.check()
        if stream.read(1) != b"" or total != declared + 8:
            raise ValueError()
        sha = digest.hexdigest()
        asset = NarrationAsset("asset:sha256:" + sha, sha, total)
        evidence = AudioInspectionEvidence(asset.asset_id, sha, total, tag, channels,
            bits, width, rate, align, byte_rate, size, frames, frames * 1000000 // rate)
        evidence = replace(evidence, evidence_signature=inspection_signature(evidence))
        validate_inspection(evidence)
        control.check()
        return asset, evidence
    except Cancelled:
        raise
    except Exception:
        raise VoiceTimingError("voice_audio_unusable") from None

def verify_audio(store, asset, *, expected_inspection=None, control=None):
    try:
        with store.open_read(asset.asset_id) as stream:
            actual, inspection = inspect_stream(stream, control=control)
        if actual != asset or (expected_inspection is not None and inspection != expected_inspection):
            raise ValueError()
        return inspection
    except Cancelled:
        raise
    except Exception:
        raise VoiceTimingError("voice_audio_unusable") from None
