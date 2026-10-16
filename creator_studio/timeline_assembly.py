from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from creator_studio.project_storage import scan_voice_assets
from creator_studio.scene_assets import load_voice_scenes


TIMELINE_FORMAT = "creator_studio_timeline_m113"
TIMELINE_FILENAME = "timeline_manifest.json"


class TimelineAssemblyError(RuntimeError):
    """Controlled M113 automatic timeline assembly failure."""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
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


def _project_relative(project_root: Path, path: Path) -> str:
    root = Path(project_root).resolve()
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except Exception as exc:
        raise TimelineAssemblyError(f"Tệp timeline phải nằm trong project: {resolved}") from exc


def _project_path(project_root: Path, value: str) -> Path:
    root = Path(project_root).resolve()
    raw = Path(str(value or ""))
    path = raw if raw.is_absolute() else root / raw
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except Exception as exc:
        raise TimelineAssemblyError(f"Timeline không được tham chiếu tệp ngoài project: {resolved}") from exc
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TimelineAssemblyError(f"JSON phải là object: {path}")
    return payload


def _float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _resolve_voice_asset(project_root: Path, voice_asset_id: str):
    wanted = str(voice_asset_id or "").strip()
    if not wanted:
        raise TimelineAssemblyError("M113 thiếu voice_asset_id của narration.")
    for record in scan_voice_assets(project_root):
        if str(record.asset_id) == wanted:
            path = record.audio_path.resolve()
            if not path.is_file() or path.stat().st_size <= 0:
                raise TimelineAssemblyError(f"Voice Asset không còn tệp audio hợp lệ: {wanted}")
            return record
    raise TimelineAssemblyError(f"Không tìm thấy Voice Asset trong project: {wanted}")


