"""Project eligible M65 fields without interpretation or narration access."""
from copy import deepcopy
from ..manifest.retrieval import request_payload, request_signature, has_intent
from .models import RetrievalRequest


def build_request(plan, unit, shot, spec):
    return RetrievalRequest(**deepcopy(request_payload(plan, unit, shot, spec)))


def sufficient_intent(request):
    return has_intent(vars(request))
