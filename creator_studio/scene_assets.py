"""M107.1 scene-to-media assignment foundation.

This module keeps manual scene/media choices outside canonical ProjectManifest
media/timeline state.  It binds each assignment file to one exact VoicePipeline
``voice_scenes.json`` source via SHA-256 and stores assignments by stable
M106 media asset IDs.

No rendering, timing authority creation, media mutation, or manifest promotion
happens here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .project_storage import MediaAssetRecord, safe_slug, scan_media_assets, voice_work_root


SCENE_ASSET_WORK_DIRNAME = "scene_assets"
SCENE_ASSIGNMENT_FILENAME = "scene_asset_assignments.json"
SCENE_ASSIGNMENT_FORMAT = "creator_studio_scene_asset_assignments_m107_1_v1"


class SceneAssetAssignmentError(RuntimeError):
    """Controlled scene-assignment failure."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_project_path(project_root: Path, path: Path) -> str:
    root = Path(project_root).resolve()
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError as exc:
        raise SceneAssetAssignmentError(
            f"Tệp nguồn cảnh phải nằm trong project: {resolved}"
        ) from exc


@dataclass(frozen=True)
class SceneAssetAssignment:
    scene_id: str
    asset_id: str
    media_type: str
    assigned_at: str


@dataclass(frozen=True)
class SceneAssetAssignmentState:
    format: str
    source_voice_asset_id: str
    source_scenes_relpath: str
    source_scenes_sha256: str
    created_at: str
    updated_at: str
    assignments: tuple[SceneAssetAssignment, ...] = ()

    def assignment_map(self) -> dict[str, SceneAssetAssignment]:
        return {item.scene_id: item for item in self.assignments}


def load_voice_scenes(source_scenes_path: Path) -> list[dict[str, Any]]:
    source = Path(source_scenes_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SceneAssetAssignmentError("voice_scenes.json phải chứa một danh sách cảnh.")

    scenes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            raise SceneAssetAssignmentError(f"Cảnh #{index} không phải object JSON.")
        scene_id = str(raw.get("id", "") or "").strip()
        if not scene_id:
            raise SceneAssetAssignmentError(f"Cảnh #{index} thiếu id.")
        if scene_id in seen_ids:
            raise SceneAssetAssignmentError(f"Scene id bị trùng: {scene_id}")
        seen_ids.add(scene_id)

        start = raw.get("start")
        end = raw.get("end")
        if isinstance(start, bool) or isinstance(end, bool):
            raise SceneAssetAssignmentError(f"Thời gian cảnh {scene_id} không hợp lệ.")
        try:
            start_f = float(start)
            end_f = float(end)
        except (TypeError, ValueError) as exc:
            raise SceneAssetAssignmentError(
                f"Cảnh {scene_id} thiếu start/end hợp lệ."
            ) from exc
        if start_f < 0 or end_f <= start_f:
            raise SceneAssetAssignmentError(
                f"Khoảng thời gian cảnh {scene_id} không hợp lệ: {start_f} -> {end_f}"
            )

        scenes.append(
            {
                "id": scene_id,
                "start": start_f,
                "end": end_f,
                "duration": float(raw.get("duration", end_f - start_f) or (end_f - start_f)),
                "text": str(raw.get("text", "") or ""),
                "scene_type": str(raw.get("scene_type", "speech") or "speech"),
            }
        )
    return scenes


def latest_voice_scenes_path(project_root: Path, voice_asset_id: str) -> Path | None:
    root = voice_work_root(project_root) / safe_slug(voice_asset_id, "voice_asset", 64)
    if not root.is_dir():
        return None

    candidates = [p for p in root.rglob("voice_scenes.json") if p.is_file()]
    if not candidates:
        return None

    def key(path: Path):
        try:
            stat = path.stat()
            return (stat.st_mtime_ns, str(path).lower())
        except OSError:
            return (0, str(path).lower())

    return max(candidates, key=key)


def scene_assignment_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "work" / SCENE_ASSET_WORK_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def scene_assignment_state_path(
    project_root: Path,
    voice_asset_id: str,
    source_scenes_path: Path,
) -> Path:
    source = Path(source_scenes_path).resolve()
    source_hash = _sha256_file(source)
    run_name = safe_slug(source.parent.name, "run", 72)
    voice_part = safe_slug(voice_asset_id, "voice_asset", 64)
    state_dir = scene_assignment_root(project_root) / voice_part / f"{run_name}_{source_hash[:10]}"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / SCENE_ASSIGNMENT_FILENAME


def _new_state(
    project_root: Path,
    voice_asset_id: str,
    source_scenes_path: Path,
) -> SceneAssetAssignmentState:
    source = Path(source_scenes_path).resolve()
    load_voice_scenes(source)  # strict validation before creating state
    stamp = now_iso()
    return SceneAssetAssignmentState(
        format=SCENE_ASSIGNMENT_FORMAT,
        source_voice_asset_id=str(voice_asset_id),
        source_scenes_relpath=_relative_project_path(project_root, source),
        source_scenes_sha256=_sha256_file(source),
        created_at=stamp,
        updated_at=stamp,
        assignments=(),
    )


def _write_state(path: Path, state: SceneAssetAssignmentState) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": state.format,
        "source_voice_asset_id": state.source_voice_asset_id,
        "source_scenes_relpath": state.source_scenes_relpath,
        "source_scenes_sha256": state.source_scenes_sha256,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "assignments": [asdict(item) for item in state.assignments],
    }
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def _read_state(path: Path) -> SceneAssetAssignmentState:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SceneAssetAssignmentError("Tệp assignment không phải object JSON.")
    if payload.get("format") != SCENE_ASSIGNMENT_FORMAT:
        raise SceneAssetAssignmentError("Định dạng assignment không được hỗ trợ.")

    items = payload.get("assignments", [])
    if not isinstance(items, list):
        raise SceneAssetAssignmentError("assignments phải là danh sách.")

    assignments: list[SceneAssetAssignment] = []
    seen_scene_ids: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise SceneAssetAssignmentError("Một assignment không hợp lệ.")
        scene_id = str(raw.get("scene_id", "") or "").strip()
        asset_id = str(raw.get("asset_id", "") or "").strip()
        media_type = str(raw.get("media_type", "") or "").strip().lower()
        assigned_at = str(raw.get("assigned_at", "") or "").strip()
        if not scene_id or not asset_id or media_type not in {"image", "video"} or not assigned_at:
            raise SceneAssetAssignmentError("Assignment thiếu trường bắt buộc.")
        if scene_id in seen_scene_ids:
            raise SceneAssetAssignmentError(f"Scene assignment bị trùng: {scene_id}")
        seen_scene_ids.add(scene_id)
        assignments.append(
            SceneAssetAssignment(
                scene_id=scene_id,
                asset_id=asset_id,
                media_type=media_type,
                assigned_at=assigned_at,
            )
        )

    return SceneAssetAssignmentState(
        format=SCENE_ASSIGNMENT_FORMAT,
        source_voice_asset_id=str(payload.get("source_voice_asset_id", "") or ""),
        source_scenes_relpath=str(payload.get("source_scenes_relpath", "") or ""),
        source_scenes_sha256=str(payload.get("source_scenes_sha256", "") or ""),
        created_at=str(payload.get("created_at", "") or ""),
        updated_at=str(payload.get("updated_at", "") or ""),
        assignments=tuple(assignments),
    )