@dataclass(frozen=True)
class TimelineAssemblyReport:
    status: str
    scene_count: int
    visual_clip_count: int
    gap_fill_count: int
    duration_seconds: float
    music_included: bool
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutomaticTimelineAssemblyService:
    """Build a render-neutral, voice-authoritative timeline manifest.

    M113 does not render, transcode, stretch narration, loop scene video, or
    mutate source assets.  It binds the exact M110.6 render assets to the exact
    VoicePipeline scene timing, attaches M112 music instructions, and records
    deterministic operations for M114 FFmpeg rendering.
    """

    def __init__(
        self,
        *,
        project_root: Path,
        run_dir: Path,
        source_scenes_path: Path,
        voice_asset_id: str,
        final_renderable_manifest_path: Path,
        music_selection_manifest_path: Path,
        progress_callback: Callable[[int, int, str, str], None] | None = None,
        timing_tolerance_seconds: float = 0.05,
    ):
        self.project_root = Path(project_root).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.source_scenes_path = Path(source_scenes_path).resolve()
        self.voice_asset_id = str(voice_asset_id or "")
        self.final_renderable_manifest_path = Path(final_renderable_manifest_path).resolve()
        self.music_selection_manifest_path = Path(music_selection_manifest_path).resolve()
        self.progress_callback = progress_callback
        self.timing_tolerance_seconds = max(0.001, float(timing_tolerance_seconds))

    @property
    def output_path(self) -> Path:
        return self.run_dir / TIMELINE_FILENAME

    def _validate_sources(self):
        if not self.source_scenes_path.is_file():
            raise FileNotFoundError(self.source_scenes_path)
        if not self.final_renderable_manifest_path.is_file():
            raise FileNotFoundError(self.final_renderable_manifest_path)
        if not self.music_selection_manifest_path.is_file():
            raise FileNotFoundError(self.music_selection_manifest_path)
        try:
            self.run_dir.relative_to(self.project_root)
        except Exception as exc:
            raise TimelineAssemblyError("run_dir của M113 phải nằm trong project.") from exc

    def _load_final_by_scene(self, scenes: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        payload = _read_json(self.final_renderable_manifest_path)
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            raise TimelineAssemblyError("final_renderable_assets.json thiếu summary.")
        if int(summary.get("unresolved_count") or 0) != 0:
            raise TimelineAssemblyError("M113 chỉ chạy khi M110.6 không còn unresolved scene.")
        raw = payload.get("scenes")
        if not isinstance(raw, list):
            raise TimelineAssemblyError("final_renderable_assets.json thiếu scenes.")
        by_scene: dict[str, dict[str, Any]] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("scene_id") or "").strip()
            if sid:
                if sid in by_scene:
                    raise TimelineAssemblyError(f"M110.6 có scene trùng: {sid}")
                by_scene[sid] = item
        expected = {str(scene["id"]) for scene in scenes}
        if set(by_scene) != expected:
            missing = sorted(expected - set(by_scene))
            extra = sorted(set(by_scene) - expected)
            raise TimelineAssemblyError(
                f"M110.6 không khớp voice_scenes.json. missing={missing}, extra={extra}"
            )
        return payload, by_scene

    def _validate_scene_sequence(self, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(scenes, key=lambda item: (float(item["start"]), float(item["end"]), str(item["id"])))
        previous_end = 0.0
        for index, scene in enumerate(ordered):
            start = float(scene["start"])
            end = float(scene["end"])
            if index and start < previous_end - self.timing_tolerance_seconds:
                raise TimelineAssemblyError(
                    f"Voice scene bị overlap: {scene['id']} bắt đầu {start:.3f}s trước {previous_end:.3f}s"
                )
            previous_end = max(previous_end, end)
        return ordered

    def _visual_clip(self, scene: dict[str, Any], final_item: dict[str, Any], index: int) -> dict[str, Any]:
        scene_id = str(scene["id"])
        if not bool(final_item.get("render_eligible")):
            raise TimelineAssemblyError(f"Scene chưa render_eligible: {scene_id}")
        asset = final_item.get("asset")
        if not isinstance(asset, dict):
            raise TimelineAssemblyError(f"Scene thiếu final asset: {scene_id}")
        media_type = str(asset.get("media_type") or "").lower()
        if media_type not in {"video", "image"}:
            raise TimelineAssemblyError(f"media_type không hỗ trợ ở {scene_id}: {media_type}")
        asset_path = _project_path(self.project_root, str(asset.get("path") or ""))
        if not asset_path.is_file() or asset_path.stat().st_size <= 0:
            raise TimelineAssemblyError(f"Final asset không tồn tại: {asset_path}")

        start = float(scene["start"])
        end = float(scene["end"])
        duration = end - start
        final_timing = final_item.get("timing") if isinstance(final_item.get("timing"), dict) else {}
        if abs(_float(final_timing.get("start"), start) - start) > self.timing_tolerance_seconds:
            raise TimelineAssemblyError(f"M110.6 start không khớp voice timing: {scene_id}")
        if abs(_float(final_timing.get("end"), end) - end) > self.timing_tolerance_seconds:
            raise TimelineAssemblyError(f"M110.6 end không khớp voice timing: {scene_id}")

        media_duration = _float(asset.get("duration_seconds"), 0.0)
        if media_type == "video" and media_duration + self.timing_tolerance_seconds < duration:
            raise TimelineAssemblyError(
                f"Video final ngắn hơn scene {scene_id}: {media_duration:.3f}s < {duration:.3f}s"
            )

        operation: dict[str, Any]
        if media_type == "video":
            operation = {
                "mode": "trim",
                "source_in_seconds": 0.0,
                "source_out_seconds": round(duration, 6),
                "playback_rate": 1.0,
                "loop": False,
                "speed_change": False,
            }
        else:
            operation = {
                "mode": "still",
                "hold_seconds": round(duration, 6),
                "loop": False,
                "speed_change": False,
            }

        return {
            "clip_id": f"visual_{index:04d}",
            "kind": "scene",
            "scene_id": scene_id,
            "start_seconds": round(start, 6),
            "end_seconds": round(end, 6),
            "duration_seconds": round(duration, 6),
            "asset": {
                "asset_id": str(asset.get("asset_id") or ""),
                "media_type": media_type,
                "path": _project_relative(self.project_root, asset_path),
                "duration_seconds": media_duration if media_duration > 0 else None,
                "width": asset.get("width"),
                "height": asset.get("height"),
                "origin": asset.get("origin"),
            },
            "operation": operation,
            "fit": {"mode": "cover", "position": "center"},
            "selection": final_item.get("selection") if isinstance(final_item.get("selection"), dict) else {},
        }

    def _gap_fill(self, *, index: int, start: float, end: float, reference_clip: dict[str, Any], reason: str) -> dict[str, Any]:
        duration = max(0.0, end - start)
        return {
            "clip_id": f"gap_{index:04d}",
            "kind": "gap_fill",
            "scene_id": None,
            "start_seconds": round(start, 6),
            "end_seconds": round(end, 6),
            "duration_seconds": round(duration, 6),
            "asset": dict(reference_clip["asset"]),
            "operation": {
                "mode": "freeze_frame",
                "source": "first_frame" if reason == "opening_gap" else "last_frame",
                "hold_seconds": round(duration, 6),
                "loop": False,
                "speed_change": False,
            },
            "fit": dict(reference_clip.get("fit") or {"mode": "cover", "position": "center"}),
            "reason": reason,
        }

    def _music_track(self, timeline_duration: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        payload = _read_json(self.music_selection_manifest_path)
        status = str(payload.get("status") or "").strip().lower()
        if status in {"skipped_disabled", "skipped_no_music", "skipped_no_valid_music"}:
            return None, {"status": status, "included": False}
        if status != "selected":
            raise TimelineAssemblyError(f"Trạng thái M112 không hỗ trợ: {status or '(trống)'}")

        selected = payload.get("selected")
        mix = payload.get("mix")
        if not isinstance(selected, dict) or not isinstance(mix, dict):
            raise TimelineAssemblyError("M112 selected thiếu selected/mix.")
        music_path = _project_path(self.project_root, str(selected.get("path") or ""))
        if not music_path.is_file() or music_path.stat().st_size <= 0:
            raise TimelineAssemblyError(f"Music asset không tồn tại: {music_path}")
        music_duration = _float(selected.get("duration_seconds"), 0.0)
        if music_duration <= 0:
            raise TimelineAssemblyError("M112 selected music thiếu duration_seconds hợp lệ.")

        start = max(0.0, _float(mix.get("start_seconds"), 0.0))
        target = max(0.0, timeline_duration - start)
        loop_required = music_duration + self.timing_tolerance_seconds < target
        trim_required = music_duration > target + self.timing_tolerance_seconds
        fade_in = min(max(0.0, _float(mix.get("fade_in_seconds"), 1.5)), target)
        fade_out = min(max(0.0, _float(mix.get("fade_out_seconds"), 2.0)), target)

        track = {
            "asset_id": str(selected.get("asset_id") or ""),
            "path": _project_relative(self.project_root, music_path),
            "start_seconds": round(start, 6),
            "end_seconds": round(start + target, 6),
            "target_duration_seconds": round(target, 6),
            "source_duration_seconds": round(music_duration, 6),
            "operation": {
                "loop_required": bool(loop_required),
                "trim_to_target": bool(trim_required),
                "playback_rate": 1.0,
            },
            "mix": {
                "gain_db": _float(mix.get("music_gain_db"), -22.0),
                "fade_in_seconds": round(fade_in, 3),
                "fade_out_seconds": round(fade_out, 3),
                "ducking_enabled": bool(mix.get("ducking_enabled", True)),
                "ducking_reduction_db": max(0.0, _float(mix.get("ducking_reduction_db"), 6.0)),
                "voice_is_primary": True,
            },
        }
        return track, {"status": status, "included": True}

    def run(self) -> TimelineAssemblyReport:
        self._validate_sources()
        scenes = self._validate_scene_sequence(load_voice_scenes(self.source_scenes_path))
        if not scenes:
            raise TimelineAssemblyError("M113 không thể dựng timeline khi không có scene.")
        _, final_by_scene = self._load_final_by_scene(scenes)
        voice = _resolve_voice_asset(self.project_root, self.voice_asset_id)
        voice_path = voice.audio_path.resolve()

        base_visuals: list[dict[str, Any]] = []
        total = len(scenes)
        for index, scene in enumerate(scenes, start=1):
            clip = self._visual_clip(scene, final_by_scene[str(scene["id"])], index)
            base_visuals.append(clip)
            if self.progress_callback is not None:
                self.progress_callback(index, total, str(scene["id"]), "scene_bound")

        timeline_duration = max(float(scene["end"]) for scene in scenes)
        visuals: list[dict[str, Any]] = []
        gap_fill_count = 0
        cursor = 0.0
        for clip in base_visuals:
            start = float(clip["start_seconds"])
            if start > cursor + self.timing_tolerance_seconds:
                reference = visuals[-1] if visuals else clip
                gap_fill_count += 1
                visuals.append(
                    self._gap_fill(
                        index=gap_fill_count,
                        start=cursor,
                        end=start,
                        reference_clip=reference,
                        reason="between_scene_gap" if visuals else "opening_gap",
                    )
                )
            visuals.append(clip)
            cursor = max(cursor, float(clip["end_seconds"]))

        music_track, music_state = self._music_track(timeline_duration)
        narration_duration = _float(getattr(voice, "duration_seconds", None), 0.0)

        payload = {
            "format": TIMELINE_FORMAT,
            "created_at": _now_iso(),
            "status": "ready",
            "duration_seconds": round(timeline_duration, 6),
            "summary": {
                "scene_count": len(scenes),
                "visual_clip_count": len(base_visuals),
                "gap_fill_count": gap_fill_count,
                "music_included": music_track is not None,
                "unresolved_count": 0,
            },
            "source": {
                "voice_scenes": _project_relative(self.project_root, self.source_scenes_path),
                "final_renderable": self.final_renderable_manifest_path.name,
                "music_selection": self.music_selection_manifest_path.name,
            },
            "tracks": {
                "narration": {
                    "asset_id": self.voice_asset_id,
                    "path": _project_relative(self.project_root, voice_path),
                    "start_seconds": 0.0,
                    "end_seconds": round(timeline_duration, 6),
                    "timeline_duration_seconds": round(timeline_duration, 6),
                    "source_duration_seconds": round(narration_duration, 6) if narration_duration > 0 else None,
                    "gain_db": 0.0,
                    "primary": True,
                    "time_stretch": False,
                },
                "visuals": visuals,
                "music": music_track,
            },
            "music_state": music_state,
            "policy": {
                "timing_authority": "voice_scenes.json",
                "narration_time_stretch": False,
                "scene_video_loop": False,
                "scene_video_speed_change": False,
                "video_scene_operation": "trim_from_source_start",
                "image_scene_operation": "still_hold",
                "gap_policy": "freeze_adjacent_render_asset",
                "youtube_reference_is_render_asset": False,
                "local_project_paths_only": True,
                "rendering_performed": False,
            },
            "issues": [],
        }
        _atomic_json_write(self.output_path, payload)
        return TimelineAssemblyReport(
            status="ready",
            scene_count=len(scenes),
            visual_clip_count=len(base_visuals),
            gap_fill_count=gap_fill_count,
            duration_seconds=timeline_duration,
            music_included=music_track is not None,
            manifest_path=str(self.output_path),
        )
