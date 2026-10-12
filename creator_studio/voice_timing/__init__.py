"""Offline narration timing foundation; inject storage and an acceptance gate."""
from .models import Observation, AcceptanceRequest, TimingAcceptanceGate, TimingEligibility, VoiceTimingError
from .storage import NarrationByteStore, LocalNarrationByteStore
from .inspector import inspect_stream, verify_audio
from .engine import register_narration, build_voice_timing, current_timing_eligibility, source_binding
from .stage import VoiceTimingStage
