"""M105 project-local storage and voice asset library helpers.

This module intentionally has no PyQt dependency.  It defines filesystem layout
and durable sidecar metadata for user-visible project assets.  ProjectManifest
remains the authority for the *active* voice; this catalog preserves all created
or imported voice files without overwriting them.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_MANIFEST_FILENAME = "project_manifest.json"
ASSETS_DIRNAME = "assets"
VOICE_ASSETS_DIRNAME = "voice"
VOICE_GENERATED_DIRNAME = "generated"
VOICE_IMPORTED_DIRNAME = "imported"
WORK_DIRNAME = "work"
VOICE_WORK_DIRNAME = "voice"
SCRIPTS_DIRNAME = "scripts"
EXPORTS_DIRNAME = "exports"
CACHE_DIRNAME = "cache"
VOICE_ASSET_META_SUFFIX = ".asset.json"


class ProjectStorageError(RuntimeError):
    """Controlled project-storage failure."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def safe_slug(value: str, fallback: str = "project", max_len: int = 72) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_text).strip("._-")
    return (slug or fallback)[:max_len]


def project_root_from_manifest(manifest_path: Path) -> Path:
    return Path(manifest_path).resolve().parent


def initialize_project_layout(project_root: Path) -> dict[str, Path]:
    root = Path(project_root).resolve()
    directories = {
        "root": root,
        "scripts": root / SCRIPTS_DIRNAME,
        "assets": root / ASSETS_DIRNAME,
        "voice_assets": root / ASSETS_DIRNAME / VOICE_ASSETS_DIRNAME,
        "voice_generated": root / ASSETS_DIRNAME / VOICE_ASSETS_DIRNAME / VOICE_GENERATED_DIRNAME,
        "voice_imported": root / ASSETS_DIRNAME / VOICE_ASSETS_DIRNAME / VOICE_IMPORTED_DIRNAME,
        "work": root / WORK_DIRNAME,
        "voice_work": root / WORK_DIRNAME / VOICE_WORK_DIRNAME,
        "exports": root / EXPORTS_DIRNAME,
        "cache": root / CACHE_DIRNAME,
    }
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return directories


def create_project_root(parent_dir: Path, project_name: str) -> Path:
    parent = Path(parent_dir).expanduser().resolve()
    if not parent.exists() or not parent.is_dir():
        raise ProjectStorageError(f"Thư mục lưu dự án không tồn tại: {parent}")

    folder_name = safe_slug(project_name, "project")
    project_root = parent / folder_name
    if project_root.exists():
        raise FileExistsError(
            f"Thư mục dự án đã tồn tại: {project_root}. "
            "Hãy đổi tên dự án hoặc chọn nơi lưu khác."
        )

    project_root.mkdir(parents=False, exist_ok=False)
    try:
        initialize_project_layout(project_root)
    except Exception:
        shutil.rmtree(project_root, ignore_errors=True)
        raise
    return project_root


def voice_assets_root(project_root: Path) -> Path:
    return initialize_project_layout(project_root)["voice_assets"]


def voice_generated_root(project_root: Path) -> Path:
    return initialize_project_layout(project_root)["voice_generated"]


def voice_imported_root(project_root: Path) -> Path:
    return initialize_project_layout(project_root)["voice_imported"]


def voice_work_root(project_root: Path) -> Path:
    return initialize_project_layout(project_root)["voice_work"]


def _asset_metadata_path(audio_path: Path) -> Path:
    audio_path = Path(audio_path)
    return audio_path.with_name(audio_path.name + VOICE_ASSET_META_SUFFIX)


