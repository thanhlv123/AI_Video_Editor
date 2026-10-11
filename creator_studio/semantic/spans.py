"""Exact code-point evidence validation; never repair spans."""
from ..manifest.semantic_validation import valid_span


class SemanticError(ValueError):
    def __init__(self, code="semantic_output_invalid"):
        from ..manifest.semantic_validation import DIAGNOSTIC_CODES
        self.code = code if code in DIAGNOSTIC_CODES else "semantic_output_invalid"
        super().__init__(self.code)


def require_slice(text, span, source_text):
    if not valid_span(span, text):
        raise SemanticError("semantic_span_invalid")
    if text[span.start:span.end] != source_text:
        raise SemanticError("semantic_source_text_mismatch")
