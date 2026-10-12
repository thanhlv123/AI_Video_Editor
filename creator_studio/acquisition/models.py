"""Closed runtime failures: external exception text is never retained."""
ERROR_CODES = frozenset("""acquisition_provider_failed acquisition_timeout
acquisition_unsupported acquisition_validation_failed acquisition_storage_failed
acquisition_limit_exceeded acquisition_selection_stale acquisition_review_rejected
acquisition_inspection_failed acquisition_boundary_invalid acquisition_collision""".split())


class AcquisitionError(Exception):
    def __init__(self, code):
        self.code = code if code in ERROR_CODES else "acquisition_validation_failed"
        super().__init__(self.code)
