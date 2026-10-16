from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from creator_studio.project_storage import MediaAssetRecord, scan_media_assets
from creator_studio.scene_assets import load_scene_assignment_state, load_voice_scenes


FINAL_RENDERABLE_FORMAT = "creator_studio_final_renderable_assets_m110_6"
FINAL_RENDERABLE_FILENAME = "final_renderable_assets.json"


class FinalRenderableError(RuntimeError):
    """Controlled M110.6 final renderable-asset resolution failure."""


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(temp_name, target)
    except Exception:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except Exception:
            pass
        raise
    return target


def _load_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        if required:
            raise FileNotFoundError(target)
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FinalRenderableError(f"Không thể đọc {target.name}: {type(exc).__name__}.") from None
    if not isinstance(payload, dict):
        raise FinalRenderableError(f"{target.name} phải chứa JSON object.")
    return payload


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _score(value: Any) -> float | None:
    result = _float(value, None)
    if result is None or result < 0:
        return None
    return max(0.0, min(1.0, result))


def _scene_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("scenes") or []:
        if not isinstance(item, dict):
            continue
        scene_id = str(item.get("scene_id") or item.get("id") or "").strip()
        if scene_id:
            result[scene_id] = item
    return result


def _relative_project_path(project_root: Path, path: Path) -> str:
    root = Path(project_root).resolve()
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def _inside_project(project_root: Path, path: Path) -> bool:
    root = Path(project_root).resolve()
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(root)
        return True
    except ValueError:
        return False


def _ranking_score(scene: dict[str, Any]) -> float | None:
    stock = scene.get("stock") if isinstance(scene.get("stock"), dict) else {}
    return _score(stock.get("score"))


def _research_final(scene_id: str, ranking_scene: dict[str, Any], research_scene: dict[str, Any]) -> tuple[float | None, str, str | None]:
    old_score = _ranking_score(ranking_scene)
    if not research_scene:
        return old_score, "stock_ranked", None

    original = research_scene.get("original") if isinstance(research_scene.get("original"), dict) else {}
    research = research_scene.get("research") if isinstance(research_scene.get("research"), dict) else {}
    decision = research_scene.get("decision") if isinstance(research_scene.get("decision"), dict) else {}
    outcome = str(decision.get("outcome") or "").strip() or None
    accepted = bool(decision.get("accepted_new_asset"))

    if accepted and outcome in {"improved", "render_asset_acquired"}:
        return _score(research.get("score")), "m110_5_research", outcome
    if outcome == "fallback_preserved":
        return _score(original.get("score")) if _score(original.get("score")) is not None else old_score, "m110_5_fallback", outcome
    return old_score, "stock_ranked", outcome


@dataclass(frozen=True)
class FinalRenderableReport:
    total_scene_count: int
    ready_count: int
    unresolved_count: int
    video_count: int
    image_count: int
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_scene_count": self.total_scene_count,
            "ready_count": self.ready_count,
            "unresolved_count": self.unresolved_count,
            "video_count": self.video_count,
            "image_count": self.image_count,
            "manifest_path": self.manifest_path,
        }


