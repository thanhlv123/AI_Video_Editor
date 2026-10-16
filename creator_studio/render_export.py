from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Optional

from core.media import Media
from core.project import Project
from core.timeline import Clip, Track

from creator_studio.export_lock import ProjectExportBusy, project_export_lock
from creator_studio.export_recovery import recover_interrupted_exports
from creator_studio.output_integrity import verify_rendered_output

from creator_studio.render_backend import (
    RenderBackendCancelled,
    RenderBackendError,
    RenderBackendRequest,
    RenderBackendResult,
    RenderCancellationToken,
    RenderMixPolicy,
    RenderProgress,
    RenderProgressCallback,
    TimelineRendererBackend,
)


class RenderExportError(RuntimeError):
    """Raised when an M114 render/export operation cannot be completed."""


@dataclass(frozen=True, slots=True)
class RenderExportResult:
    status: str
    output_path: Path
    manifest_path: Path

    duration_seconds: float
    width: int
    height: int
    fps: float

    backend_result: RenderBackendResult


@dataclass(frozen=True, slots=True)
class _PreparedRender:
    project: Project

    duration_seconds: float

    video_track_id: str
    narration_track_id: str
    music_track_id: Optional[str]

    mix_policy: RenderMixPolicy

    visual_clip_count: int
    has_narration: bool
    has_music: bool


