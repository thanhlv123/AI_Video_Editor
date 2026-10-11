from pathlib import Path
import argparse
import re
import sys
import traceback


ROOT = Path(
    __file__
).resolve().parent


sys.path.insert(
    0,
    str(ROOT)
)


from pipeline.full_video_pipeline import (
    FullVideoPipeline,
    FullVideoPipelineError,
)


# ==================================================
# ROBUST PIPELINE
#
# Adds a normalization layer between:
#
# VoicePipeline
#       ↓
# AI Scene Analysis
#
# This prevents empty speech scenes and simple
# non-verbal vocalizations such as:
#
# Ooooo...
# ooooooooo
#
# from being sent to the AI scene validator.
# ==================================================

class RobustFullVideoPipeline(
    FullVideoPipeline
):

    # ==================================================
    # NON-SPEECH DETECTOR
    # ==================================================

    def _looks_like_non_speech(
        self,
        text,
    ):

        text = str(
            text or ""
        ).strip()


        # ----------------------------------------------
        # EMPTY TEXT
        # ----------------------------------------------

        if not text:

            return True


        # ----------------------------------------------
        # KEEP ONLY LETTERS
        #
        # Examples:
        #
        # Ooooo...
        # oooooooooooo
        #
        # become:
        #
        # ooooo
        # oooooooooooo
        # ----------------------------------------------

        letters = "".join(

            character.lower()

            for character
            in text

            if character.isalpha()
        )


        if not letters:

            return True


        # ----------------------------------------------
        # REPEATED SINGLE CHARACTER
        #
        # oooooooo
        # aaaaaaaa
        # mmmmmmmm
        # ----------------------------------------------

        if (
            len(
                letters
            )
            >= 4

            and len(
                set(
                    letters
                )
            )
            == 1
        ):

            return True


        # ----------------------------------------------
        # COMMON SIMPLE VOCALIZATIONS
        # ----------------------------------------------

        simple_patterns = (

            r"h+m+",
            r"h+m+m+",
            r"u+h+",
            r"u+m+",
            r"a+h+",
            r"o+h+",
        )


        for pattern in simple_patterns:

            if re.fullmatch(
                pattern,
                letters,
            ):

                if len(
                    letters
                ) >= 4:

                    return True


        return False


    # ==================================================
    # NORMALIZE VOICE SCENES
    # ==================================================

    def _normalize_voice_scenes(
        self,
        voice_result,
        paths,
    ):

        scenes = voice_result.get(
            "scenes",
            [],
        )


        changed = []


        for scene in scenes:

            scene_type = str(
                getattr(
                    scene,
                    "scene_type",
                    "speech",
                )
            )


            if scene_type == "gap":

                continue


            text = str(
                getattr(
                    scene,
                    "text",
                    "",
                )
                or ""
            ).strip()


            if not self._looks_like_non_speech(
                text
            ):

                continue


            old_text = text


            # ------------------------------------------
            # CONVERT TO GAP
            # ------------------------------------------

            scene.scene_type = "gap"

            scene.text = ""

            scene.subtitle_ids = []


            changed.append({

                "scene_id":
                    scene.id,

                "old_text":
                    old_text,

                "start":
                    scene.start,

                "end":
                    scene.end,
            })


        # ==================================================
        # NOTHING CHANGED
        # ==================================================

        if not changed:

            return voice_result


        print()
        print("=" * 70)
        print("VOICE SCENE NORMALIZATION")
        print("=" * 70)


        for item in changed:

            print()

            print(
                item[
                    "scene_id"
                ],
                "speech -> gap"
            )

            print(
                "  Time:",
                f"{item['start']:.3f}",
                "->",
                f"{item['end']:.3f}",
            )

            print(
                "  Removed text:",
                repr(
                    item[
                        "old_text"
                    ]
                ),
            )


        # ==================================================
        # RECOUNT
        # ==================================================

        speech_count = sum(

            1

            for scene
            in scenes

            if scene.scene_type
            != "gap"
        )


        gap_count = sum(

            1

            for scene
            in scenes

            if scene.scene_type
            == "gap"
        )


        voice_result[
            "scene_count"
        ] = len(
            scenes
        )


        voice_result[
            "speech_scene_count"
        ] = speech_count


        voice_result[
            "gap_scene_count"
        ] = gap_count


        # ==================================================
        # UPDATE SAVED VOICE MANIFEST
        # ==================================================

        voice_manifest_path = (
            paths[
                "voice"
            ]
        )


        if voice_manifest_path.exists():

            manifest = self._load_json(
                voice_manifest_path
            )

        else:

            manifest = {}


        manifest[
            "scene_count"
        ] = len(
            scenes
        )


        manifest[
            "speech_scene_count"
        ] = speech_count


        manifest[
            "gap_scene_count"
        ] = gap_count


        manifest[
            "scenes"
        ] = [

            self._scene_to_dict(
                scene
            )

            for scene
            in scenes
        ]


        self._save_json(

            voice_manifest_path,

            manifest,
        )


        # ==================================================
        # INVALIDATE ONLY DOWNSTREAM MANIFESTS
        #
        # Voice transcription remains cached.
        #
        # Old AI per-scene cache may remain because
        # converted gap scenes will no longer be sent
        # to analyze_one().
        # ==================================================

        self._invalidate_downstream(
            paths
        )


        print()
        print(
            "Speech scenes:",
            speech_count,
        )

        print(
            "Gap scenes:",
            gap_count,
        )

        print(
            "Downstream manifests reset: PASS"
        )

        print(
            "Voice transcription preserved: PASS"
        )


        return voice_result


    # ==================================================
    # OVERRIDE VOICE STAGE
    # ==================================================

    def _run_voice_stage(
        self,
        audio_path,
        paths,
    ):

        result = super()._run_voice_stage(

            audio_path=audio_path,

            paths=paths,
        )


        result = (
            self._normalize_voice_scenes(

                voice_result=result,

                paths=paths,
            )
        )


        return result


