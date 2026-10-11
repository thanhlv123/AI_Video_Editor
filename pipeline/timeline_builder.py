from pathlib import Path

from core.project import Project
from core.timeline import Track
from core.operations import OperationManager
from automation.executor import CommandExecutor


class BatchTimelineBuilder:

    def __init__(
        self,
        project_name="AI Video Editor Batch Timeline",
        video_track_id="video_1",
        video_track_name="Video 1",
        voice_track_id="voice_1",
        voice_track_name="Voice"
    ):

        self.project_name = project_name

        self.video_track_id = video_track_id
        self.video_track_name = video_track_name

        self.voice_track_id = voice_track_id
        self.voice_track_name = voice_track_name


    # ==================================================
    # BUILD PROJECT FROM MANIFEST
    # ==================================================

    def build(
        self,
        manifest,
        voice_path=None
    ):

        # ==============================================
        # VALIDATE MANIFEST
        # ==============================================

        if not isinstance(
            manifest,
            dict
        ):

            raise ValueError(
                "Manifest must be a dictionary."
            )


        scenes = manifest.get(
            "scenes",
            []
        )


        if not scenes:

            raise ValueError(
                "Manifest contains no scenes."
            )


        # ==============================================
        # CREATE PROJECT
        # ==============================================

        project = Project(
            name=self.project_name
        )


        # ==============================================
        # CREATE VIDEO TRACK
        # ==============================================

        video_track = Track(

            id=self.video_track_id,

            name=self.video_track_name,

            track_type="video"
        )


        project.timeline.add_track(
            video_track
        )


        # ==============================================
        # CREATE VOICE TRACK
        # ==============================================

        voice_track = Track(

            id=self.voice_track_id,

            name=self.voice_track_name,

            track_type="audio"
        )


        project.timeline.add_track(
            voice_track
        )


        # ==============================================
        # AUTOMATION
        # ==============================================

        operations = OperationManager(
            project
        )


        executor = CommandExecutor(
            operations
        )


        # ==============================================
        # RESULT INFORMATION
        # ==============================================

        build_result = {

            "total_scenes": len(
                scenes
            ),

            "validated_scenes": 0,

            "skipped_scenes": 0,

            "imported_media": 0,

            "created_clips": 0,

            "video_clips": 0,

            "voice_clips": 0,

            "timeline_duration": 0.0,

            "voice_added": False,

            "voice_duration": 0.0,

            "project_revision": 0,

            "scenes": []
        }


        # ==============================================
        # SORT SCENES
        # ==============================================

        sorted_scenes = sorted(

            scenes,

            key=lambda item: float(
                item.get(
                    "start",
                    0.0
                )
            )
        )


        # ==============================================
        # PROCESS VIDEO SCENES
        # ==============================================

        for scene in sorted_scenes:

            scene_id = scene.get(
                "scene_id"
            )


            print()
            print("-" * 70)

            print(
                "Processing:",
                scene_id
            )


            # ==========================================
            # SCENE ID
            # ==========================================

            if not scene_id:

                print(
                    "Skipped: missing scene_id"
                )

                build_result[
                    "skipped_scenes"
                ] += 1

                continue


            stock = scene.get(
                "stock",
                {}
            )


            status = stock.get(
                "status"
            )


            # ==========================================
            # ONLY VALIDATED STOCK
            # ==========================================

            if status != "validated":

                print(
                    "Skipped:",
                    f"stock status = {status}"
                )

                build_result[
                    "skipped_scenes"
                ] += 1


                build_result[
                    "scenes"
                ].append({

                    "scene_id": scene_id,

                    "status": "skipped",

                    "reason": (
                        "Stock media is not validated."
                    )
                })

                continue


            build_result[
                "validated_scenes"
            ] += 1


            # ==========================================
            # DOWNLOADED MEDIA
            # ==========================================

            download = stock.get(
                "download",
                {}
            )


            media_path = download.get(
                "path"
            )


            if not media_path:

                raise ValueError(
                    f"{scene_id}: "
                    "download path is missing."
                )


            media_path = Path(
                media_path
            )


            if not media_path.exists():

                raise FileNotFoundError(
                    f"{scene_id}: "
                    f"media file not found: "
                    f"{media_path}"
                )


            # ==========================================
            # TIMING
            # ==========================================

            scene_start = float(
                scene.get(
                    "start",
                    0.0
                )
            )


            scene_duration = float(
                scene.get(
                    "duration",
                    0.0
                )
            )


            if scene_duration <= 0:

                scene_end = float(
                    scene.get(
                        "end",
                        scene_start
                    )
                )

                scene_duration = (
                    scene_end
                    - scene_start
                )


            if scene_duration <= 0:

                raise ValueError(
                    f"{scene_id}: "
                    "invalid scene duration."
                )


            # ==========================================
            # SELECTED MEDIA
            # ==========================================

            selected_media = stock.get(
                "selected_media",
                {}
            )


            provider = selected_media.get(
                "provider",
                "stock"
            )


            provider_media_id = (
                selected_media.get(
                    "media_id"
                )
            )


            if provider_media_id:

                media_id = (
                    f"stock_"
                    f"{provider}_"
                    f"{provider_media_id}"
                )

            else:

                media_id = (
                    f"stock_{scene_id}"
                )


            # ==========================================
            # EXISTING TIMELINE INFORMATION
            # ==========================================

            timeline_info = stock.get(
                "timeline",
                {}
            )


            existing_media_id = (
                timeline_info.get(
                    "media_id"
                )
            )


            if existing_media_id:

                media_id = (
                    existing_media_id
                )


            clip_id = (
                timeline_info.get(
                    "clip_id"
                )
            )


            if not clip_id:

                clip_id = (
                    f"clip_{scene_id}"
                )


            source_start = float(
                timeline_info.get(
                    "source_start",
                    0.0
                )
            )


            # ==========================================
            # VALIDATE SOURCE DURATION
            # ==========================================

            validation = stock.get(
                "validation",
                {}
            )


            media_duration = float(
                validation.get(
                    "duration",
                    0.0
                )
                or 0.0
            )


            if media_duration > 0:

                available_duration = (
                    media_duration
                    - source_start
                )


                if (
                    scene_duration
                    > available_duration
                ):

                    raise ValueError(

                        f"{scene_id}: "
                        f"scene duration "
                        f"{scene_duration:.3f}s "
                        f"is longer than available "
                        f"source duration "
                        f"{available_duration:.3f}s."
                    )


            # ==========================================
            # IMPORT VIDEO MEDIA
            # ==========================================

            if (
                project.get_media(
                    media_id
                )
                is None
            ):

                executor.execute({

                    "command": (
                        "media.import"
                    ),

                    "parameters": {

                        "path": str(
                            media_path
                        ),

                        "media_id": (
                            media_id
                        )
                    }
                })


                build_result[
                    "imported_media"
                ] += 1


                print(
                    "Imported:",
                    media_id
                )


            # ==========================================
            # ADD VIDEO CLIP
            # ==========================================

            executor.execute({

                "command": (
                    "timeline.add_clip"
                ),

                "parameters": {

                    "clip_id": (
                        clip_id
                    ),

                    "media_id": (
                        media_id
                    ),

                    "track_id": (
                        self.video_track_id
                    ),

                    "start": (
                        scene_start
                    ),

                    "duration": (
                        scene_duration
                    ),

                    "source_start": (
                        source_start
                    ),

                    "author": (
                        "batch_timeline_builder"
                    )
                }
            })


            build_result[
                "created_clips"
            ] += 1


            build_result[
                "video_clips"
            ] += 1


            print(
                "Clip:",
                clip_id
            )

            print(
                "Timeline:",
                f"{scene_start:.3f}"
                " -> "
                f"{scene_start + scene_duration:.3f}"
            )

            print(
                "Duration:",
                f"{scene_duration:.3f}"
            )

            print(
                "Source start:",
                f"{source_start:.3f}"
            )


            # ==========================================
            # UPDATE MANIFEST TIMELINE
            # ==========================================

            stock[
                "timeline"
            ] = {

                "clip_id": (
                    clip_id
                ),

                "media_id": (
                    media_id
                ),

                "track_id": (
                    self.video_track_id
                ),

                "start": (
                    scene_start
                ),

                "duration": (
                    scene_duration
                ),

                "source_start": (
                    source_start
                )
            }


            # ==========================================
            # RESULT
            # ==========================================

            build_result[
                "scenes"
            ].append({

                "scene_id": (
                    scene_id
                ),

                "status": (
                    "timeline_ready"
                ),

                "media_id": (
                    media_id
                ),

                "clip_id": (
                    clip_id
                ),

                "track_id": (
                    self.video_track_id
                ),

                "start": (
                    scene_start
                ),

                "duration": (
                    scene_duration
                ),

                "end": (
                    scene_start
                    + scene_duration
                ),

                "source_start": (
                    source_start
                ),

                "media_path": str(
                    media_path
                )
            })


        # ==============================================
        # REQUIRE VIDEO CLIPS
        # ==============================================

        if not video_track.clips:

            raise RuntimeError(
                "No timeline video clips were created."
            )


        # ==============================================
        # SORT VIDEO CLIPS
        # ==============================================

        video_track.clips.sort(
            key=lambda clip: clip.start
        )


        # ==============================================
        # CALCULATE VIDEO TIMELINE DURATION
        # ==============================================

        timeline_duration = 0.0


        for clip in video_track.clips:

            timeline_duration = max(
                timeline_duration,
                clip.end
            )


        build_result[
            "timeline_duration"
        ] = timeline_duration


        # ==============================================
        # OPTIONAL VOICE
        # ==============================================

        if voice_path is not None:

            print()
            print("=" * 70)
            print("ADDING VOICE")
            print("=" * 70)


            voice_path = Path(
                voice_path
            )


            if not voice_path.exists():

                raise FileNotFoundError(
                    f"Voice file not found: "
                    f"{voice_path}"
                )


            # ==========================================
            # IMPORT VOICE
            # ==========================================

            voice_media_id = (
                "voice_main"
            )


            executor.execute({

                "command": (
                    "media.import"
                ),

                "parameters": {

                    "path": str(
                        voice_path
                    ),

                    "media_id": (
                        voice_media_id
                    )
                }
            })


            build_result[
                "imported_media"
            ] += 1


            voice_media = (
                project.get_media(
                    voice_media_id
                )
            )


            if voice_media is None:

                raise RuntimeError(
                    "Voice import failed."
                )


            voice_duration = float(
                voice_media.duration
            )


            build_result[
                "voice_duration"
            ] = voice_duration


            print(
                "Voice file:",
                voice_path.name
            )

            print(
                "Voice duration:",
                voice_duration
            )

            print(
                "Timeline duration:",
                timeline_duration
            )


            # ==========================================
            # VALIDATE VOICE LENGTH
            # ==========================================

            tolerance = 0.05


            if (
                voice_duration
                + tolerance
                < timeline_duration
            ):

                raise ValueError(

                    "Voice is shorter than "
                    "the video timeline. "
                    f"Voice: "
                    f"{voice_duration:.3f}s, "
                    f"timeline: "
                    f"{timeline_duration:.3f}s."
                )


            # ==========================================
            # VOICE CLIP DURATION
            # ==========================================

            voice_clip_duration = min(
                voice_duration,
                timeline_duration
            )


            # ==========================================
            # ADD VOICE CLIP
            # ==========================================

            executor.execute({

                "command": (
                    "timeline.add_clip"
                ),

                "parameters": {

                    "clip_id": (
                        "clip_voice_main"
                    ),

                    "media_id": (
                        voice_media_id
                    ),

                    "track_id": (
                        self.voice_track_id
                    ),

                    "start": 0.0,

                    "duration": (
                        voice_clip_duration
                    ),

                    "source_start": 0.0,

                    "author": (
                        "batch_timeline_builder"
                    )
                }
            })


            build_result[
                "created_clips"
            ] += 1


            build_result[
                "voice_clips"
            ] += 1


            build_result[
                "voice_added"
            ] = True


            print(
                "Voice media ID:",
                voice_media_id
            )

            print(
                "Voice clip:",
                "clip_voice_main"
            )

            print(
                "Voice timeline:",
                "0.000"
                " -> "
                f"{voice_clip_duration:.3f}"
            )


        # ==============================================
        # FINAL REVISION
        # ==============================================

        build_result[
            "project_revision"
        ] = project.revision


        return (
            project,
            build_result
        )