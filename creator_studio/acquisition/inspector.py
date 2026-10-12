"""Trusted injected inspector boundary. No production adapter in M68."""
from typing import Protocol
from ..manifest.acquisition import InspectionFacts
from .models import AcquisitionError


class MediaInspector(Protocol):
    inspector_id: str
    inspector_version: str
    policy_id: str
    policy_version: str

    def inspect(self, path, control) -> InspectionFacts: ...


class UnavailableInspector:
    inspector_id = "unavailable"
    inspector_version = "1"
    policy_id = "objective_media"
    policy_version = "1"

    def inspect(self, path, control):
        raise AcquisitionError("acquisition_inspection_failed")


def inspect_media(inspector, path, kind, spec, control):
    from ..manifest.acquisition_validation import inspection_valid
    from ..orchestrator.contracts import Cancelled
    control.check()
    try:
        facts = inspector.inspect(path, control)
        control.check()
        if (not inspection_valid(facts) or facts.media_kind != kind
                or (facts.inspector_id, facts.inspector_version) !=
                   (inspector.inspector_id, inspector.inspector_version)
                or (facts.policy_id, facts.policy_version) !=
                   (spec.inspection_policy_id, spec.inspection_policy_version)
                or (inspector.policy_id, inspector.policy_version) !=
                   (spec.inspection_policy_id, spec.inspection_policy_version)):
            raise AcquisitionError("acquisition_inspection_failed")
        return facts
    except Cancelled:
        raise
    except Exception:
        raise AcquisitionError("acquisition_inspection_failed") from None
