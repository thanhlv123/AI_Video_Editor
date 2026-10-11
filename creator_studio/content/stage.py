"""M62 adapter: parsing stays in ingest; only successful proposals are returned."""
from copy import deepcopy
import json
from ..manifest.codec import to_data
from ..manifest.signatures import signature
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus)
from .models import IngestLimits, IngestStatus
from .ingest import ingest, apply_ingest
from .normalization import IngestError


class ContentIngestStage:
    stage_id = "content_ingest"
    stage_version = "1"
    dependencies = ()

    def __init__(self, request, *, limits=IngestLimits(), canonical=True):
        self.request = deepcopy(request)
        self.limits = limits
        self.canonical = canonical
        self._expected = None

    def _inputs(self, result):
        # Original formatting and locator matter to the persisted output, even
        # when semantic revision identity is unchanged. Only hashes reach M62.
        # ASCII escaping preserves exact Unicode code points despite M61's NFC
        # signature normalization, essential for original_text preservation.
        return {"request": signature(json.dumps(to_data(self.request), ensure_ascii=True, sort_keys=True)),
                "limits": signature(self.limits),
                "result": signature(json.dumps(to_data(result), ensure_ascii=True, sort_keys=True)),
                "canonical": self.canonical}

    def signature_inputs(self, manifest):
        self._expected = self._inputs(ingest(self.request, self.limits))
        return deepcopy(self._expected)

    def _output_fingerprint(self, record, manifest=None):
        output = {"record": to_data(record), "canonical": self.canonical}
        if self.canonical:
            output.update(canonical_content_id=(manifest.content.canonical_content_id
                          if manifest else record.content_id),
                          script=manifest.content.script if manifest else record.normalized_text,
                          source_language=(manifest.content.source_language
                          if manifest else record.language or "und"))
        return signature(json.dumps(output, ensure_ascii=True, sort_keys=True))

    def validate_reuse(self, manifest, previous):
        expected = ingest(self.request, self.limits)
        if expected.status != IngestStatus.SUCCESS:
            return False
        record = next((r for r in manifest.content.records
                       if r.content_id == expected.content.content_id), None)
        if record is None:
            return False
        fingerprint = self._output_fingerprint(expected.content)
        return (previous.artifacts == [Artifact("content/" + record.content_id, fingerprint)]
                and self._output_fingerprint(record, manifest) == fingerprint)

    def _diagnostics(self, codes):
        return [Diagnostic(code=code, stage_id=self.stage_id,
                           message="Content ingest requires attention.") for code in codes]

    def _update_diagnostics(self, error):
        diagnostics = self._diagnostics([error.code])
        if error.code == "scene_script_span_changed":
            diagnostics[0].context = ["scene_id=" + error.scene_id,
                                      "span_start=" + str(error.span_start),
                                      "span_end=" + str(error.span_end)]
        return diagnostics

    def readiness(self, manifest):
        result = ingest(self.request, self.limits)
        if result.status == IngestStatus.FAILURE:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics(d.code for d in result.diagnostics)))
        try:
            apply_ingest(manifest, result, canonical=self.canonical)
        except IngestError as exc:
            return Readiness(ReadinessKind.BLOCKED, tuple(self._update_diagnostics(exc)))
        return Readiness()

    def execute(self, context):
        context.cancellation.check()
        result = ingest(self.request, self.limits)
        if self._expected is not None and self._inputs(result) != self._expected:
            return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                diagnostics=self._diagnostics(["source_changed"])))
        if result.status == IngestStatus.FAILURE:
            return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                diagnostics=self._diagnostics(d.code for d in result.diagnostics)))
        try:
            proposed = apply_ingest(context.manifest, result, canonical=self.canonical)
        except IngestError as exc:
            return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                diagnostics=self._update_diagnostics(exc)))
        context.cancellation.check()
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
            artifacts=[Artifact("content/" + result.content.content_id, self._output_fingerprint(result.content, proposed))],
            diagnostics=self._diagnostics(d.code for d in result.diagnostics)),
            ManifestUpdate(proposed))