def load_scene_assignment_state(
    project_root: Path,
    voice_asset_id: str,
    source_scenes_path: Path,
) -> SceneAssetAssignmentState:
    path = scene_assignment_state_path(project_root, voice_asset_id, source_scenes_path)
    if not path.is_file():
        return _new_state(project_root, voice_asset_id, source_scenes_path)

    state = _read_state(path)
    source = Path(source_scenes_path).resolve()
    current_hash = _sha256_file(source)
    expected_relpath = _relative_project_path(project_root, source)
    if state.source_voice_asset_id != str(voice_asset_id):
        raise SceneAssetAssignmentError("Assignment không khớp Voice Asset hiện tại.")
    if state.source_scenes_relpath != expected_relpath:
        raise SceneAssetAssignmentError("Assignment không khớp nguồn voice_scenes.json.")
    if state.source_scenes_sha256 != current_hash:
        raise SceneAssetAssignmentError("voice_scenes.json đã thay đổi sau khi assignment được tạo.")

    valid_scene_ids = {item["id"] for item in load_voice_scenes(source)}
    for item in state.assignments:
        if item.scene_id not in valid_scene_ids:
            raise SceneAssetAssignmentError(
                f"Assignment tham chiếu scene không tồn tại: {item.scene_id}"
            )
    return state


def _find_asset(project_root: Path, asset_id: str) -> MediaAssetRecord:
    for record in scan_media_assets(project_root):
        if record.asset_id == asset_id:
            return record
    raise SceneAssetAssignmentError(f"Không tìm thấy Media Asset: {asset_id}")


def assign_media_asset(
    project_root: Path,
    voice_asset_id: str,
    source_scenes_path: Path,
    scene_id: str,
    media_asset_id: str,
) -> SceneAssetAssignmentState:
    project_root = Path(project_root).resolve()
    scenes = load_voice_scenes(source_scenes_path)
    valid_scene_ids = {item["id"] for item in scenes}
    scene_id = str(scene_id or "").strip()
    if scene_id not in valid_scene_ids:
        raise SceneAssetAssignmentError(f"Scene không tồn tại: {scene_id}")

    asset = _find_asset(project_root, media_asset_id)
    state = load_scene_assignment_state(project_root, voice_asset_id, source_scenes_path)
    mapping = state.assignment_map()
    mapping[scene_id] = SceneAssetAssignment(
        scene_id=scene_id,
        asset_id=asset.asset_id,
        media_type=asset.media_type,
        assigned_at=now_iso(),
    )
    ordered = tuple(mapping[key] for key in sorted(mapping))
    updated = SceneAssetAssignmentState(
        format=state.format,
        source_voice_asset_id=state.source_voice_asset_id,
        source_scenes_relpath=state.source_scenes_relpath,
        source_scenes_sha256=state.source_scenes_sha256,
        created_at=state.created_at,
        updated_at=now_iso(),
        assignments=ordered,
    )
    _write_state(
        scene_assignment_state_path(project_root, voice_asset_id, source_scenes_path),
        updated,
    )
    return updated


def remove_scene_assignment(
    project_root: Path,
    voice_asset_id: str,
    source_scenes_path: Path,
    scene_id: str,
) -> SceneAssetAssignmentState:
    project_root = Path(project_root).resolve()
    state = load_scene_assignment_state(project_root, voice_asset_id, source_scenes_path)
    scene_id = str(scene_id or "").strip()
    remaining = tuple(item for item in state.assignments if item.scene_id != scene_id)
    updated = SceneAssetAssignmentState(
        format=state.format,
        source_voice_asset_id=state.source_voice_asset_id,
        source_scenes_relpath=state.source_scenes_relpath,
        source_scenes_sha256=state.source_scenes_sha256,
        created_at=state.created_at,
        updated_at=now_iso(),
        assignments=remaining,
    )
    _write_state(
        scene_assignment_state_path(project_root, voice_asset_id, source_scenes_path),
        updated,
    )
    return updated
