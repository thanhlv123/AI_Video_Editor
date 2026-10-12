"""Offline editorial placement timing foundation; no default acceptance gate."""
from .models import (PlacementTimingAcceptanceRequest, PlacementTimingAcceptanceGate,
    PlacementTimingEligibility, PlacementTimingError)
from .engine import build_placement_timing, current_placement_timing_eligibility
from .stage import PlacementTimingStage