class RenderExportService:
    """
    M114 runtime/export service.

    Responsibilities:
    - read a ready M113 timeline_manifest.json
    - validate referenced assets before FFmpeg starts
    - resolve paths relative to the project root
    - convert the M113 timeline into core.Project
    - reserve a non-overwriting final_video_NNN.mp4 path
    - invoke a RenderBackend
    - persist render_export_manifest*.json

    This service intentionally does not modify the M72/M73/M74
    render planning contracts.
    """

    FORMAT = "creator_studio.render_export.v1"

    VIDEO_TRACK_ID = "video_1"
    NARRATION_TRACK_ID = "voice_1"
    MUSIC_TRACK_ID = "music_1"

    def __init__(
        self,
        backend=None,
        *,
        default_width: int = 1920,
        default_height: int = 1080,
        default_fps: float = 30.0,
        verify_output: Optional[bool] = None,
    ) -> None:
        self.backend = (
            backend
            if backend is not None
            else TimelineRendererBackend()
        )
        # Real production renders must pass ffprobe; synthetic test backends
        # remain injectable without requiring a playable MP4 fixture.
        self.verify_output = (
            isinstance(self.backend, TimelineRendererBackend)
            if verify_output is None
            else bool(verify_output)
        )

        self.default_width = self._positive_int(
            default_width,
            "default_width",
        )

        self.default_height = self._positive_int(
            default_height,
            "default_height",
        )

        self.default_fps = self._positive_float(
            default_fps,
            "default_fps",
        )

        if not callable(
            getattr(self.backend, "render", None)
        ):
            raise TypeError(
                "backend must expose a callable render() method."
            )


    # ==================================================
    # PUBLIC API
    # ==================================================

    def export(
        self,
        timeline_manifest_path,
        project_root,
        *,
        progress_callback: Optional[RenderProgressCallback] = None,
        cancel_token: Optional[RenderCancellationToken] = None,
    ) -> RenderExportResult:
        """Serialize exports per project across threads and processes."""
        token = cancel_token if cancel_token is not None else RenderCancellationToken()
        token.check()
        timeline_path = Path(timeline_manifest_path).expanduser().resolve()
        root = Path(project_root).expanduser().resolve()
        if not timeline_path.is_file():
            raise RenderExportError(
                f"Timeline manifest does not exist: {timeline_path}"
            )
        if not root.is_dir():
            raise RenderExportError(f"Project root does not exist: {root}")

        try:
            with project_export_lock(root):
                recover_interrupted_exports(timeline_path.parent, root)
                return self._export_unlocked(
                    timeline_path,
                    root,
                    progress_callback=progress_callback,
                    cancel_token=token,
                )
        except ProjectExportBusy as exc:
            raise RenderExportError(str(exc)) from exc

    def _export_unlocked(
        self,
        timeline_manifest_path,
        project_root,
        *,
        progress_callback: Optional[
            RenderProgressCallback
        ] = None,
        cancel_token: Optional[
            RenderCancellationToken
        ] = None,
    ) -> RenderExportResult:

        token = (
            cancel_token
            if cancel_token is not None
            else RenderCancellationToken()
        )

        token.check()

        timeline_path = Path(
            timeline_manifest_path
        ).expanduser().resolve()

        root = Path(
            project_root
        ).expanduser().resolve()

        if not timeline_path.is_file():
            raise RenderExportError(
                "Timeline manifest does not exist: "
                f"{timeline_path}"
            )

        if not root.is_dir():
            raise RenderExportError(
                "Project root does not exist: "
                f"{root}"
            )

        self._emit(
            progress_callback,
            "validating",
            0.0,
            "Validating M113 timeline manifest.",
        )

        manifest = self._load_json(
            timeline_path
        )

        prepared = self._prepare_render(
            manifest=manifest,
            project_root=root,
        )

        token.check()

        export_directory = (
            root
            / "exports"
        )

        export_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path = self._reserve_numbered_path(
            directory=export_directory,
            stem="final_video",
            suffix=".mp4",
        )

        export_manifest_path = (
            self._reserve_export_manifest_path(
                timeline_path.parent
            )
        )

        now = self._timestamp()

        export_manifest = {
            "format": self.FORMAT,
            "created_at": now,
            "updated_at": now,
            "status": "rendering",
            "timeline_manifest": str(
                timeline_path
            ),
            "project_root": str(
                root
            ),
            "output_path": str(
                output_path
            ),
            "duration_seconds": (
                prepared.duration_seconds
            ),
            "width": (
                prepared.project.settings.width
            ),
            "height": (
                prepared.project.settings.height
            ),
            "fps": (
                prepared.project.settings.fps
            ),
            "video_codec": "h264",
            "audio_codec": "aac",
            "summary": {
                "visual_clip_count": (
                    prepared.visual_clip_count
                ),
                "narration_included": (
                    prepared.has_narration
                ),
                "music_included": (
                    prepared.has_music
                ),
            },
            "backend": (
                type(self.backend).__name__
            ),
            "issues": [],
            "error": None,
        }

        self._write_json(
            export_manifest_path,
            export_manifest,
        )

        try:
            self._emit(
                progress_callback,
                "prepared",
                3.0,
                (
                    "Render project prepared. "
                    f"Output: {output_path.name}"
                ),
            )

            request = RenderBackendRequest(
                project=prepared.project,
                output_path=output_path,
                duration_seconds=(
                    prepared.duration_seconds
                ),
                video_track_id=(
                    prepared.video_track_id
                ),
                narration_track_id=(
                    prepared.narration_track_id
                ),
                music_track_id=(
                    prepared.music_track_id
                ),
                mix_policy=(
                    prepared.mix_policy
                ),
                allow_overwrite=False,
            )

            backend_result = (
                self.backend.render(
                    request,
                    progress_callback=(
                        progress_callback
                    ),
                    cancel_token=token,
                )
            )

            if not isinstance(backend_result, RenderBackendResult):
                raise RenderExportError("Render backend returned an invalid result.")
            if not backend_result.success:
                raise RenderExportError("Render backend returned an unsuccessful result.")
            try:
                reported_path = Path(backend_result.output_path).expanduser().resolve()
            except (TypeError, ValueError, OSError) as exc:
                raise RenderExportError("Render backend returned an invalid output path.") from exc
            if reported_path != output_path:
                raise RenderExportError("Render backend returned an unexpected output path.")
            if not output_path.is_file():
                raise RenderExportError("Render backend completed but the final output file is missing.")
            if output_path.stat().st_size <= 0:
                raise RenderExportError("Render backend completed but the final output file is empty.")
            if self.verify_output:
                verify_rendered_output(
                    output_path,
                    expected_width=prepared.project.settings.width,
                    expected_height=prepared.project.settings.height,
                    expected_duration=prepared.duration_seconds,
                    require_audio=prepared.has_narration or prepared.has_music,
                )

        except RenderBackendCancelled as exc:
            self._remove_partial_output(
                output_path
            )

            export_manifest[
                "status"
            ] = "cancelled"

            export_manifest[
                "updated_at"
            ] = self._timestamp()

            export_manifest[
                "error"
            ] = str(exc)

            export_manifest[
                "issues"
            ] = [
                "render_cancelled"
            ]

            self._write_json(
                export_manifest_path,
                export_manifest,
            )

            raise

        except (
            RenderBackendError,
            Exception,
        ) as exc:
            self._remove_partial_output(
                output_path
            )

            export_manifest[
                "status"
            ] = "failed"

            export_manifest[
                "updated_at"
            ] = self._timestamp()

            export_manifest[
                "error"
            ] = str(exc)

            export_manifest[
                "issues"
            ] = [
                "render_failed"
            ]

            self._write_json(
                export_manifest_path,
                export_manifest,
            )

            if isinstance(
                exc,
                RenderExportError,
            ):
                raise

            raise RenderExportError(
                f"Render/export failed: {exc}"
            ) from exc

        export_manifest[
            "status"
        ] = "completed"

        export_manifest[
            "updated_at"
        ] = self._timestamp()

        export_manifest[
            "output_path"
        ] = str(
            backend_result.output_path
        )

        export_manifest[
            "width"
        ] = (
            backend_result.width
            or prepared.project.settings.width
        )

        export_manifest[
            "height"
        ] = (
            backend_result.height
            or prepared.project.settings.height
        )

        export_manifest[
            "fps"
        ] = (
            backend_result.fps
            or prepared.project.settings.fps
        )

        export_manifest[
            "backend_result"
        ] = {
            "video_clips": (
                backend_result.video_clips
            ),
            "has_narration": (
                backend_result.has_narration
            ),
            "has_music": (
                backend_result.has_music
            ),
        }

        self._write_json(
            export_manifest_path,
            export_manifest,
        )

        return RenderExportResult(
            status="completed",
            output_path=(
                backend_result.output_path
            ),
            manifest_path=(
                export_manifest_path
            ),
            duration_seconds=(
                prepared.duration_seconds
            ),
            width=int(
                export_manifest["width"]
            ),
            height=int(
                export_manifest["height"]
            ),
            fps=float(
                export_manifest["fps"]
            ),
            backend_result=(
                backend_result
            ),
        )


    # ==================================================
    # MANIFEST -> CORE PROJECT
    # ==================================================

    def _prepare_render(
        self,
        *,
        manifest: Mapping[str, Any],
        project_root: Path,
    ) -> _PreparedRender:

        status = str(
            manifest.get(
                "status",
                "",
            )
            or ""
        ).strip().lower()

        if status != "ready":
            raise RenderExportError(
                "Timeline manifest is not ready. "
                f"Current status: {status or '<missing>'}"
            )

        duration_seconds = (
            self._positive_float(
                manifest.get(
                    "duration_seconds"
                ),
                "duration_seconds",
            )
        )

        tracks = self._mapping(
            manifest.get("tracks"),
            "tracks",
        )

        visuals = tracks.get(
            "visuals"
        )

        if not isinstance(
            visuals,
            list,
        ) or not visuals:
            raise RenderExportError(
                "Timeline manifest contains "
                "no visual clips."
            )

        narration = self._mapping(
            tracks.get("narration"),
            "tracks.narration",
        )

        narration_path_value = str(
            narration.get(
                "path",
                "",
            )
            or ""
        ).strip()

        if not narration_path_value:
            raise RenderExportError(
                "Timeline narration path is missing."
            )

        music_state_raw = (
            manifest.get(
                "music_state"
            )
        )

        music_state = (
            music_state_raw
            if isinstance(
                music_state_raw,
                Mapping,
            )
            else {}
        )

        music_data_raw = tracks.get(
            "music"
        )

        has_music = bool(
            music_state.get(
                "included",
                music_data_raw is not None,
            )
        )

        music_data = None

        if has_music:
            music_data = self._mapping(
                music_data_raw,
                "tracks.music",
            )

        width, height, fps = (
            self._resolve_project_settings(
                manifest=manifest,
                visuals=visuals,
            )
        )

        project = Project(
            name=project_root.name
            or "Creator Studio Project"
        )

        project.settings.width = width
        project.settings.height = height
        project.settings.fps = fps

        video_track = Track(
            id=self.VIDEO_TRACK_ID,
            name="Video 1",
            track_type="video",
        )

        narration_track = Track(
            id=self.NARRATION_TRACK_ID,
            name="Narration",
            track_type="audio",
        )

        project.timeline.add_track(
            video_track
        )

        project.timeline.add_track(
            narration_track
        )

        self._add_visuals(
            project=project,
            track=video_track,
            visuals=visuals,
            project_root=project_root,
        )

        narration_gain_db = (
            self._finite_float(
                narration.get(
                    "gain_db",
                    0.0,
                ),
                "tracks.narration.gain_db",
            )
        )

        self._add_narration(
            project=project,
            track=narration_track,
            narration=narration,
            project_root=project_root,
            timeline_duration=duration_seconds,
        )

        music_track_id = None

        music_mix = {
            "gain_db": -24.0,
            "fade_in_seconds": 0.0,
            "fade_out_seconds": 0.0,
            "ducking_enabled": False,
            "ducking_reduction_db": 0.0,
            "voice_is_primary": True,
        }

        if has_music:
            music_track = Track(
                id=self.MUSIC_TRACK_ID,
                name="Background Music",
                track_type="audio",
            )

            project.timeline.add_track(
                music_track
            )

            self._add_music(
                project=project,
                track=music_track,
                music=music_data,
                project_root=project_root,
                timeline_duration=(
                    duration_seconds
                ),
            )

            mix_raw = music_data.get(
                "mix"
            )

            if isinstance(
                mix_raw,
                Mapping,
            ):
                music_mix.update(
                    mix_raw
                )

            music_track_id = (
                self.MUSIC_TRACK_ID
            )

        mix_policy = RenderMixPolicy(
            narration_gain_db=(
                narration_gain_db
            ),
            music_gain_db=(
                music_mix.get(
                    "gain_db",
                    -24.0,
                )
            ),
            music_fade_in_seconds=(
                music_mix.get(
                    "fade_in_seconds",
                    0.0,
                )
            ),
            music_fade_out_seconds=(
                music_mix.get(
                    "fade_out_seconds",
                    0.0,
                )
            ),
            ducking_enabled=(
                music_mix.get(
                    "ducking_enabled",
                    False,
                )
            ),
            ducking_reduction_db=(
                music_mix.get(
                    "ducking_reduction_db",
                    0.0,
                )
            ),
            voice_is_primary=(
                music_mix.get(
                    "voice_is_primary",
                    True,
                )
            ),
        )

        return _PreparedRender(
            project=project,
            duration_seconds=(
                duration_seconds
            ),
            video_track_id=(
                self.VIDEO_TRACK_ID
            ),
            narration_track_id=(
                self.NARRATION_TRACK_ID
            ),
            music_track_id=(
                music_track_id
            ),
            mix_policy=mix_policy,
            visual_clip_count=len(
                visuals
            ),
            has_narration=True,
            has_music=has_music,
        )


    def _add_visuals(
        self,
        *,
        project: Project,
        track: Track,
        visuals,
        project_root: Path,
    ) -> None:

        seen_clip_ids = set()

        for index, raw_visual in enumerate(
            visuals,
            start=1,
        ):
            visual = self._mapping(
                raw_visual,
                f"tracks.visuals[{index - 1}]",
            )

            asset = self._mapping(
                visual.get("asset"),
                (
                    "tracks.visuals"
                    f"[{index - 1}].asset"
                ),
            )

            clip_id = str(
                visual.get(
                    "clip_id",
                    f"visual_{index:04d}",
                )
                or ""
            ).strip()

            if not clip_id:
                raise RenderExportError(
                    "Visual clip ID is missing."
                )

            if clip_id in seen_clip_ids:
                raise RenderExportError(
                    "Duplicate visual clip ID: "
                    f"{clip_id}"
                )

            seen_clip_ids.add(
                clip_id
            )

            media_id = str(
                asset.get(
                    "asset_id",
                    "",
                )
                or ""
            ).strip()

            if not media_id:
                raise RenderExportError(
                    f"Visual asset ID is missing "
                    f"for {clip_id}."
                )

            media_type = str(
                asset.get(
                    "media_type",
                    "",
                )
                or ""
            ).strip().lower()

            if media_type not in {
                "video",
                "image",
            }:
                raise RenderExportError(
                    "Unsupported visual media type "
                    f"for {clip_id}: {media_type}"
                )

            media_path = (
                self._resolve_asset(
                    project_root,
                    asset.get("path"),
                    (
                        "visual asset "
                        f"{media_id}"
                    ),
                )
            )

            media_duration = (
                self._nonnegative_float(
                    asset.get(
                        "duration_seconds",
                        0.0,
                    ),
                    (
                        f"{media_id}."
                        "duration_seconds"
                    ),
                )
            )

            media_width = (
                self._optional_positive_int(
                    asset.get("width")
                )
            )

            media_height = (
                self._optional_positive_int(
                    asset.get("height")
                )
            )

            if project.get_media(
                media_id
            ) is None:
                project.add_media(
                    Media(
                        id=media_id,
                        path=str(
                            media_path
                        ),
                        media_type=(
                            media_type
                        ),
                        name=(
                            media_path.name
                        ),
                        duration=(
                            media_duration
                        ),
                        width=(
                            media_width
                        ),
                        height=(
                            media_height
                        ),
                        has_audio=False,
                    )
                )

            start = self._nonnegative_float(
                visual.get(
                    "start_seconds"
                ),
                (
                    f"{clip_id}."
                    "start_seconds"
                ),
            )

            duration = self._positive_float(
                visual.get(
                    "duration_seconds"
                ),
                (
                    f"{clip_id}."
                    "duration_seconds"
                ),
            )

            operation_raw = visual.get(
                "operation"
            )

            operation = (
                operation_raw
                if isinstance(
                    operation_raw,
                    Mapping,
                )
                else {}
            )

            source_start = (
                self._nonnegative_float(
                    operation.get(
                        "source_in_seconds",
                        0.0,
                    ),
                    (
                        f"{clip_id}."
                        "source_in_seconds"
                    ),
                )
            )

            track.add_clip(
                Clip(
                    id=clip_id,
                    media_id=media_id,
                    track_id=(
                        self.VIDEO_TRACK_ID
                    ),
                    start=start,
                    duration=duration,
                    source_start=(
                        source_start
                    ),
                    source_duration=(
                        duration
                    ),
                )
            )


    def _add_narration(
        self,
        *,
        project: Project,
        track: Track,
        narration: Mapping[str, Any],
        project_root: Path,
        timeline_duration: float,
    ) -> None:

        asset_id = str(
            narration.get(
                "asset_id",
                "narration_main",
            )
            or "narration_main"
        ).strip()

        path = self._resolve_asset(
            project_root,
            narration.get("path"),
            "narration",
        )

        # M113 explicitly writes null when the source voice duration
        # is unknown. Treat only null (or an absent key) as unknown;
        # keep rejecting invalid non-null numeric metadata.
        source_duration_value = narration.get(
            "source_duration_seconds"
        )
        source_duration = self._positive_float(
            timeline_duration
            if source_duration_value is None
            else source_duration_value,
            "tracks.narration.source_duration_seconds",
        )

        start = self._nonnegative_float(
            narration.get(
                "start_seconds",
                0.0,
            ),
            (
                "tracks.narration."
                "start_seconds"
            ),
        )

        end = self._positive_float(
            narration.get(
                "end_seconds",
                timeline_duration,
            ),
            (
                "tracks.narration."
                "end_seconds"
            ),
        )

        duration = end - start

        if duration <= 0:
            raise RenderExportError(
                "Narration duration must "
                "be positive."
            )

        if (
            end
            > timeline_duration + 0.001
        ):
            raise RenderExportError(
                "Narration extends beyond "
                "timeline duration."
            )

        project.add_media(
            Media(
                id=asset_id,
                path=str(path),
                media_type="audio",
                name=path.name,
                duration=source_duration,
                has_audio=True,
            )
        )

        track.add_clip(
            Clip(
                id="narration_main",
                media_id=asset_id,
                track_id=(
                    self.NARRATION_TRACK_ID
                ),
                start=start,
                duration=duration,
                source_start=0.0,
                source_duration=duration,
            )
        )


    def _add_music(
        self,
        *,
        project: Project,
        track: Track,
        music: Mapping[str, Any],
        project_root: Path,
        timeline_duration: float,
    ) -> None:

        path = self._resolve_asset(
            project_root,
            music.get("path"),
            "background music",
        )

        source_duration = (
            self._positive_float(
                music.get(
                    "source_duration_seconds",
                    timeline_duration,
                ),
                (
                    "tracks.music."
                    "source_duration_seconds"
                ),
            )
        )

        start = self._nonnegative_float(
            music.get(
                "start_seconds",
                0.0,
            ),
            (
                "tracks.music."
                "start_seconds"
            ),
        )

        end = self._positive_float(
            music.get(
                "end_seconds",
                timeline_duration,
            ),
            (
                "tracks.music."
                "end_seconds"
            ),
        )

        duration = end - start

        if duration <= 0:
            raise RenderExportError(
                "Music duration must be positive."
            )

        if (
            end
            > timeline_duration + 0.001
        ):
            raise RenderExportError(
                "Music extends beyond "
                "timeline duration."
            )

        media_id = "music_main"

        if project.get_media(
            media_id
        ) is not None:
            media_id = (
                "music_background"
            )

        project.add_media(
            Media(
                id=media_id,
                path=str(path),
                media_type="audio",
                name=path.name,
                duration=source_duration,
                has_audio=True,
            )
        )

        track.add_clip(
            Clip(
                id="music_main_clip",
                media_id=media_id,
                track_id=(
                    self.MUSIC_TRACK_ID
                ),
                start=start,
                duration=duration,
                source_start=0.0,
                source_duration=duration,
            )
        )


    # ==================================================
    # PROJECT SETTINGS
    # ==================================================

    def _resolve_project_settings(
        self,
        *,
        manifest: Mapping[str, Any],
        visuals,
    ):

        width = None
        height = None
        fps = None

        policy = manifest.get(
            "policy"
        )

        if isinstance(
            policy,
            Mapping,
        ):
            width = self._first_valid_positive_int(
                policy,
                (
                    "width",
                    "output_width",
                    "render_width",
                ),
            )

            height = self._first_valid_positive_int(
                policy,
                (
                    "height",
                    "output_height",
                    "render_height",
                ),
            )

            fps = self._first_valid_positive_float(
                policy,
                (
                    "fps",
                    "output_fps",
                    "render_fps",
                ),
            )

        first_visual = (
            visuals[0]
            if visuals
            else None
        )

        if isinstance(
            first_visual,
            Mapping,
        ):
            asset = first_visual.get(
                "asset"
            )

            if isinstance(
                asset,
                Mapping,
            ):
                if width is None:
                    width = (
                        self._optional_positive_int(
                            asset.get("width")
                        )
                    )

                if height is None:
                    height = (
                        self._optional_positive_int(
                            asset.get("height")
                        )
                    )

                if fps is None:
                    fps = (
                        self._optional_positive_float(
                            asset.get("fps")
                        )
                    )

        return (
            width
            or self.default_width,
            height
            or self.default_height,
            fps
            or self.default_fps,
        )


    # ==================================================
    # PATHS
    # ==================================================

    def _resolve_asset(
        self,
        project_root: Path,
        value,
        label: str,
    ) -> Path:

        text = str(
            value or ""
        ).strip()

        if not text:
            raise RenderExportError(
                f"{label} path is missing."
            )

        path = Path(
            text
        ).expanduser()

        if not path.is_absolute():
            path = (
                project_root
                / path
            )

        path = path.resolve()

        if not path.is_file():
            raise RenderExportError(
                f"{label} file does not exist: "
                f"{path}"
            )

        return path


    def _reserve_numbered_path(
        self,
        *,
        directory: Path,
        stem: str,
        suffix: str,
    ) -> Path:

        for number in range(
            1,
            1_000_000,
        ):
            candidate = (
                directory
                / (
                    f"{stem}_"
                    f"{number:03d}"
                    f"{suffix}"
                )
            )

            if not candidate.exists():
                return candidate

        raise RenderExportError(
            "Unable to reserve a unique "
            "render output path."
        )


    def _reserve_export_manifest_path(
        self,
        directory: Path,
    ) -> Path:

        first = (
            directory
            / "render_export_manifest.json"
        )

        if not first.exists():
            return first

        for number in range(
            2,
            1_000_000,
        ):
            candidate = (
                directory
                / (
                    "render_export_manifest_"
                    f"{number:03d}.json"
                )
            )

            if not candidate.exists():
                return candidate

        raise RenderExportError(
            "Unable to reserve a unique "
            "render export manifest path."
        )


    # ==================================================
    # JSON / STATUS
    # ==================================================

    def _load_json(
        self,
        path: Path,
    ) -> Mapping[str, Any]:

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                data = json.load(
                    handle
                )

        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise RenderExportError(
                "Unable to read timeline "
                f"manifest: {exc}"
            ) from exc

        if not isinstance(
            data,
            Mapping,
        ):
            raise RenderExportError(
                "Timeline manifest root "
                "must be a JSON object."
            )

        return data


    def _write_json(
        self,
        path: Path,
        data,
    ) -> None:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = path.with_name(
            path.name + ".tmp"
        )

        try:
            with temporary.open(
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    data,
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )

                handle.write(
                    "\n"
                )

            temporary.replace(
                path
            )

        except OSError as exc:
            try:
                temporary.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise RenderExportError(
                "Unable to write render "
                f"manifest: {exc}"
            ) from exc


    def _remove_partial_output(
        self,
        path: Path,
    ) -> None:

        try:
            path.unlink(
                missing_ok=True
            )
        except OSError:
            pass


    # ==================================================
    # VALIDATION HELPERS
    # ==================================================

    def _mapping(
        self,
        value,
        name: str,
    ) -> Mapping[str, Any]:

        if not isinstance(
            value,
            Mapping,
        ):
            raise RenderExportError(
                f"{name} must be an object."
            )

        return value


    def _finite_float(
        self,
        value,
        name: str,
    ) -> float:

        if isinstance(
            value,
            bool,
        ):
            raise RenderExportError(
                f"{name} must be numeric."
            )

        try:
            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RenderExportError(
                f"{name} must be numeric."
            ) from exc

        if not isfinite(
            number
        ):
            raise RenderExportError(
                f"{name} must be finite."
            )

        return number


    def _positive_float(
        self,
        value,
        name: str,
    ) -> float:

        number = self._finite_float(
            value,
            name,
        )

        if number <= 0.0:
            raise RenderExportError(
                f"{name} must be positive."
            )

        return number


    def _nonnegative_float(
        self,
        value,
        name: str,
    ) -> float:

        number = self._finite_float(
            value,
            name,
        )

        if number < 0.0:
            raise RenderExportError(
                f"{name} cannot be negative."
            )

        return number


    def _positive_int(
        self,
        value,
        name: str,
    ) -> int:

        if isinstance(
            value,
            bool,
        ):
            raise RenderExportError(
                f"{name} must be a positive integer."
            )

        try:
            number = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RenderExportError(
                f"{name} must be a positive integer."
            ) from exc

        if number <= 0:
            raise RenderExportError(
                f"{name} must be positive."
            )

        return number


    def _optional_positive_int(
        self,
        value,
    ):

        if value is None:
            return None

        try:
            number = int(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if number <= 0:
            return None

        return number


    def _optional_positive_float(
        self,
        value,
    ):

        if value is None:
            return None

        try:
            number = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if (
            not isfinite(number)
            or number <= 0
        ):
            return None

        return number


    def _first_valid_positive_int(
        self,
        mapping: Mapping[str, Any],
        names,
    ):

        for name in names:
            value = (
                self._optional_positive_int(
                    mapping.get(name)
                )
            )

            if value is not None:
                return value

        return None


    def _first_valid_positive_float(
        self,
        mapping: Mapping[str, Any],
        names,
    ):

        for name in names:
            value = (
                self._optional_positive_float(
                    mapping.get(name)
                )
            )

            if value is not None:
                return value

        return None


    # ==================================================
    # MISC
    # ==================================================

    def _emit(
        self,
        callback,
        phase,
        percent,
        detail,
    ) -> None:

        if callback is None:
            return

        callback(
            RenderProgress(
                phase=phase,
                percent=percent,
                detail=detail,
            )
        )


    def _timestamp(
        self,
    ) -> str:

        return (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )