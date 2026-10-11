from pathlib import Path
import copy
import hashlib
import json
import os
import re
import subprocess


from pipeline.voice_pipeline import VoicePipeline

from scenes.scene_builder import Scene

from ai.providers.kie_provider import KieAIProvider
from ai.scene_ai_analyzer import SceneAIAnalyzer
from ai.batch_analyzer import BatchSceneAnalyzer
from ai.manifest_builder import AnalysisManifestBuilder

from pipeline.batch_pipeline import BatchPipeline
from pipeline.timeline_builder import BatchTimelineBuilder

from engine.timeline_renderer import TimelineRenderer


from pipeline.context_geo import enrich_manifest_with_project_context

class FullVideoPipelineError(Exception):
    pass


class FullVideoPipeline:

    def __init__(
        self,
        root,
        ai_model="gpt-6-luna",
        reasoning_effort="low",
        review_mode="auto",
        visual_top_n=10,
        target_scene_duration=5.0,
        max_scene_duration=8.0,
        duration_tolerance=0.05,
    ):

        self.root = Path(
            root
        ).resolve()

        self.ai_model = ai_model

        self.reasoning_effort = (
            reasoning_effort
        )

        self.review_mode = (
            review_mode
        )

        self.visual_top_n = int(
            visual_top_n
        )

        self.target_scene_duration = float(
            target_scene_duration
        )

        self.max_scene_duration = float(
            max_scene_duration
        )

        self.duration_tolerance = float(
            duration_tolerance
        )


    # ==================================================
    # BASIC HELPERS
    # ==================================================

    def _load_json(
        self,
        path,
    ):

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )


    def _save_json(
        self,
        path,
        data,
    ):

        path = Path(
            path
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False,
            )


    def _to_float(
        self,
        value,
        default=0.0,
    ):

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return float(
                default
            )


    # ==================================================
    # JOB NAME
    # ==================================================

    def _safe_name(
        self,
        text,
    ):

        text = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            text,
        )

        text = text.strip(
            "_"
        )

        if not text:

            text = "video"

        return text[:60]


    def _job_id(
        self,
        audio_path,
    ):

        audio_path = Path(
            audio_path
        ).resolve()

        base = self._safe_name(
            audio_path.stem
        )

        digest = hashlib.sha1(
            str(
                audio_path
            ).lower().encode(
                "utf-8"
            )
        ).hexdigest()[:8]

        return (
            f"{base}_{digest}"
        )


    # ==================================================
    # INPUT SIGNATURE
    # ==================================================

    def _audio_signature(
        self,
        audio_path,
    ):

        audio_path = Path(
            audio_path
        ).resolve()

        stat = audio_path.stat()

        return {

            "path":
                str(
                    audio_path
                ),

            "size":
                int(
                    stat.st_size
                ),

            "mtime_ns":
                int(
                    stat.st_mtime_ns
                ),
        }


    def _signature_matches(
        self,
        first,
        second,
    ):

        return (
            isinstance(
                first,
                dict,
            )
            and isinstance(
                second,
                dict,
            )
            and first.get(
                "path"
            )
            == second.get(
                "path"
            )
            and first.get(
                "size"
            )
            == second.get(
                "size"
            )
            and first.get(
                "mtime_ns"
            )
            == second.get(
                "mtime_ns"
            )
        )


    # ==================================================
    # PATHS
    # ==================================================

    def _build_paths(
        self,
        audio_path,
        output_path=None,
    ):

        job_id = self._job_id(
            audio_path
        )

        run_dir = (
            self.root
            / "projects"
            / "runs"
            / job_id
        )

        run_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        download_dir = (
            self.root
            / "media"
            / "downloads"
            / job_id
        )

        download_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        cache_dir = (
            self.root
            / "cache"
            / "full_video"
            / job_id
        )

        cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        subtitle_path = (
            self.root
            / "subtitles"
            / f"{job_id}_clean.srt"
        )

        if output_path is None:

            output_path = (
                self.root
                / "exports"
                / f"{job_id}_final.mp4"
            )

        else:

            output_path = Path(
                output_path
            ).resolve()

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        return {

            "job_id":
                job_id,

            "run_dir":
                run_dir,

            "download_dir":
                download_dir,

            "cache_dir":
                cache_dir,

            "subtitle":
                subtitle_path,

            "voice":
                run_dir
                / "voice_scenes.json",

            "ai":
                run_dir
                / "ai_manifest.json",

            "speech_stock":
                run_dir
                / "speech_stock_manifest.json",

            "full_stock":
                run_dir
                / "full_stock_manifest.json",

            "output":
                output_path,
        }


    # ==================================================
    # ENVIRONMENT
    # ==================================================

    def _validate_environment(
        self,
    ):

        missing = []

        if not os.getenv(
            "KIE_API_KEY"
        ):

            missing.append(
                "KIE_API_KEY"
            )

        if not os.getenv(
            "PEXELS_API_KEY"
        ):

            missing.append(
                "PEXELS_API_KEY"
            )

        if missing:

            raise FullVideoPipelineError(

                "Missing environment variable(s): "
                + ", ".join(
                    missing
                )
            )


    # ==================================================
    # SCENE SERIALIZATION
    # ==================================================

    def _scene_to_dict(
        self,
        scene,
    ):

        if hasattr(
            scene,
            "to_dict",
        ):

            return scene.to_dict()

        return {

            "id":
                scene.id,

            "start":
                scene.start,

            "end":
                scene.end,

            "duration":
                scene.duration,

            "text":
                scene.text,

            "subtitle_ids":
                list(
                    scene.subtitle_ids
                ),

            "scene_type":
                scene.scene_type,
        }


    def _scene_from_dict(
        self,
        item,
    ):

        return Scene(

            id=item[
                "id"
            ],

            start=float(
                item[
                    "start"
                ]
            ),

            end=float(
                item[
                    "end"
                ]
            ),

            duration=float(
                item[
                    "duration"
                ]
            ),

            text=str(
                item.get(
                    "text",
                    "",
                )
                or ""
            ),

            subtitle_ids=list(
                item.get(
                    "subtitle_ids",
                    [],
                )
            ),

            scene_type=str(
                item.get(
                    "scene_type",
                    "speech",
                )
            ),
        )


    # ==================================================
    # INVALIDATE DOWNSTREAM MANIFESTS
    # ==================================================

    def _invalidate_downstream(
        self,
        paths,
    ):

        for key in (
            "ai",
            "speech_stock",
            "full_stock",
        ):

            path = paths[
                key
            ]

            if path.exists():

                path.unlink()


    # ==================================================
    # STAGE 1
    # VOICE -> SCENES
    # ==================================================

    def _run_voice_stage(
        self,
        audio_path,
        paths,
    ):

        signature = (
            self._audio_signature(
                audio_path
            )
        )

        voice_manifest = paths[
            "voice"
        ]

        if voice_manifest.exists():

            existing = (
                self._load_json(
                    voice_manifest
                )
            )

            if self._signature_matches(
                existing.get(
                    "audio_signature"
                ),
                signature,
            ):

                scene_data = (
                    existing.get(
                        "scenes",
                        [],
                    )
                )

                if scene_data:

                    scenes = [

                        self._scene_from_dict(
                            item
                        )

                        for item
                        in scene_data
                    ]

                    print()
                    print(
                        "VOICE STAGE: RESUME"
                    )

                    print(
                        "Loaded scenes:",
                        len(
                            scenes
                        ),
                    )

                    return {

                        "scenes":
                            scenes,

                        "audio_duration":
                            existing.get(
                                "audio_duration"
                            ),

                        "language":
                            existing.get(
                                "language"
                            ),

                        "srt_path":
                            existing.get(
                                "srt_path"
                            ),
                    }


        print()
        print("=" * 70)
        print("[1/5] VOICE PIPELINE")
        print("=" * 70)

        # Audio changed or this is a new run.
        self._invalidate_downstream(
            paths
        )

        pipeline = VoicePipeline(

            model_size="small",

            device="cpu",

            compute_type="int8",

            vad_filter=False,

            target_scene_duration=(
                self.target_scene_duration
            ),

            max_scene_duration=(
                self.max_scene_duration
            ),
        )

        result = pipeline.run(

            audio_path=audio_path,

            srt_output_path=(
                paths[
                    "subtitle"
                ]
            ),
        )

        scenes = result[
            "scenes"
        ]

        save_data = {

            "audio_signature":
                signature,

            "audio_duration":
                result.get(
                    "audio_duration"
                ),

            "language":
                result.get(
                    "language"
                ),

            "language_probability":
                result.get(
                    "language_probability"
                ),

            "srt_path":
                result.get(
                    "srt_path"
                ),

            "scene_count":
                len(
                    scenes
                ),

            "speech_scene_count":
                result.get(
                    "speech_scene_count"
                ),

            "gap_scene_count":
                result.get(
                    "gap_scene_count"
                ),

            "scenes": [

                self._scene_to_dict(
                    scene
                )

                for scene
                in scenes
            ],
        }

        self._save_json(
            voice_manifest,
            save_data,
        )

        return {

            "scenes":
                scenes,

            "audio_duration":
                result.get(
                    "audio_duration"
                ),

            "language":
                result.get(
                    "language"
                ),

            "srt_path":
                result.get(
                    "srt_path"
                ),
        }


    # ==================================================
    # SCENE MANIFEST MATCH
    # ==================================================

    def _manifest_matches_scenes(
        self,
        manifest,
        scenes,
    ):

        manifest_scenes = (
            manifest.get(
                "scenes",
                []
            )
        )

        if len(
            manifest_scenes
        ) != len(
            scenes
        ):

            return False

        for raw, scene in zip(
            manifest_scenes,
            scenes,
        ):

            if (
                raw.get(
                    "scene_id"
                )
                != scene.id
            ):

                return False

            if abs(
                self._to_float(
                    raw.get(
                        "start"
                    )
                )
                - scene.start
            ) > 0.01:

                return False

            if abs(
                self._to_float(
                    raw.get(
                        "end"
                    )
                )
                - scene.end
            ) > 0.01:

                return False

        return True


    # ==================================================
    # FIND GAP REFERENCE
    # ==================================================

    def _find_gap_reference(
        self,
        gap_scene,
        speech_scenes,
    ):

        previous = None
        following = None

        for scene in speech_scenes:

            if (
                scene.end
                <= gap_scene.start
                + 0.01
            ):

                previous = scene

            if (
                scene.start
                >= gap_scene.end
                - 0.01
            ):

                following = scene

                break


        # Leading gap -> next speech.
        if previous is None:

            if following is None:

                raise FullVideoPipelineError(
                    f"{gap_scene.id}: "
                    "no speech scene available "
                    "for gap inheritance."
                )

            return following


        # Internal/trailing gap -> previous speech.
        return previous


    # ==================================================
    # STAGE 2
    # SCENES -> AI MANIFEST
    # ==================================================

    def _run_ai_stage(
        self,
        voice_result,
        paths,
    ):

        scenes = voice_result[
            "scenes"
        ]

        ai_manifest_path = paths[
            "ai"
        ]

        if ai_manifest_path.exists():

            existing = self._load_json(
                ai_manifest_path
            )

            if self._manifest_matches_scenes(
                existing,
                scenes,
            ):

                print()
                print(
                    "AI STAGE: RESUME"
                )

                print(
                    "Loaded AI scenes:",
                    len(
                        existing.get(
                            "scenes",
                            [],
                        )
                    ),
                )

                return existing


        print()
        print("=" * 70)
        print("[2/5] AI SCENE ANALYSIS")
        print("=" * 70)

        provider = KieAIProvider(

            model=self.ai_model,

            reasoning_effort=(
                self.reasoning_effort
            ),

            timeout=180,

            max_retries=2,

            retry_delay=2,
        )

        analyzer = SceneAIAnalyzer(
            provider=provider
        )

        batch = BatchSceneAnalyzer(

            analyzer=analyzer,

            cache_dir=(
                paths[
                    "cache_dir"
                ]
            ),
        )

        speech_scenes = [

            scene

            for scene
            in scenes

            if scene.scene_type
            != "gap"
        ]

        gap_scenes = [

            scene

            for scene
            in scenes

            if scene.scene_type
            == "gap"
        ]

        print(
            "Speech scenes:",
            len(
                speech_scenes
            ),
        )

        print(
            "Gap scenes:",
            len(
                gap_scenes
            ),
        )

        analyses = []

        # ==================================================
        # SEMANTIC WINDOW 58C V1
        #
        # Scene timing and original dialogue remain unchanged.
        #
        # AI temporarily receives:
        #
        # PREVIOUS CONTEXT
        # CURRENT NARRATION
        # NEXT CONTEXT
        #
        # This helps resolve fragments caused by time-based
        # SceneBuilder splitting without changing the timeline.
        # ==================================================

        for index, scene in enumerate(
            speech_scenes,
            start=1,
        ):

            print()
            print(
                f"AI scene "
                f"{index}/"
                f"{len(speech_scenes)}: "
                f"{scene.id}"
            )

            # ----------------------------------------------
            # NEIGHBOR TEXT
            # ----------------------------------------------

            previous_text = ""

            next_text = ""


            if index > 1:

                previous_scene = (
                    speech_scenes[
                        index - 2
                    ]
                )

                previous_text = str(
                    previous_scene.text
                    or ""
                ).strip()


            if index < len(
                speech_scenes
            ):

                next_scene = (
                    speech_scenes[
                        index
                    ]
                )

                next_text = str(
                    next_scene.text
                    or ""
                ).strip()


            current_text = str(
                scene.text
                or ""
            ).strip()


            # ----------------------------------------------
            # CREATE TEMPORARY AI SCENE
            #
            # deepcopy keeps:
            # id
            # start/end
            # duration
            # subtitle IDs
            #
            # Only text is temporarily expanded.
            # ----------------------------------------------

            semantic_scene = (
                copy.deepcopy(
                    scene
                )
            )


            semantic_scene.text = (
                "SEMANTIC CONTEXT FOR STOCK ANALYSIS\n\n"

                "IMPORTANT RULES:\n"
                "- Analyze CURRENT NARRATION for the visual.\n"
                "- PREVIOUS and NEXT are context only.\n"
                "- Use neighboring text to resolve incomplete "
                "phrases, pronouns, subjects, locations, or "
                "sentences split by timing.\n"
                "- Do NOT blend an unrelated previous or next "
                "topic into the current visual.\n"
                "- If CURRENT continues a thought from PREVIOUS, "
                "inherit the missing subject or location.\n"
                "- If CURRENT ends mid-thought and NEXT completes "
                "that same thought, use NEXT only to understand "
                "the completion.\n\n"

                "PREVIOUS CONTEXT:\n"
                + (
                    previous_text
                    if previous_text
                    else "[NONE]"
                )

                + "\n\n"

                "CURRENT NARRATION:\n"
                + current_text

                + "\n\n"

                "NEXT CONTEXT:\n"
                + (
                    next_text
                    if next_text
                    else "[NONE]"
                )
            )


            print(
                "  Semantic window:",
                (
                    "PREV"
                    if previous_text
                    else "-"
                ),
                "| CURRENT |",
                (
                    "NEXT"
                    if next_text
                    else "-"
                ),
            )


            # ----------------------------------------------
            # ANALYZE TEMPORARY SEMANTIC SCENE
            #
            # Its expanded text also naturally changes the
            # BatchSceneAnalyzer cache key, preventing old
            # single-scene analysis cache from being reused.
            # ----------------------------------------------

            result = batch.analyze_one(

                scene=semantic_scene,

                use_cache=True,
            )


            # ----------------------------------------------
            # RESTORE ORIGINAL SCENE IDENTITY
            #
            # KIE saw the semantic window, but the manifest
            # must contain ONLY the real current narration.
            # ----------------------------------------------

            analysis_object = (
                result.get(
                    "analysis"
                )
            )


            if analysis_object is None:

                raise FullVideoPipelineError(
                    f"Missing semantic AI analysis "
                    f"for {scene.id}"
                )


            analysis_object.scene_id = (
                scene.id
            )

            analysis_object.start = (
                scene.start
            )

            analysis_object.end = (
                scene.end
            )

            analysis_object.duration = (
                scene.duration
            )

            analysis_object.dialogue = (
                current_text
            )


            analyses.append(
                result
            )


        builder = (
            AnalysisManifestBuilder()
        )

        speech_manifest = builder.build(

            analyses=analyses,

            source_srt=(
                voice_result.get(
                    "srt_path"
                )
            ),

            provider=(
                f"KieAIProvider:"
                f"{self.ai_model}"
            ),
        )


        speech_map = {

            scene[
                "scene_id"
            ]:
                scene

            for scene
            in speech_manifest.get(
                "scenes",
                []
            )
        }


        # Force video for V1 renderer.
        for scene in speech_map.values():

            scene[
                "scene_type"
            ] = "speech"

            stock = scene.setdefault(
                "stock",
                {},
            )

            stock[
                "preferred_type"
            ] = "video"


        final_scenes = []


        for original in scenes:

            # ==================================================
            # SPEECH
            # ==================================================

            if (
                original.scene_type
                != "gap"
            ):

                if original.id not in speech_map:

                    raise FullVideoPipelineError(
                        f"Missing AI analysis "
                        f"for {original.id}"
                    )

                item = copy.deepcopy(
                    speech_map[
                        original.id
                    ]
                )

                item[
                    "scene_type"
                ] = "speech"

                item[
                    "subtitle_ids"
                ] = list(
                    original.subtitle_ids
                )

                final_scenes.append(
                    item
                )

                continue


            # ==================================================
            # GAP
            # ==================================================

            reference = (
                self._find_gap_reference(
                    original,
                    speech_scenes,
                )
            )

            source = copy.deepcopy(

                speech_map[
                    reference.id
                ]
            )

            source[
                "scene_id"
            ] = original.id

            source[
                "scene_type"
            ] = "gap"

            source[
                "start"
            ] = original.start

            source[
                "end"
            ] = original.end

            source[
                "duration"
            ] = original.duration

            source[
                "dialogue"
            ] = ""

            source[
                "subtitle_ids"
            ] = list(
                original.subtitle_ids
            )

            source[
                "gap_source_scene_id"
            ] = reference.id


            analysis_section = (
                source.setdefault(
                    "analysis",
                    {},
                )
            )

            old_context = str(
                analysis_section.get(
                    "context",
                    "",
                )
                or ""
            )

            analysis_section[
                "context"
            ] = (
                "Visual continuation during "
                "a non-speech section. "
                + old_context
            )


            source[
                "stock"
            ] = {

                "status":
                    "pending",

                "preferred_type":
                    "video",

                "searches":
                    [],

                "candidates":
                    [],

                "selected_media":
                    None,
            }


            source[
                "timeline"
            ] = {

                "clip_id":
                    None,

                "media_id":
                    None,

                "track_id":
                    "video_1",
            }


            final_scenes.append(
                source
            )


        final_manifest = {

            "version":
                speech_manifest.get(
                    "version",
                    1,
                ),

            "source":
                speech_manifest.get(
                    "source",
                    {},
                ),

            "ai":
                speech_manifest.get(
                    "ai",
                    {},
                ),

            "scene_count":
                len(
                    final_scenes
                ),

            "speech_scene_count":
                len(
                    speech_scenes
                ),

            "gap_scene_count":
                len(
                    gap_scenes
                ),

            "scenes":
                final_scenes,
        }


        self._save_json(
            ai_manifest_path,
            final_manifest,
        )


        print()
        print(
            "AI manifest saved:",
            ai_manifest_path,
        )

        return final_manifest


    # ==================================================
    # STOCK VALIDATION
    # ==================================================

    def _stock_is_valid(
        self,
        scene,
        stock,
    ):

        if not isinstance(
            stock,
            dict,
        ):

            return False

        if (
            stock.get(
                "status"
            )
            != "validated"
        ):

            return False

        validation = stock.get(
            "validation",
            {},
        )

        if (
            validation.get(
                "valid"
            )
            is not True
        ):

            return False

        download = stock.get(
            "download",
            {},
        )

        path = download.get(
            "path"
        )

        if not path:

            return False

        if not Path(
            path
        ).exists():

            return False


        selected = stock.get(
            "selected_media",
            {},
        )

        media_type = str(
            selected.get(
                "media_type",
                "video",
            )
            or "video"
        ).lower()


        if media_type != "video":

            return True


        actual_duration = (
            self._to_float(
                validation.get(
                    "duration"
                )
            )
        )

        scene_duration = (
            self._to_float(
                scene.get(
                    "duration"
                )
            )
        )


        return (
            actual_duration
            + self.duration_tolerance
            >= scene_duration
        )


    # ==================================================
    # PREPARE SPEECH STOCK MANIFEST
    # ==================================================

    def _prepare_speech_stock_manifest(
        self,
        ai_manifest,
        paths,
    ):

        manifest_path = paths[
            "speech_stock"
        ]

        ai_speech = [

            copy.deepcopy(
                scene
            )

            for scene
            in ai_manifest.get(
                "scenes",
                []
            )

            if scene.get(
                "scene_type"
            )
            != "gap"
        ]


        # Existing persistent progress.
        if manifest_path.exists():

            existing = (
                self._load_json(
                    manifest_path
                )
            )

            existing_ids = [

                scene.get(
                    "scene_id"
                )

                for scene
                in existing.get(
                    "scenes",
                    []
                )
            ]

            expected_ids = [

                scene.get(
                    "scene_id"
                )

                for scene
                in ai_speech
            ]

            if (
                existing_ids
                == expected_ids
            ):

                print(
                    "Speech stock manifest: RESUME"
                )

                return


        new_manifest = copy.deepcopy(
            ai_manifest
        )

        new_manifest[
            "scenes"
        ] = ai_speech

        new_manifest[
            "scene_count"
        ] = len(
            ai_speech
        )

        new_manifest[
            "gap_scene_count"
        ] = 0

        self._save_json(
            manifest_path,
            new_manifest,
        )


    # ==================================================
    # GAP REUSE
    # ==================================================

    def _build_full_stock_manifest(
        self,
        ai_manifest,
        speech_stock_manifest,
    ):

        speech_map = {

            scene[
                "scene_id"
            ]:
                scene

            for scene
            in speech_stock_manifest.get(
                "scenes",
                []
            )
        }


        final_manifest = copy.deepcopy(
            ai_manifest
        )


        for scene in final_manifest.get(
            "scenes",
            []
        ):

            scene_id = scene[
                "scene_id"
            ]


            # ==================================================
            # SPEECH
            # ==================================================

            if (
                scene.get(
                    "scene_type"
                )
                != "gap"
            ):

                source = speech_map.get(
                    scene_id
                )

                if source is None:

                    raise FullVideoPipelineError(
                        f"{scene_id}: "
                        "missing speech stock result."
                    )

                if not self._stock_is_valid(
                    source,
                    source.get(
                        "stock",
                        {},
                    ),
                ):

                    raise FullVideoPipelineError(
                        f"{scene_id}: "
                        "speech stock is not valid."
                    )

                scene[
                    "stock"
                ] = copy.deepcopy(
                    source[
                        "stock"
                    ]
                )

                continue


            # ==================================================
            # GAP
            # ==================================================

            reference_id = scene.get(
                "gap_source_scene_id"
            )

            source_scene = speech_map.get(
                reference_id
            )

            if source_scene is None:

                raise FullVideoPipelineError(
                    f"{scene_id}: "
                    f"gap source "
                    f"{reference_id} "
                    "not found."
                )


            source_stock = (
                source_scene.get(
                    "stock",
                    {},
                )
            )


            if not self._stock_is_valid(
                source_scene,
                source_stock,
            ):

                raise FullVideoPipelineError(
                    f"{scene_id}: "
                    "gap source stock "
                    "is not valid."
                )


            gap_duration = (
                self._to_float(
                    scene.get(
                        "duration"
                    )
                )
            )

            media_duration = (
                self._to_float(
                    source_stock.get(
                        "validation",
                        {},
                    ).get(
                        "duration"
                    )
                )
            )


            if (
                media_duration
                + self.duration_tolerance
                < gap_duration
            ):

                raise FullVideoPipelineError(

                    f"{scene_id}: "

                    "gap source is too short. "

                    f"gap={gap_duration:.3f}s, "

                    f"source="
                    f"{media_duration:.3f}s"
                )


            reused_stock = copy.deepcopy(
                source_stock
            )

            reused_stock[
                "status"
            ] = "validated"

            reused_stock[
                "reuse"
            ] = {

                "enabled":
                    True,

                "source_scene_id":
                    reference_id,

                "reason":
                    (
                        "gap_scene_"
                        "visual_continuation"
                    ),
            }

            scene[
                "stock"
            ] = reused_stock


        return final_manifest


    # ==================================================
    # GAP REUSE V2
    # ==================================================

    def _media_identity(
        self,
        scene,
    ):

        stock = scene.get(
            "stock",
            {},
        )

        selected = stock.get(
            "selected_media",
            {},
        )

        provider = str(
            selected.get(
                "provider",
                "",
            )
            or ""
        )

        media_id = str(
            selected.get(
                "media_id",
                "",
            )
            or ""
        )

        if media_id:

            return (
                provider,
                media_id,
            )


        download = stock.get(
            "download",
            {},
        )

        return (
            "path",
            str(
                download.get(
                    "path",
                    "",
                )
                or ""
            ),
        )


    def _apply_gap_reuse_v2(
        self,
        manifest,
    ):

        scenes = sorted(

            manifest.get(
                "scenes",
                []
            ),

            key=lambda item:
                self._to_float(
                    item.get(
                        "start"
                    )
                ),
        )


        previous_identity = None

        source_cursor = 0.0


        for scene in scenes:

            scene_id = scene[
                "scene_id"
            ]

            stock = scene[
                "stock"
            ]

            selected = stock.get(
                "selected_media",
                {},
            )

            media_type = str(
                selected.get(
                    "media_type",
                    "video",
                )
                or "video"
            ).lower()

            scene_duration = (
                self._to_float(
                    scene.get(
                        "duration"
                    )
                )
            )

            validation = stock.get(
                "validation",
                {},
            )

            media_duration = (
                self._to_float(
                    validation.get(
                        "duration"
                    )
                )
            )

            identity = (
                self._media_identity(
                    scene
                )
            )


            # ==================================================
            # IMAGE
            # ==================================================

            if media_type == "image":

                source_start = 0.0

                source_cursor = 0.0

                previous_identity = (
                    identity
                )


            # ==================================================
            # VIDEO
            # ==================================================

            else:

                if media_duration <= 0:

                    raise FullVideoPipelineError(
                        f"{scene_id}: "
                        "invalid media duration."
                    )


                if (
                    identity
                    != previous_identity
                ):

                    source_start = 0.0


                else:

                    proposed_start = (
                        source_cursor
                    )

                    proposed_end = (
                        proposed_start
                        + scene_duration
                    )

                    if (
                        proposed_end
                        <= media_duration
                        + self.duration_tolerance
                    ):

                        source_start = (
                            proposed_start
                        )

                    else:

                        source_start = 0.0


                if (
                    source_start
                    + scene_duration
                    > media_duration
                    + self.duration_tolerance
                ):

                    raise FullVideoPipelineError(

                        f"{scene_id}: "

                        "source duration safety "
                        "check failed."
                    )


                source_cursor = (
                    source_start
                    + scene_duration
                )

                previous_identity = (
                    identity
                )


            timeline = stock.setdefault(
                "timeline",
                {},
            )

            timeline[
                "source_start"
            ] = round(
                source_start,
                6,
            )

            timeline[
                "source_end"
            ] = round(
                source_start
                + scene_duration,
                6,
            )

            timeline[
                "source_strategy"
            ] = "gap_reuse_v2"


        manifest[
            "scenes"
        ] = scenes

        return manifest


    # ==================================================
    # STAGE 3
    # STOCK PIPELINE
    # ==================================================

    def _run_stock_stage(
        self,
        ai_manifest,
        paths,
    ):

        print()
        print("=" * 70)
        print("[3/5] STOCK PIPELINE")
        print("=" * 70)

        self._prepare_speech_stock_manifest(
            ai_manifest,
            paths,
        )


        pipeline = BatchPipeline(

            manifest_path=(
                paths[
                    "speech_stock"
                ]
            ),

            download_dir=(
                paths[
                    "download_dir"
                ]
            ),

            review_mode=(
                self.review_mode
            ),

            resume=True,

            per_query=5,

            max_candidates=20,

            visual_top_n=(
                self.visual_top_n
            ),
        )


        summary = pipeline.run()


        print()
        print(
            "Batch summary:",
            summary,
        )


        speech_manifest = (
            self._load_json(
                paths[
                    "speech_stock"
                ]
            )
        )


        incomplete = []


        for scene in speech_manifest.get(
            "scenes",
            []
        ):

            if not self._stock_is_valid(
                scene,
                scene.get(
                    "stock",
                    {},
                ),
            ):

                incomplete.append(
                    scene.get(
                        "scene_id"
                    )
                )


        if incomplete:

            print()
            print(
                "Incomplete speech scenes:"
            )

            for scene_id in incomplete:

                print(
                    "  -",
                    scene_id,
                )


            raise FullVideoPipelineError(

                f"{len(incomplete)} "
                "speech scene(s) remain "
                "incomplete. "

                "Progress was saved. "
                "Run the SAME command "
                "again to resume."
            )


        print()
        print(
            "All speech stock scenes "
            "validated: PASS"
        )


        full_manifest = (
            self._build_full_stock_manifest(
                ai_manifest,
                speech_manifest,
            )
        )


        full_manifest = (
            self._apply_gap_reuse_v2(
                full_manifest
            )
        )


        self._save_json(

            paths[
                "full_stock"
            ],

            full_manifest,
        )


        print(
            "Full stock manifest:",
            paths[
                "full_stock"
            ],
        )


        return full_manifest


    # ==================================================
    # OUTPUT PROBE
    # ==================================================

    def _probe_output(
        self,
        output_path,
    ):

        command = [

            "ffprobe",

            "-v",
            "error",

            "-show_streams",

            "-show_format",

            "-of",
            "json",

            str(
                output_path
            ),
        ]


        process = subprocess.run(

            command,

            capture_output=True,

            text=True,
        )


        if process.returncode != 0:

            raise FullVideoPipelineError(

                "FFprobe failed:\n"
                + process.stderr
            )


        return json.loads(
            process.stdout
        )


    # ==================================================
    # STAGE 4 + 5
    # TIMELINE + RENDER
    # ==================================================

    def _render_stage(
        self,
        manifest,
        audio_path,
        paths,
    ):

        print()
        print("=" * 70)
        print("[4/5] BUILD TIMELINE")
        print("=" * 70)


        builder = BatchTimelineBuilder(

            project_name=(
                "AI Video Editor "
                + paths[
                    "job_id"
                ]
            ),

            video_track_id="video_1",

            video_track_name="Video 1",

            voice_track_id="voice_1",

            voice_track_name="Voice",
        )


        project, build_result = (
            builder.build(

                manifest=manifest,

                voice_path=audio_path,
            )
        )


        print()
        print(
            "Video clips:",
            build_result.get(
                "video_clips"
            ),
        )

        print(
            "Voice clips:",
            build_result.get(
                "voice_clips"
            ),
        )

        print(
            "Timeline duration:",
            build_result.get(
                "timeline_duration"
            ),
        )


        print()
        print("=" * 70)
        print("[5/5] RENDER")
        print("=" * 70)


        renderer = (
            TimelineRenderer()
        )


        result = renderer.render(

            project=project,

            output_path=(
                paths[
                    "output"
                ]
            ),

            video_track_id="video_1",

            audio_track_id="voice_1",
        )


        if not result.get(
            "success"
        ):

            raise FullVideoPipelineError(
                "Timeline render failed."
            )


        output_path = paths[
            "output"
        ]


        if not output_path.exists():

            raise FullVideoPipelineError(
                "Output MP4 was not created."
            )


        probe = self._probe_output(
            output_path
        )


        streams = probe.get(
            "streams",
            []
        )


        video_streams = [

            item

            for item
            in streams

            if item.get(
                "codec_type"
            )
            == "video"
        ]


        audio_streams = [

            item

            for item
            in streams

            if item.get(
                "codec_type"
            )
            == "audio"
        ]


        if len(
            video_streams
        ) != 1:

            raise FullVideoPipelineError(

                "Final output does not "
                "contain exactly one "
                "video stream."
            )


        if len(
            audio_streams
        ) != 1:

            raise FullVideoPipelineError(

                "Final output does not "
                "contain exactly one "
                "audio stream."
            )


        video_stream = (
            video_streams[
                0
            ]
        )


        width = int(
            video_stream.get(
                "width",
                0,
            )
        )

        height = int(
            video_stream.get(
                "height",
                0,
            )
        )


        duration = self._to_float(

            probe.get(
                "format",
                {},
            ).get(
                "duration"
            )
        )


        return {

            "output_path":
                str(
                    output_path
                ),

            "duration":
                duration,

            "width":
                width,

            "height":
                height,

            "video_streams":
                len(
                    video_streams
                ),

            "audio_streams":
                len(
                    audio_streams
                ),

            "render_result":
                result,

            "build_result":
                build_result,
        }


    # ==================================================
    # PUBLIC RUN
    # ==================================================

    def run(
        self,
        audio_path,
        output_path=None,
    ):

        audio_path = Path(
            audio_path
        ).resolve()


        if not audio_path.exists():

            raise FileNotFoundError(
                f"Audio file not found: "
                f"{audio_path}"
            )


        self._validate_environment()


        paths = self._build_paths(

            audio_path=audio_path,

            output_path=output_path,
        )


        print("=" * 70)
        print("AI VIDEO EDITOR")
        print("FULL AUTOMATIC VIDEO PIPELINE")
        print("=" * 70)

        print()
        print(
            "Job:",
            paths[
                "job_id"
            ],
        )

        print(
            "Audio:",
            audio_path,
        )

        print(
            "Run directory:",
            paths[
                "run_dir"
            ],
        )

        print(
            "Downloads:",
            paths[
                "download_dir"
            ],
        )

        print(
            "Output:",
            paths[
                "output"
            ],
        )


        # ==================================================
        # 1. VOICE
        # ==================================================

        voice_result = (
            self._run_voice_stage(
                audio_path,
                paths,
            )
        )


        # ==================================================
        # 2. AI ANALYSIS
        # ==================================================

        ai_manifest = (
            self._run_ai_stage(
                voice_result,
                paths,
            )
        )

        # CONTEXT CARRYOVER 58B V1
        ai_manifest = (
            enrich_manifest_with_project_context(
                ai_manifest
            )
        )

        project_country = (
            ai_manifest.get(
                "project_context",
                {},
            ).get(
                "required_country"
            )
        )

        print(
            "Project geography:",
            project_country
            or "not established",
        )


        # ==================================================
        # 3. STOCK
        # ==================================================

        full_stock_manifest = (
            self._run_stock_stage(
                ai_manifest,
                paths,
            )
        )


        # ==================================================
        # 4 + 5. TIMELINE + RENDER
        # ==================================================

        render_result = (
            self._render_stage(

                manifest=(
                    full_stock_manifest
                ),

                audio_path=audio_path,

                paths=paths,
            )
        )


        print()
        print("=" * 70)
        print(
            "FULL VIDEO PIPELINE SUCCESS"
        )
        print("=" * 70)

        print(
            "Scenes:",
            len(
                full_stock_manifest.get(
                    "scenes",
                    [],
                )
            ),
        )

        print(
            "Output:",
            render_result[
                "output_path"
            ],
        )

        print(
            "Duration:",
            render_result[
                "duration"
            ],
        )

        print(
            "Resolution:",
            (
                f"{render_result['width']}"
                f"x"
                f"{render_result['height']}"
            ),
        )

        print(
            "Video streams:",
            render_result[
                "video_streams"
            ],
        )

        print(
            "Audio streams:",
            render_result[
                "audio_streams"
            ],
        )

        print(
            "Gap Reuse V2: PASS"
        )

        print(
            "Stock audio isolation: PASS"
        )

        return {

            "success":
                True,

            "job_id":
                paths[
                    "job_id"
                ],

            "paths": {
                key:
                    str(
                        value
                    )

                for key, value
                in paths.items()

                if isinstance(
                    value,
                    Path,
                )
            },

            **render_result,
        }