def _unique_audio_path(folder: Path, base_name: str, suffix: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    candidate = folder / f"{base_name}{suffix.lower()}"
    index = 2
    while candidate.exists() or _asset_metadata_path(candidate).exists():
        candidate = folder / f"{base_name}_{index:02d}{suffix.lower()}"
        index += 1
    return candidate


@dataclass(frozen=True)
class VoiceAssetRecord:
    asset_id: str
    display_name: str
    kind: str
    path: str
    created_at: str
    provider_id: str | None = None
    model_id: str | None = None
    voice_id: str | None = None
    language: str | None = None
    speed: float | None = None
    duration_seconds: float | None = None
    source_reference: str | None = None
    size_bytes: int | None = None

    @property
    def audio_path(self) -> Path:
        return Path(self.path)

    @property
    def metadata_path(self) -> Path:
        return _asset_metadata_path(self.audio_path)


def new_generated_voice_target(
    project_root: Path,
    *,
    provider_id: str,
    model_id: str | None,
    voice_id: str,
) -> VoiceAssetRecord:
    folder = voice_generated_root(project_root)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    asset_id = f"voice_{uuid.uuid4().hex[:12]}"
    parts = [
        stamp,
        safe_slug(provider_id, "tts", 28),
        safe_slug(model_id or "", "", 28),
        safe_slug(voice_id, "voice", 36),
        asset_id[-6:],
    ]
    base = "_".join(part for part in parts if part)
    path = _unique_audio_path(folder, base, ".wav")
    return VoiceAssetRecord(
        asset_id=asset_id,
        display_name=path.stem,
        kind="generated",
        path=str(path),
        created_at=now_iso(),
        provider_id=provider_id or None,
        model_id=model_id or None,
        voice_id=voice_id or None,
    )


def finalize_voice_asset(
    record: VoiceAssetRecord,
    *,
    language: str | None = None,
    speed: float | None = None,
    duration_seconds: float | None = None,
) -> VoiceAssetRecord:
    path = record.audio_path.resolve()
    if not path.is_file() or path.stat().st_size <= 0:
        raise ProjectStorageError(f"Tệp voice asset không hợp lệ: {path}")

    finalized = VoiceAssetRecord(
        asset_id=record.asset_id,
        display_name=record.display_name,
        kind=record.kind,
        path=str(path),
        created_at=record.created_at,
        provider_id=record.provider_id,
        model_id=record.model_id,
        voice_id=record.voice_id,
        language=language if language is not None else record.language,
        speed=float(speed) if speed is not None else record.speed,
        duration_seconds=(
            float(duration_seconds) if duration_seconds is not None else record.duration_seconds
        ),
        source_reference=record.source_reference,
        size_bytes=int(path.stat().st_size),
    )
    _write_record(finalized)
    return finalized


def import_voice_asset(
    project_root: Path,
    source_path: Path,
    *,
    display_name: str | None = None,
) -> VoiceAssetRecord:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    folder = voice_imported_root(project_root)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    asset_id = f"voice_{uuid.uuid4().hex[:12]}"
    label = safe_slug(display_name or source.stem, "imported_voice", 52)
    base = f"{stamp}_{label}_{asset_id[-6:]}"
    target = _unique_audio_path(folder, base, source.suffix or ".wav")
    shutil.copy2(source, target)

    record = VoiceAssetRecord(
        asset_id=asset_id,
        display_name=display_name or source.stem,
        kind="imported",
        path=str(target.resolve()),
        created_at=now_iso(),
        source_reference=str(source),
        size_bytes=int(target.stat().st_size),
    )
    _write_record(record)
    return record


def _write_record(record: VoiceAssetRecord) -> None:
    meta_path = record.metadata_path
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "creator_studio_voice_asset_m105_v1",
        **asdict(record),
    }
    temp = meta_path.with_name(meta_path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(meta_path)


def read_voice_asset_metadata(metadata_path: Path) -> VoiceAssetRecord:
    path = Path(metadata_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProjectStorageError(f"Metadata voice asset không hợp lệ: {path}")
    required = ("asset_id", "display_name", "kind", "path", "created_at")
    if any(not payload.get(key) for key in required):
        raise ProjectStorageError(f"Metadata voice asset thiếu trường bắt buộc: {path}")
    return VoiceAssetRecord(
        asset_id=str(payload["asset_id"]),
        display_name=str(payload["display_name"]),
        kind=str(payload["kind"]),
        path=str(payload["path"]),
        created_at=str(payload["created_at"]),
        provider_id=_optional_str(payload.get("provider_id")),
        model_id=_optional_str(payload.get("model_id")),
        voice_id=_optional_str(payload.get("voice_id")),
        language=_optional_str(payload.get("language")),
        speed=_optional_float(payload.get("speed")),
        duration_seconds=_optional_float(payload.get("duration_seconds")),
        source_reference=_optional_str(payload.get("source_reference")),
        size_bytes=_optional_int(payload.get("size_bytes")),
    )


def _optional_str(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def scan_voice_assets(project_root: Path) -> list[VoiceAssetRecord]:
    root = voice_assets_root(project_root)
    records: list[VoiceAssetRecord] = []
    known_paths: set[Path] = set()

    for metadata_path in sorted(root.rglob(f"*{VOICE_ASSET_META_SUFFIX}")):
        try:
            record = read_voice_asset_metadata(metadata_path)
            audio_path = record.audio_path.resolve()
            if not audio_path.is_file():
                continue
            known_paths.add(audio_path)
            if record.size_bytes != audio_path.stat().st_size:
                record = VoiceAssetRecord(
                    **{**asdict(record), "size_bytes": int(audio_path.stat().st_size)}
                )
            records.append(record)
        except Exception:
            continue

    supported = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
    for audio_path in sorted(root.rglob("*")):
        if not audio_path.is_file() or audio_path.suffix.lower() not in supported:
            continue
        resolved = audio_path.resolve()
        if resolved in known_paths:
            continue
        stat = audio_path.stat()
        records.append(
            VoiceAssetRecord(
                asset_id=f"orphan_{uuid.uuid5(uuid.NAMESPACE_URL, str(resolved)).hex[:12]}",
                display_name=audio_path.stem,
                kind="unindexed",
                path=str(resolved),
                created_at=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                size_bytes=int(stat.st_size),
            )
        )

    records.sort(key=lambda item: item.created_at, reverse=True)
    return records


def find_voice_asset_by_path(project_root: Path, audio_path: Path) -> VoiceAssetRecord | None:
    wanted = Path(audio_path).resolve()
    for record in scan_voice_assets(project_root):
        try:
            if record.audio_path.resolve() == wanted:
                return record
        except Exception:
            continue
    return None


def create_voice_work_run(project_root: Path, asset_id: str) -> Path:
    root = voice_work_root(project_root) / safe_slug(asset_id, "voice_asset", 64)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    run_dir = root / f"run_{stamp}"
    suffix = 2
    while run_dir.exists():
        run_dir = root / f"run_{stamp}_{suffix:02d}"
        suffix += 1
    run_dir.mkdir(parents=False, exist_ok=False)
    return run_dir