# ==================================================
# MAIN
# ==================================================

def main():

    parser = argparse.ArgumentParser(

        description=(
            "AI Video Editor - "
            "Voice to final stock video"
        )
    )


    parser.add_argument(

        "audio",

        help=(
            "Path to input voice/audio file"
        ),
    )


    parser.add_argument(

        "--output",

        default=None,

        help=(
            "Optional final MP4 path"
        ),
    )


    args = parser.parse_args()


    audio_path = Path(
        args.audio
    ).expanduser().resolve()


    output_path = None


    if args.output:

        output_path = Path(
            args.output
        ).expanduser().resolve()


    pipeline = RobustFullVideoPipeline(

        root=ROOT,

        ai_model="gpt-6-luna",

        reasoning_effort="low",

        review_mode="auto",

        visual_top_n=10,

        target_scene_duration=5.0,

        max_scene_duration=8.0,

        duration_tolerance=0.05,
    )


    try:

        result = pipeline.run(

            audio_path=audio_path,

            output_path=output_path,
        )


    except (
        FullVideoPipelineError,
        FileNotFoundError,
        ValueError,
    ) as error:

        print()
        print("=" * 70)
        print("PIPELINE STOPPED")
        print("=" * 70)

        print(
            str(
                error
            )
        )

        print()
        print(
            "If stock progress was already "
            "saved, run the SAME command "
            "again to resume."
        )

        sys.exit(
            1
        )


    except KeyboardInterrupt:

        print()
        print()

        print(
            "Pipeline interrupted by user."
        )

        print(
            "Saved progress can be resumed "
            "with the same command."
        )

        sys.exit(
            130
        )


    except Exception as error:

        print()
        print("=" * 70)
        print("UNEXPECTED ERROR")
        print("=" * 70)

        traceback.print_exc()

        print()

        print(
            "Error:",
            error,
        )

        sys.exit(
            1
        )


    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

    print(
        "Final video:",
        result[
            "output_path"
        ],
    )


if __name__ == "__main__":

    main()