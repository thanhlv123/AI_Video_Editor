"""Immutable metadata describing a separately persisted recoverable manifest."""
from .models import SnapshotMetadata, new_id, utc_now
from .signatures import signature
from .validation import require_valid


def snapshot_metadata(manifest, label: str, manifest_reference: str, parent_snapshot_id=None):
    require_valid(manifest)
    if not manifest_reference.strip():
        raise ValueError("Snapshot requires a recovery reference")
    if parent_snapshot_id is not None and parent_snapshot_id not in {s.id for s in manifest.snapshots}:
        raise ValueError("Unknown parent snapshot")
    return SnapshotMetadata(new_id(), manifest.project_id, utc_now(), label,
                            manifest.schema_version, signature(manifest),
                            manifest_reference, parent_snapshot_id)
