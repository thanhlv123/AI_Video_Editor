from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from pathlib import Path
from threading import Event
from typing import Any, Callable, Mapping, Optional, Protocol
import inspect


class RenderBackendError(RuntimeError):
    """Base error raised by the M114 render backend boundary."""


class RenderBackendCancelled(RenderBackendError):
    """Raised when a render request is cancelled."""


@dataclass(frozen=True, slots=True)
class RenderProgress:
    """
    Progress event exposed by the render backend.

    percent uses the closed range 0..100.
    """

    phase: str
    percent: float
    detail: str = ""

    def __post_init__(self) -> None:
        phase = str(self.phase or "").strip()
        detail = str(self.detail or "").strip()

        try:
            percent = float(self.percent)
        except (TypeError, ValueError) as exc:
            raise ValueError("Render progress percent must be numeric.") from exc

        if not phase:
            raise ValueError("Render progress phase is required.")

        if not isfinite(percent):
            raise ValueError("Render progress percent must be finite.")

        if percent < 0.0 or percent > 100.0:
            raise ValueError(
                "Render progress percent must be between 0 and 100."
            )

        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "percent", percent)
        object.__setattr__(self, "detail", detail)


@dataclass(frozen=True, slots=True)
class RenderMixPolicy:
    """
    Runtime audio-mix policy.

    This intentionally lives outside creator_studio.render_job.
    M74 remains a pure planning/contract layer and does not gain
    FFmpeg/runtime responsibilities.
    """

    narration_gain_db: float = 0.0

    music_gain_db: float = -24.0
    music_fade_in_seconds: float = 0.0
    music_fade_out_seconds: float = 0.0

    ducking_enabled: bool = False
    ducking_reduction_db: float = 0.0
    voice_is_primary: bool = True

    def __post_init__(self) -> None:
        numeric_values = {
            "narration_gain_db": self.narration_gain_db,
            "music_gain_db": self.music_gain_db,
            "music_fade_in_seconds": self.music_fade_in_seconds,
            "music_fade_out_seconds": self.music_fade_out_seconds,
            "ducking_reduction_db": self.ducking_reduction_db,
        }

        normalized: dict[str, float] = {}

        for name, value in numeric_values.items():
            if isinstance(value, bool):
                raise ValueError(f"{name} must be numeric, not bool.")

            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be numeric.") from exc

            if not isfinite(number):
                raise ValueError(f"{name} must be finite.")

            normalized[name] = number

        if normalized["music_fade_in_seconds"] < 0.0:
            raise ValueError(
                "music_fade_in_seconds cannot be negative."
            )

        if normalized["music_fade_out_seconds"] < 0.0:
            raise ValueError(
                "music_fade_out_seconds cannot be negative."
            )

        if normalized["ducking_reduction_db"] < 0.0:
            raise ValueError(
                "ducking_reduction_db cannot be negative."
            )

        for name, value in normalized.items():
            object.__setattr__(self, name, value)

        object.__setattr__(
            self,
            "ducking_enabled",
            bool(self.ducking_enabled),
        )

        object.__setattr__(
            self,
            "voice_is_primary",
            bool(self.voice_is_primary),
        )

    def to_renderer_options(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RenderBackendRequest:
    """
    Stable M114 request passed from RenderExportService to a backend.
    """

    project: Any
    output_path: Path | str
    duration_seconds: float

    video_track_id: str = "video_1"
    narration_track_id: str = "voice_1"
    music_track_id: Optional[str] = None

    mix_policy: RenderMixPolicy = field(
        default_factory=RenderMixPolicy
    )

    allow_overwrite: bool = False

    def __post_init__(self) -> None:
        if self.project is None:
            raise ValueError("Render project is required.")

        output_path = Path(self.output_path).expanduser()

        if not str(output_path):
            raise ValueError("Render output path is required.")

        try:
            duration = float(self.duration_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Render duration_seconds must be numeric."
            ) from exc

        if not isfinite(duration) or duration <= 0.0:
            raise ValueError(
                "Render duration_seconds must be a positive finite number."
            )

        video_track_id = str(
            self.video_track_id or ""
        ).strip()

        narration_track_id = str(
            self.narration_track_id or ""
        ).strip()

        music_track_id = (
            str(self.music_track_id).strip()
            if self.music_track_id is not None
            else None
        )

        if not video_track_id:
            raise ValueError("video_track_id is required.")

        if not narration_track_id:
            raise ValueError("narration_track_id is required.")

        if music_track_id == "":
            music_track_id = None

        if not isinstance(self.mix_policy, RenderMixPolicy):
            raise TypeError(
                "mix_policy must be a RenderMixPolicy."
            )

        object.__setattr__(self, "output_path", output_path)
        object.__setattr__(self, "duration_seconds", duration)
        object.__setattr__(self, "video_track_id", video_track_id)
        object.__setattr__(
            self,
            "narration_track_id",
            narration_track_id,
        )
        object.__setattr__(
            self,
            "music_track_id",
            music_track_id,
        )
        object.__setattr__(
            self,
            "allow_overwrite",
            bool(self.allow_overwrite),
        )


@dataclass(frozen=True, slots=True)
class RenderBackendResult:
    success: bool
    output_path: Path

    video_clips: int = 0
    has_narration: bool = False
    has_music: bool = False

    width: int = 0
    height: int = 0
    fps: float = 0.0

    raw: Mapping[str, Any] = field(
        default_factory=dict
    )


class RenderCancellationToken:
    """
    Thread-safe cancellation signal shared between automation and renderer.
    """

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise RenderBackendCancelled(
                "Render was cancelled."
            )


RenderProgressCallback = Callable[[RenderProgress], None]


class RenderBackend(Protocol):
    def render(
        self,
        request: RenderBackendRequest,
        *,
        progress_callback: Optional[
            RenderProgressCallback
        ] = None,
        cancel_token: Optional[
            RenderCancellationToken
        ] = None,
    ) -> RenderBackendResult:
        ...


class TimelineRendererBackend:
    """
    Adapter around engine.timeline_renderer.TimelineRenderer.

    The renderer itself owns FFmpeg process execution. This adapter owns
    the Creator Studio runtime boundary and normalizes progress,
    cancellation and result data.

    M114 deliberately keeps this separate from creator_studio.render_job.
    """

    _M114_RENDER_PARAMETERS = {
        "project",
        "output_path",
        "video_track_id",
        "audio_track_id",
        "music_track_id",
        "mix_policy",
        "progress_callback",
        "cancel_event",
    }

    def __init__(
        self,
        renderer: Any = None,
        *,
        ffmpeg: str = "ffmpeg",
    ) -> None:
        if renderer is None:
            from engine.timeline_renderer import TimelineRenderer

            renderer = TimelineRenderer(
                ffmpeg=ffmpeg
            )

        if not callable(
            getattr(renderer, "render", None)
        ):
            raise TypeError(
                "renderer must expose a callable render() method."
            )

        self.renderer = renderer

    def render(
        self,
        request: RenderBackendRequest,
        *,
        progress_callback: Optional[
            RenderProgressCallback
        ] = None,
        cancel_token: Optional[
            RenderCancellationToken
        ] = None,
    ) -> RenderBackendResult:
        if not isinstance(
            request,
            RenderBackendRequest,
        ):
            raise TypeError(
                "request must be a RenderBackendRequest."
            )

        token = (
            cancel_token
            if cancel_token is not None
            else RenderCancellationToken()
        )

        token.check()

        if (
            request.output_path.exists()
            and not request.allow_overwrite
        ):
            raise RenderBackendError(
                "Render output already exists and overwrite is disabled: "
                f"{request.output_path}"
            )

        self._require_m114_renderer_api(
            request
        )

        def emit(
            phase: str,
            percent: float,
            detail: str = "",
        ) -> None:
            token.check()

            if progress_callback is None:
                return

            progress_callback(
                RenderProgress(
                    phase=phase,
                    percent=percent,
                    detail=detail,
                )
            )

        emit(
            "starting",
            0.0,
            "Preparing render backend.",
        )

        renderer_kwargs = {
            "project": request.project,
            "output_path": request.output_path,
            "video_track_id": request.video_track_id,
            "audio_track_id": request.narration_track_id,
            "music_track_id": request.music_track_id,
            "mix_policy": request.mix_policy.to_renderer_options(),
            "progress_callback": emit,
            "cancel_event": token,
        }

        try:
            raw_result = self.renderer.render(
                **renderer_kwargs
            )

        except RenderBackendCancelled:
            raise

        except Exception as exc:
            if token.is_cancelled():
                raise RenderBackendCancelled(
                    "Render was cancelled."
                ) from exc

            raise RenderBackendError(
                f"Timeline renderer failed: {exc}"
            ) from exc

        token.check()

        if not isinstance(raw_result, Mapping):
            raise RenderBackendError(
                "Timeline renderer returned an invalid result."
            )

        if not bool(raw_result.get("success")):
            raise RenderBackendError(
                "Timeline renderer reported failure."
            )

        output_value = raw_result.get(
            "output",
            request.output_path,
        )

        output_path = Path(
            output_value
        ).expanduser()

        if not output_path.exists():
            raise RenderBackendError(
                "Timeline renderer reported success but "
                f"the output file does not exist: {output_path}"
            )

        result = RenderBackendResult(
            success=True,
            output_path=output_path,
            video_clips=int(
                raw_result.get(
                    "video_clips",
                    0,
                )
                or 0
            ),
            has_narration=bool(
                raw_result.get(
                    "has_narration",
                    raw_result.get(
                        "has_audio",
                        False,
                    ),
                )
            ),
            has_music=bool(
                raw_result.get(
                    "has_music",
                    request.music_track_id is not None,
                )
            ),
            width=int(
                raw_result.get(
                    "width",
                    0,
                )
                or 0
            ),
            height=int(
                raw_result.get(
                    "height",
                    0,
                )
                or 0
            ),
            fps=float(
                raw_result.get(
                    "fps",
                    0.0,
                )
                or 0.0
            ),
            raw=dict(raw_result),
        )

        emit(
            "completed",
            100.0,
            f"Render completed: {output_path.name}",
        )

        return result

    def _require_m114_renderer_api(
        self,
        request: RenderBackendRequest,
    ) -> None:
        """
        Fail explicitly while the legacy TimelineRenderer has not yet
        been upgraded for M114.

        We do not silently drop music/progress/cancellation arguments,
        because doing so could create an output that appears successful
        but does not match the M113 timeline contract.
        """

        try:
            signature = inspect.signature(
                self.renderer.render
            )
        except (TypeError, ValueError) as exc:
            raise RenderBackendError(
                "Unable to inspect TimelineRenderer.render()."
            ) from exc

        parameters = signature.parameters

        accepts_kwargs = any(
            parameter.kind
            is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )

        if accepts_kwargs:
            return

        missing = sorted(
            name
            for name in self._M114_RENDER_PARAMETERS
            if name not in parameters
        )

        if missing:
            raise RenderBackendError(
                "TimelineRenderer is not yet M114-compatible. "
                "Missing render() parameters: "
                + ", ".join(missing)
            )

        if (
            request.music_track_id is not None
            and "music_track_id" not in parameters
        ):
            raise RenderBackendError(
                "TimelineRenderer does not support the M114 music track."
            )