class FinalRenderableAssetService:
    """Resolve the exact local project asset that will feed later timeline/render stages.

    M110.6 trusts the current M107 scene-assignment state as the final selection
    pointer, then verifies that every selected M106 asset is local, present and
    technically usable for the scene duration.  YouTube reference metadata is
    never converted to a render asset here.
    """

    def __init__(
        self,
        *,
        project_root: Path,
        run_dir: Path,
        source_scenes_path: Path,
        voice_asset_id: str,
        ranking_manifest_path: Path,
        research_manifest_path: Path | None = None,
        progress_callback: Callable[[int, int, str, str], None] | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.source_scenes_path = Path(source_scenes_path).resolve()
        self.voice_asset_id = str(voice_asset_id or "").strip()
        self.ranking_manifest_path = Path(ranking_manifest_path).resolve()
        self.research_manifest_path = Path(research_manifest_path).resolve() if research_manifest_path else None
        self.progress_callback = progress_callback

    @property
    def output_path(self) -> Path:
        return self.run_dir / FINAL_RENDERABLE_FILENAME

    def run(self) -> FinalRenderableReport:
        if not self.voice_asset_id:
            raise FinalRenderableError("Thiếu Voice Asset ID cho M110.6.")
        if not self.source_scenes_path.is_file():
            raise FileNotFoundError(self.source_scenes_path)
        if not self.ranking_manifest_path.is_file():
            raise FileNotFoundError(self.ranking_manifest_path)

        scenes = load_voice_scenes(self.source_scenes_path)
        ranking_payload = _load_json(self.ranking_manifest_path)
        research_payload = _load_json(self.research_manifest_path, required=False) if self.research_manifest_path else {}
        ranking_by_id = _scene_map(ranking_payload)
        research_by_id = _scene_map(research_payload)

        state = load_scene_assignment_state(
            self.project_root,
            self.voice_asset_id,
            self.source_scenes_path,
        )
        assignments = state.assignment_map()
        assets = {item.asset_id: item for item in scan_media_assets(self.project_root)}

        results: list[dict[str, Any]] = []
        ready_count = 0
        video_count = 0
        image_count = 0
        total = len(scenes)

        for index, scene in enumerate(scenes, start=1):
            scene_id = str(scene.get("id") or f"scene_{index:03d}").strip()
            required_duration = max(0.0, float(scene.get("duration") or (float(scene["end"]) - float(scene["start"]))))
            assignment = assignments.get(scene_id)
            issues: list[str] = []
            asset: MediaAssetRecord | None = None

            if assignment is None:
                issues.append("missing_scene_assignment")
            else:
                asset = assets.get(assignment.asset_id)
                if asset is None:
                    issues.append("assigned_asset_missing_from_library")

            if asset is not None:
                path = asset.media_path.resolve()
                if not _inside_project(self.project_root, path):
                    issues.append("asset_outside_project")
                if not path.is_file() or path.stat().st_size <= 0:
                    issues.append("asset_file_missing_or_empty")
                if assignment is not None and assignment.media_type != asset.media_type:
                    issues.append("assignment_media_type_mismatch")
                if asset.media_type not in {"image", "video"}:
                    issues.append("unsupported_media_type")
                if str(asset.provider_id or "").strip().lower() == "youtube_reference":
                    issues.append("youtube_reference_not_renderable")
                if asset.media_type == "video":
                    duration = _float(asset.duration_seconds, None)
                    if duration is None or duration <= 0:
                        issues.append("video_duration_unknown")
                    elif duration + 0.01 < required_duration:
                        issues.append("video_too_short_for_scene")

            ranking_scene = ranking_by_id.get(scene_id, {})
            research_scene = research_by_id.get(scene_id, {})
            final_score, selection_source, research_outcome = _research_final(
                scene_id,
                ranking_scene,
                research_scene,
            )
            render_eligible = not issues and asset is not None
            if render_eligible:
                ready_count += 1
                if asset.media_type == "video":
                    video_count += 1
                elif asset.media_type == "image":
                    image_count += 1

            result = {
                "scene_id": scene_id,
                "timing": {
                    "start": float(scene["start"]),
                    "end": float(scene["end"]),
                    "duration": required_duration,
                },
                "assignment": {
                    "asset_id": assignment.asset_id if assignment is not None else None,
                    "media_type": assignment.media_type if assignment is not None else None,
                },
                "asset": None if asset is None else {
                    "asset_id": asset.asset_id,
                    "display_name": asset.display_name,
                    "media_type": asset.media_type,
                    "origin": asset.origin,
                    "path": _relative_project_path(self.project_root, asset.media_path),
                    "provider_id": asset.provider_id,
                    "source_reference": asset.source_reference,
                    "width": asset.width,
                    "height": asset.height,
                    "duration_seconds": asset.duration_seconds,
                    "size_bytes": asset.size_bytes,
                },
                "selection": {
                    "score": final_score,
                    "source": selection_source,
                    "research_outcome": research_outcome,
                },
                "render_eligible": render_eligible,
                "issues": issues,
            }
            results.append(result)
            if self.progress_callback is not None:
                self.progress_callback(
                    index,
                    max(1, total),
                    scene_id,
                    "ready" if render_eligible else "unresolved",
                )

        unresolved_count = max(0, total - ready_count)
        payload = {
            "format": FINAL_RENDERABLE_FORMAT,
            "created_at": datetime.now().astimezone().isoformat(),
            "scene_count": total,
            "summary": {
                "ready_count": ready_count,
                "unresolved_count": unresolved_count,
                "video_count": video_count,
                "image_count": image_count,
            },
            "policy": {
                "selection_authority": "m107_scene_assignment_state",
                "asset_catalog": "m106_project_media_library",
                "voice_timing_authority": "voice_scenes.json",
                "youtube_render_policy": "preview_reference_only",
                "local_project_asset_required": True,
                "video_duration_must_cover_scene": True,
            },
            "source": {
                "voice_scenes": _relative_project_path(self.project_root, self.source_scenes_path),
                "ranking_manifest": self.ranking_manifest_path.name,
                "research_manifest": (
                    self.research_manifest_path.name
                    if self.research_manifest_path is not None and self.research_manifest_path.is_file()
                    else None
                ),
            },
            "scenes": results,
        }
        _atomic_json_write(self.output_path, payload)
        return FinalRenderableReport(
            total_scene_count=total,
            ready_count=ready_count,
            unresolved_count=unresolved_count,
            video_count=video_count,
            image_count=image_count,
            manifest_path=str(self.output_path),
        )
