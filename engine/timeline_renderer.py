from __future__ import annotations

from collections import deque
from math import isfinite
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import subprocess
import time


class TimelineRenderError(Exception):
    pass


class TimelineRenderCancelled(TimelineRenderError):
    pass


class TimelineRenderer:

    def __init__(self, ffmpeg="ffmpeg"):
        self.ffmpeg = ffmpeg


    # ==================================================
    # PUBLIC RENDER
    # ==================================================

    def render(
        self,
        project,
        output_path,
        video_track_id="video_1",
        audio_track_id="voice_1",
        music_track_id=None,
        mix_policy=None,
        progress_callback=None,
        cancel_event=None,
    ):

        self._check_cancelled(
            cancel_event
        )

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        # ==============================================
        # PROJECT SETTINGS
        # ==============================================

        width = project.settings.width
        height = project.settings.height
        fps = project.settings.fps


        if width <= 0 or height <= 0:
            raise TimelineRenderError(
                "Project resolution must be positive."
            )

        if fps <= 0:
            raise TimelineRenderError(
                "Project FPS must be positive."
            )


        # ==============================================
        # GET TRACKS
        # ==============================================

        video_track = project.timeline.get_track(
            video_track_id
        )

        if video_track is None:
            raise TimelineRenderError(
                f"Video track not found: {video_track_id}"
            )


        audio_track = project.timeline.get_track(
            audio_track_id
        )


        music_track = None

        if music_track_id:

            music_track = project.timeline.get_track(
                music_track_id
            )

            if music_track is None:
                raise TimelineRenderError(
                    f"Music track not found: {music_track_id}"
                )


        # ==============================================
        # SORT CLIPS
        # ==============================================

        video_clips = sorted(
            [
                clip
                for clip in video_track.clips
                if clip.enabled
            ],
            key=lambda clip: clip.start
        )


        if not video_clips:
            raise TimelineRenderError(
                "Video track contains no clips."
            )


        # ==============================================
        # VALIDATE VIDEO TIMELINE
        # ==============================================

        self._validate_video_clips(
            video_clips
        )


        timeline_duration = float(
            self._number(
                video_clips[-1].start
                + video_clips[-1].duration
            )
        )


        if timeline_duration <= 0:
            raise TimelineRenderError(
                "Timeline duration must be positive."
            )


        self._emit_progress(
            progress_callback,
            "preparing",
            2.0,
            "Validating timeline and media."
        )


        # ==============================================
        # MIX POLICY
        # ==============================================

        mix = self._normalize_mix_policy(
            mix_policy
        )


        # ==============================================
        # BUILD INPUTS
        # ==============================================

        command = [
            self.ffmpeg,
            "-y"
        ]


        video_inputs = []


        for clip in video_clips:

            self._check_cancelled(
                cancel_event
            )

            media = project.get_media(
                clip.media_id
            )

            if media is None:
                raise TimelineRenderError(
                    f"Media not found: {clip.media_id}"
                )


            media_path = Path(
                media.path
            )


            if not media_path.exists():
                raise TimelineRenderError(
                    f"Media file missing: {media_path}"
                )


            input_index = len(
                video_inputs
            )


            if media.media_type == "image":

                command.extend([
                    "-loop",
                    "1",
                    "-framerate",
                    str(fps),
                    "-i",
                    str(media_path)
                ])


            elif media.media_type == "video":

                command.extend([
                    "-i",
                    str(media_path)
                ])


            else:

                raise TimelineRenderError(
                    "Video track can only contain "
                    "image or video media. "
                    f"Found: {media.media_type}"
                )


            video_inputs.append({
                "clip": clip,
                "media": media,
                "input_index": input_index
            })


        # ==============================================
        # NARRATION INPUT
        # ==============================================

        audio_info = None


        if audio_track and audio_track.clips:

            audio_clips = sorted(
                [
                    clip
                    for clip in audio_track.clips
                    if clip.enabled
                ],
                key=lambda clip: clip.start
            )


            if len(audio_clips) > 1:

                raise TimelineRenderError(
                    "Current M114 renderer supports only "
                    "one narration clip on the voice track."
                )


            if audio_clips:

                audio_clip = audio_clips[0]

                audio_media = project.get_media(
                    audio_clip.media_id
                )


                if audio_media is None:

                    raise TimelineRenderError(
                        f"Audio media not found: "
                        f"{audio_clip.media_id}"
                    )


                audio_path = Path(
                    audio_media.path
                )


                if not audio_path.exists():

                    raise TimelineRenderError(
                        f"Audio file missing: "
                        f"{audio_path}"
                    )


                audio_input_index = len(
                    video_inputs
                )


                command.extend([
                    "-i",
                    str(audio_path)
                ])


                audio_info = {
                    "clip": audio_clip,
                    "media": audio_media,
                    "input_index": audio_input_index
                }


        # ==============================================
        # MUSIC INPUT
        # ==============================================

        music_info = None


        if music_track and music_track.clips:

            music_clips = sorted(
                [
                    clip
                    for clip in music_track.clips
                    if clip.enabled
                ],
                key=lambda clip: clip.start
            )


            if len(music_clips) > 1:

                raise TimelineRenderError(
                    "Current M114 renderer supports only "
                    "one clip on the music track."
                )


            if music_clips:

                music_clip = music_clips[0]

                music_media = project.get_media(
                    music_clip.media_id
                )


                if music_media is None:

                    raise TimelineRenderError(
                        f"Music media not found: "
                        f"{music_clip.media_id}"
                    )


                music_path = Path(
                    music_media.path
                )


                if not music_path.exists():

                    raise TimelineRenderError(
                        f"Music file missing: "
                        f"{music_path}"
                    )


                music_input_index = (
                    len(video_inputs)
                    + (
                        1
                        if audio_info is not None
                        else 0
                    )
                )


                # Loop automatically when the requested clip is
                # longer than the known source duration.
                music_source_duration = float(
                    getattr(
                        music_media,
                        "duration",
                        0.0
                    )
                    or 0.0
                )

                music_required_end = (
                    float(
                        music_clip.source_start
                    )
                    + float(
                        music_clip.duration
                    )
                )


                if (
                    music_source_duration > 0
                    and music_required_end
                    > music_source_duration + 0.001
                ):

                    command.extend([
                        "-stream_loop",
                        "-1"
                    ])


                command.extend([
                    "-i",
                    str(music_path)
                ])


                music_info = {
                    "clip": music_clip,
                    "media": music_media,
                    "input_index": music_input_index
                }


        # ==============================================
        # BUILD FILTER GRAPH
        # ==============================================

        filters = []

        video_labels = []


        for number, item in enumerate(
            video_inputs
        ):

            clip = item["clip"]
            media = item["media"]
            index = item["input_index"]

            label = f"v{number}"


            if media.media_type == "image":

                filter_part = (
                    f"[{index}:v]"
                    f"scale={width}:{height}:"
                    f"force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:"
                    f"(ow-iw)/2:(oh-ih)/2,"
                    f"setsar=1,"
                    f"fps={fps},"
                    f"trim=duration={self._number(clip.duration)},"
                    f"setpts=PTS-STARTPTS"
                    f"[{label}]"
                )


            else:

                source_start = clip.source_start

                filter_part = (
                    f"[{index}:v]"
                    f"trim="
                    f"start={self._number(source_start)}:"
                    f"duration={self._number(clip.duration)},"
                    f"setpts=PTS-STARTPTS,"
                    f"scale={width}:{height}:"
                    f"force_original_aspect_ratio=increase,"
                    f"crop={width}:{height},"
                    f"setsar=1,"
                    f"fps={fps}"
                    f"[{label}]"
                )


            filters.append(
                filter_part
            )

            video_labels.append(
                f"[{label}]"
            )


        # ==============================================
        # CONCAT VIDEO CLIPS
        # ==============================================

        concat_filter = (
            "".join(video_labels)
            + f"concat=n={len(video_labels)}:"
            + "v=1:a=0[vout]"
        )

        filters.append(
            concat_filter
        )


        # ==============================================
        # NARRATION FILTER
        # ==============================================

        narration_label = None


        if audio_info:

            audio_clip = audio_info["clip"]

            audio_index = audio_info[
                "input_index"
            ]

            audio_parts = [
                f"[{audio_index}:a]",
                (
                    "atrim="
                    f"start={self._number(audio_clip.source_start)}:"
                    f"duration={self._number(audio_clip.duration)}"
                ),
                "asetpts=PTS-STARTPTS",
            ]


            narration_gain = mix[
                "narration_gain_db"
            ]


            if abs(narration_gain) > 0.000001:

                audio_parts.append(
                    "volume="
                    f"{self._number(narration_gain)}dB"
                )


            if audio_clip.start > 0:

                delay_ms = int(
                    round(
                        audio_clip.start
                        * 1000.0
                    )
                )

                audio_parts.append(
                    f"adelay={delay_ms}:all=1"
                )


            narration_label = "anarr"

            filters.append(
                self._join_filter_parts(
                    audio_parts,
                    narration_label
                )
            )


        # ==============================================
        # MUSIC FILTER
        # ==============================================

        music_label = None


        if music_info:

            music_clip = music_info["clip"]

            music_index = music_info[
                "input_index"
            ]

            music_parts = [
                f"[{music_index}:a]",
                (
                    "atrim="
                    f"start={self._number(music_clip.source_start)}:"
                    f"duration={self._number(music_clip.duration)}"
                ),
                "asetpts=PTS-STARTPTS",
            ]


            music_gain = mix[
                "music_gain_db"
            ]


            if abs(music_gain) > 0.000001:

                music_parts.append(
                    "volume="
                    f"{self._number(music_gain)}dB"
                )


            fade_in = min(
                mix[
                    "music_fade_in_seconds"
                ],
                music_clip.duration
            )


            if fade_in > 0:

                music_parts.append(
                    "afade="
                    "t=in:"
                    "st=0:"
                    f"d={self._number(fade_in)}"
                )


            fade_out = min(
                mix[
                    "music_fade_out_seconds"
                ],
                music_clip.duration
            )


            if fade_out > 0:

                fade_out_start = max(
                    0.0,
                    music_clip.duration
                    - fade_out
                )

                music_parts.append(
                    "afade="
                    "t=out:"
                    f"st={self._number(fade_out_start)}:"
                    f"d={self._number(fade_out)}"
                )


            # M114 V1 deterministic ducking:
            # while narration is present, reduce the music by the
            # requested number of dB.
            #
            # This works for the current M113 timeline where narration
            # is a known continuous primary clip. The policy remains
            # explicit and can later be replaced by sidechain
            # compression without changing the M114 service boundary.
            if (
                audio_info is not None
                and mix[
                    "ducking_enabled"
                ]
                and mix[
                    "voice_is_primary"
                ]
                and mix[
                    "ducking_reduction_db"
                ] > 0
            ):

                narration_clip = audio_info[
                    "clip"
                ]

                duck_start = max(
                    0.0,
                    narration_clip.start
                    - music_clip.start
                )

                duck_end = min(
                    music_clip.duration,
                    narration_clip.start
                    + narration_clip.duration
                    - music_clip.start
                )


                if duck_end > duck_start:

                    reduction = -abs(
                        mix[
                            "ducking_reduction_db"
                        ]
                    )

                    enable_expression = (
                        "between(t\\,"
                        f"{self._number(duck_start)}\\,"
                        f"{self._number(duck_end)})"
                    )

                    music_parts.append(
                        "volume="
                        f"{self._number(reduction)}dB:"
                        f"enable='{enable_expression}'"
                    )


            if music_clip.start > 0:

                delay_ms = int(
                    round(
                        music_clip.start
                        * 1000.0
                    )
                )

                music_parts.append(
                    f"adelay={delay_ms}:all=1"
                )


            music_label = "amusic"

            filters.append(
                self._join_filter_parts(
                    music_parts,
                    music_label
                )
            )


        # ==============================================
        # FINAL AUDIO MIX
        # ==============================================

        final_audio_label = None


        if (
            narration_label is not None
            and music_label is not None
        ):

            final_audio_label = "aout"

            filters.append(
                f"[{narration_label}]"
                f"[{music_label}]"
                "amix="
                "inputs=2:"
                "duration=longest:"
                "dropout_transition=0:"
                "normalize=0,"
                f"atrim=duration={self._number(timeline_duration)},"
                "asetpts=PTS-STARTPTS"
                f"[{final_audio_label}]"
            )


        elif narration_label is not None:

            final_audio_label = "aout"

            filters.append(
                f"[{narration_label}]"
                f"atrim=duration={self._number(timeline_duration)},"
                "asetpts=PTS-STARTPTS"
                f"[{final_audio_label}]"
            )


        elif music_label is not None:

            final_audio_label = "aout"

            filters.append(
                f"[{music_label}]"
                f"atrim=duration={self._number(timeline_duration)},"
                "asetpts=PTS-STARTPTS"
                f"[{final_audio_label}]"
            )


        filter_complex = ";".join(
            filters
        )


        command.extend([
            "-filter_complex",
            filter_complex,

            "-map",
            "[vout]"
        ])


        if final_audio_label:

            command.extend([
                "-map",
                f"[{final_audio_label}]"
            ])


        # ==============================================
        # OUTPUT SETTINGS
        # ==============================================

        command.extend([
            "-c:v",
            "libx264",

            "-preset",
            "medium",

            "-crf",
            "20",

            "-pix_fmt",
            "yuv420p"
        ])


        if final_audio_label:

            command.extend([
                "-c:a",
                "aac",

                "-b:a",
                "192k",

                "-ar",
                "48000"
            ])


        # Machine-readable FFmpeg progress.
        command.extend([
            "-progress",
            "pipe:1",

            "-nostats",

            "-loglevel",
            "error",

            "-movflags",
            "+faststart",

            str(output_path)
        ])


        # ==============================================
        # SHOW RENDER INFORMATION
        # ==============================================

        print()
        print("=" * 70)
        print("TIMELINE RENDER")
        print("=" * 70)

        print(
            "Project:",
            project.name
        )

        print(
            "Resolution:",
            f"{width}x{height}"
        )

        print(
            "FPS:",
            fps
        )

        print(
            "Video clips:",
            len(video_clips)
        )

        print(
            "Narration:",
            "YES"
            if audio_info
            else "NO"
        )

        print(
            "Music:",
            "YES"
            if music_info
            else "NO"
        )

        print(
            "Duration:",
            timeline_duration
        )

        print()

        print("FFMPEG COMMAND")
        print("-" * 70)

        print(
            " ".join(
                f'"{item}"'
                if " " in item
                else item
                for item in command
            )
        )

        print()


        self._emit_progress(
            progress_callback,
            "rendering",
            5.0,
            "Starting FFmpeg render."
        )


        # ==============================================
        # RUN FFMPEG
        # ==============================================

        self._run_ffmpeg(
            command=command,
            duration_seconds=timeline_duration,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        )


        self._check_cancelled(
            cancel_event
        )


        if not output_path.exists():

            raise TimelineRenderError(
                "Render completed but output "
                "file was not created."
            )


        self._emit_progress(
            progress_callback,
            "finalizing",
            99.0,
            "Finalizing rendered MP4."
        )


        return {
            "success": True,
            "output": str(output_path),
            "video_clips": len(video_clips),
            "has_audio": audio_info is not None,
            "has_narration": audio_info is not None,
            "has_music": music_info is not None,
            "width": width,
            "height": height,
            "fps": fps,
            "duration_seconds": timeline_duration,
        }


    # ==================================================
    # FFMPEG PROCESS
    # ==================================================

    def _run_ffmpeg(
        self,
        *,
        command,
        duration_seconds,
        progress_callback=None,
        cancel_event=None,
    ):

        self._check_cancelled(
            cancel_event
        )


        try:

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

        except OSError as exc:

            raise TimelineRenderError(
                f"Unable to start FFmpeg: {exc}"
            ) from exc


        output_queue = Queue()

        recent_output = deque(
            maxlen=80
        )


        def reader():

            stream = process.stdout

            if stream is None:
                output_queue.put(None)
                return


            try:

                for line in stream:

                    output_queue.put(
                        line
                    )

            finally:

                output_queue.put(
                    None
                )


        reader_thread = Thread(
            target=reader,
            name="timeline-render-ffmpeg-reader",
            daemon=True,
        )

        reader_thread.start()


        reader_finished = False


        try:

            while True:

                if self._is_cancelled(
                    cancel_event
                ):

                    self._terminate_process(
                        process
                    )

                    raise TimelineRenderCancelled(
                        "FFmpeg timeline render was cancelled."
                    )


                try:

                    line = output_queue.get(
                        timeout=0.1
                    )

                except Empty:

                    line = "__NO_LINE__"


                if line is None:

                    reader_finished = True


                elif line != "__NO_LINE__":

                    clean = line.strip()

                    if clean:

                        recent_output.append(
                            clean
                        )

                        self._consume_ffmpeg_progress(
                            clean,
                            duration_seconds,
                            progress_callback,
                        )


                return_code = process.poll()


                if (
                    return_code is not None
                    and reader_finished
                ):

                    break


            reader_thread.join(
                timeout=1.0
            )


        except BaseException:

            if process.poll() is None:

                self._terminate_process(
                    process
                )

            raise


        if process.returncode != 0:

            tail = "\n".join(
                recent_output
            )

            message = (
                "FFmpeg timeline render failed."
            )

            if tail:

                message += (
                    "\n"
                    + tail
                )

            raise TimelineRenderError(
                message
            )


    def _consume_ffmpeg_progress(
        self,
        line,
        duration_seconds,
        progress_callback,
    ):

        if progress_callback is None:
            return


        if "=" not in line:
            return


        key, value = line.split(
            "=",
            1
        )


        if key == "out_time_us":

            try:

                elapsed_seconds = (
                    int(value)
                    / 1_000_000.0
                )

            except (
                TypeError,
                ValueError,
            ):

                return


            self._emit_render_percent(
                elapsed_seconds,
                duration_seconds,
                progress_callback,
            )


        elif key == "out_time":

            elapsed_seconds = (
                self._parse_ffmpeg_time(
                    value
                )
            )


            if elapsed_seconds is not None:

                self._emit_render_percent(
                    elapsed_seconds,
                    duration_seconds,
                    progress_callback,
                )


        elif (
            key == "progress"
            and value == "end"
        ):

            self._emit_progress(
                progress_callback,
                "rendering",
                98.0,
                "FFmpeg encoding complete."
            )


    def _emit_render_percent(
        self,
        elapsed_seconds,
        duration_seconds,
        progress_callback,
    ):

        if duration_seconds <= 0:
            return


        fraction = (
            elapsed_seconds
            / duration_seconds
        )


        fraction = max(
            0.0,
            min(
                1.0,
                fraction
            )
        )


        # Reserve:
        # 0-5   preparation/start
        # 5-98  FFmpeg
        # 99    finalize
        # 100   backend completion
        percent = (
            5.0
            + fraction * 93.0
        )


        self._emit_progress(
            progress_callback,
            "rendering",
            min(
                98.0,
                percent
            ),
            (
                "Rendering "
                f"{elapsed_seconds:.2f}s / "
                f"{duration_seconds:.2f}s"
            )
        )


    # ==================================================
    # AUDIO HELPERS
    # ==================================================

    def _normalize_mix_policy(
        self,
        mix_policy,
    ):

        defaults = {
            "narration_gain_db": 0.0,
            "music_gain_db": -24.0,
            "music_fade_in_seconds": 0.0,
            "music_fade_out_seconds": 0.0,
            "ducking_enabled": False,
            "ducking_reduction_db": 0.0,
            "voice_is_primary": True,
        }


        if mix_policy is None:
            return defaults


        if not isinstance(
            mix_policy,
            dict
        ):

            raise TimelineRenderError(
                "mix_policy must be a dictionary."
            )


        result = dict(
            defaults
        )


        numeric_names = (
            "narration_gain_db",
            "music_gain_db",
            "music_fade_in_seconds",
            "music_fade_out_seconds",
            "ducking_reduction_db",
        )


        for name in numeric_names:

            value = mix_policy.get(
                name,
                result[name]
            )


            if isinstance(
                value,
                bool
            ):

                raise TimelineRenderError(
                    f"{name} must be numeric."
                )


            try:

                value = float(
                    value
                )

            except (
                TypeError,
                ValueError,
            ) as exc:

                raise TimelineRenderError(
                    f"{name} must be numeric."
                ) from exc


            if not isfinite(
                value
            ):

                raise TimelineRenderError(
                    f"{name} must be finite."
                )


            result[name] = value


        if (
            result[
                "music_fade_in_seconds"
            ]
            < 0
        ):

            raise TimelineRenderError(
                "music_fade_in_seconds cannot be negative."
            )


        if (
            result[
                "music_fade_out_seconds"
            ]
            < 0
        ):

            raise TimelineRenderError(
                "music_fade_out_seconds cannot be negative."
            )


        if (
            result[
                "ducking_reduction_db"
            ]
            < 0
        ):

            raise TimelineRenderError(
                "ducking_reduction_db cannot be negative."
            )


        result[
            "ducking_enabled"
        ] = bool(
            mix_policy.get(
                "ducking_enabled",
                result[
                    "ducking_enabled"
                ]
            )
        )


        result[
            "voice_is_primary"
        ] = bool(
            mix_policy.get(
                "voice_is_primary",
                result[
                    "voice_is_primary"
                ]
            )
        )


        return result


    def _join_filter_parts(
        self,
        parts,
        output_label,
    ):

        if not parts:
            raise TimelineRenderError(
                "Audio filter parts are empty."
            )


        first = parts[0]

        remainder = ",".join(
            parts[1:]
        )


        return (
            first
            + remainder
            + f"[{output_label}]"
        )


    # ==================================================
    # PROGRESS / CANCELLATION
    # ==================================================

    def _emit_progress(
        self,
        callback,
        phase,
        percent,
        detail="",
    ):

        if callback is None:
            return


        callback(
            phase,
            float(percent),
            detail,
        )


    def _is_cancelled(
        self,
        cancel_event,
    ):

        if cancel_event is None:
            return False


        is_cancelled = getattr(
            cancel_event,
            "is_cancelled",
            None
        )


        if callable(
            is_cancelled
        ):

            return bool(
                is_cancelled()
            )


        is_set = getattr(
            cancel_event,
            "is_set",
            None
        )


        if callable(
            is_set
        ):

            return bool(
                is_set()
            )


        return False


    def _check_cancelled(
        self,
        cancel_event,
    ):

        if self._is_cancelled(
            cancel_event
        ):

            raise TimelineRenderCancelled(
                "Timeline render was cancelled."
            )


    def _terminate_process(
        self,
        process,
    ):

        if process.poll() is not None:
            return


        try:

            process.terminate()

            process.wait(
                timeout=2.0
            )

            return

        except Exception:
            pass


        try:

            process.kill()

            process.wait(
                timeout=2.0
            )

        except Exception:
            pass


    # ==================================================
    # GENERAL HELPERS
    # ==================================================

    def _number(
        self,
        value,
    ):

        try:

            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise TimelineRenderError(
                f"Invalid numeric value: {value!r}"
            ) from exc


        if not isfinite(
            number
        ):

            raise TimelineRenderError(
                f"Non-finite numeric value: {value!r}"
            )


        text = (
            f"{number:.9f}"
            .rstrip("0")
            .rstrip(".")
        )


        return text or "0"


    def _parse_ffmpeg_time(
        self,
        value,
    ):

        try:

            hours_text, minutes_text, seconds_text = (
                value.split(
                    ":",
                    2
                )
            )

            hours = int(
                hours_text
            )

            minutes = int(
                minutes_text
            )

            seconds = float(
                seconds_text
            )


            return (
                hours * 3600.0
                + minutes * 60.0
                + seconds
            )

        except (
            TypeError,
            ValueError,
        ):

            return None


    # ==================================================
    # VALIDATION
    # ==================================================

    def _validate_video_clips(
        self,
        clips
    ):

        expected_start = 0.0

        tolerance = 0.001


        for clip in clips:

            if not clip.enabled:
                continue


            if clip.duration <= 0:

                raise TimelineRenderError(
                    f"Invalid duration for "
                    f"{clip.id}: {clip.duration}"
                )


            # GAP
            if (
                clip.start
                > expected_start + tolerance
            ):

                raise TimelineRenderError(
                    f"Timeline gap detected before "
                    f"{clip.id}. "
                    f"Expected start: "
                    f"{expected_start}, "
                    f"actual: {clip.start}"
                )


            # OVERLAP
            if (
                clip.start
                < expected_start - tolerance
            ):

                raise TimelineRenderError(
                    f"Timeline overlap detected at "
                    f"{clip.id}. "
                    f"Expected start: "
                    f"{expected_start}, "
                    f"actual: {clip.start}"
                )


            expected_start = (
                clip.start
                + clip.duration
            )