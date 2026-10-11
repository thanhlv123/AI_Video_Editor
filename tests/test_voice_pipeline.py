from pathlib import Path
import sys
import json


ROOT = Path(
    __file__
).resolve().parent.parent


sys.path.insert(
    0,
    str(ROOT)
)


from pipeline.voice_pipeline import (
    VoicePipeline,
    VoicePipelineError,
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("VOICE PIPELINE TEST")
print("=" * 70)


# ==================================================
# PATHS
# ==================================================

audio_path = (
    ROOT
    / "media"
    / "test_voice.mp3"
)


srt_path = (
    ROOT
    / "subtitles"
    / "test_voice_clean.srt"
)


scenes_path = (
    ROOT
    / "projects"
    / "voice_pipeline_scenes.json"
)


# ==================================================
# CHECK INPUT
# ==================================================

if not audio_path.exists():

    raise FileNotFoundError(
        f"Audio not found: "
        f"{audio_path}"
    )


print()
print(
    "Audio:",
    audio_path
)

print(
    "Clean SRT:",
    srt_path
)

print(
    "Scenes JSON:",
    scenes_path
)


# ==================================================
# CREATE PIPELINE
# ==================================================

pipeline = VoicePipeline(

    model_size="small",

    device="cpu",

    compute_type="int8",

    language=None,

    beam_size=5,

    vad_filter=False,

    target_scene_duration=5.0,

    max_scene_duration=8.0,

    minimum_segment_duration=0.10,

    gap_threshold=2.0,
)


# ==================================================
# RUN
# ==================================================

print()
print("=" * 70)
print("RUNNING VOICE PIPELINE")
print("=" * 70)


try:

    result = pipeline.run(

        audio_path=audio_path,

        srt_output_path=srt_path,
    )


except VoicePipelineError as error:

    print()
    print("=" * 70)
    print("VOICE PIPELINE FAILED")
    print("=" * 70)

    print(
        error
    )

    raise SystemExit(1)


# ==================================================
# RESULT DATA
# ==================================================

scenes = result[
    "scenes"
]


cleaning = result[
    "cleaning"
]


gaps = result[
    "gaps"
]


# ==================================================
# SUMMARY
# ==================================================

print()
print("=" * 70)
print("VOICE PIPELINE RESULT")
print("=" * 70)


print(
    "Success:",
    result[
        "success"
    ]
)

print(
    "Language:",
    result[
        "language"
    ]
)

print(
    "Language probability:",
    result[
        "language_probability"
    ]
)

print(
    "Audio duration:",
    result[
        "audio_duration"
    ]
)

print(
    "Raw segments:",
    cleaning[
        "raw_segment_count"
    ]
)

print(
    "Clean segments:",
    cleaning[
        "clean_segment_count"
    ]
)

print(
    "Removed segments:",
    cleaning[
        "removed_segment_count"
    ]
)

print(
    "Clamped segments:",
    cleaning[
        "clamped_segment_count"
    ]
)

print(
    "Gaps:",
    len(
        gaps
    )
)

print(
    "Scenes:",
    len(
        scenes
    )
)

print(
    "SRT:",
    result[
        "srt_path"
    ]
)


# ==================================================
# DISPLAY GAPS
# ==================================================

print()
print("=" * 70)
print("TIMELINE GAPS")
print("=" * 70)


if not gaps:

    print(
        "No large gaps detected."
    )


for gap in gaps:

    print()

    print(
        "Type:",
        gap[
            "type"
        ]
    )

    print(
        "Start:",
        gap[
            "start"
        ]
    )

    print(
        "End:",
        gap[
            "end"
        ]
    )

    print(
        "Duration:",
        gap[
            "duration"
        ]
    )


# ==================================================
# DISPLAY SCENES
# ==================================================

print()
print("=" * 70)
print("GENERATED SCENES")
print("=" * 70)


for scene in scenes:

    print()

    print(
        scene.id
    )

    print(
        "  Start:",
        scene.start
    )

    print(
        "  End:",
        scene.end
    )

    print(
        "  Duration:",
        scene.duration
    )

    print(
        "  Subtitle IDs:",
        scene.subtitle_ids
    )

    print(
        "  Text:",
        scene.text
    )


# ==================================================
# VALIDATION
# ==================================================

print()
print("=" * 70)
print("VALIDATING RESULT")
print("=" * 70)


if not srt_path.exists():

    raise RuntimeError(
        "Clean SRT file was not created."
    )


if not scenes:

    raise RuntimeError(
        "No scenes were generated."
    )


audio_duration = float(
    result[
        "audio_duration"
    ]
)


# --------------------------------------------------
# CHECK EVERY SCENE
# --------------------------------------------------

for scene in scenes:

    if scene.start < 0:

        raise RuntimeError(
            f"{scene.id}: "
            "negative start time."
        )


    if scene.end <= scene.start:

        raise RuntimeError(
            f"{scene.id}: "
            "invalid scene timing."
        )


    if scene.duration <= 0:

        raise RuntimeError(
            f"{scene.id}: "
            "invalid duration."
        )


    if scene.end > (
        audio_duration + 0.01
    ):

        raise RuntimeError(
            f"{scene.id}: "
            "scene extends past "
            "audio duration."
        )


print(
    "Scene timing: VALID"
)


# ==================================================
# CHECK ORDER
# ==================================================

previous_start = -1.0


for scene in scenes:

    if scene.start < previous_start:

        raise RuntimeError(
            "Scenes are not "
            "chronologically ordered."
        )


    previous_start = (
        scene.start
    )


print(
    "Scene order: VALID"
)


# ==================================================
# SAVE SCENES JSON
# ==================================================

scenes_path.parent.mkdir(
    parents=True,
    exist_ok=True
)


data = {

    "audio": str(
        audio_path
    ),

    "audio_duration": (
        result[
            "audio_duration"
        ]
    ),

    "language": (
        result[
            "language"
        ]
    ),

    "srt": (
        result[
            "srt_path"
        ]
    ),

    "cleaning": (
        cleaning
    ),

    "gaps": (
        gaps
    ),

    "scenes": [
        scene.to_dict()
        for scene in scenes
    ],
}


with open(
    scenes_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        data,
        file,
        indent=4,
        ensure_ascii=False
    )


print(
    "Scenes JSON saved:",
    scenes_path
)


# ==================================================
# FINAL
# ==================================================

print()
print("=" * 70)
print("VOICE PIPELINE SUCCESS")
print("=" * 70)


print(
    "Audio duration:",
    audio_duration
)

print(
    "Clean SRT:",
    srt_path
)

print(
    "Scenes:",
    len(
        scenes
    )
)

print(
    "First scene:",
    f"{scenes[0].start:.3f}"
    " -> "
    f"{scenes[0].end:.3f}"
)

print(
    "Last scene:",
    f"{scenes[-1].start:.3f}"
    " -> "
    f"{scenes[-1].end:.3f}"
)

print(
    "JSON:",
    scenes_path
)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)