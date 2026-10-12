"""Controlled M67 operation failures."""

ERROR_CODES = frozenset({"selection_contract_invalid", "selection_retrieval_stale",
    "selection_spec_invalid", "selection_limit_exceeded", "selection_review_required",
    "selection_expected_state_mismatch", "selection_boundary_invalid"})


class SelectionError(ValueError):
    def __init__(self, code):
        self.code = code if type(code) is str and code in ERROR_CODES else "selection_contract_invalid"
        super().__init__(self.code)
