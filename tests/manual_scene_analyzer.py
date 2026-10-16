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


from scenes.srt_parser import (
    SRTParser
)

from scenes.scene_builder import (
    SceneBuilder
)

from ai.mock_analyzer import (
    MockSceneAnalyzer
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("SCENE ANALYZER TEST")
print("=" * 70)


# ==================================================
# SRT
# ==================================================

srt_path = (
    ROOT
    / "subtitles"
    / "test_voice.srt"
)


parser = SRTParser()

subtitles = parser.parse(
    srt_path
)


# ==================================================
# SCENES
# ==================================================

builder = SceneBuilder(
    target_duration=5.0,
    max_duration=8.0
)


scenes = builder.build(
    subtitles
)


print()
print(
    "Scenes:",
    len(scenes)
)


# ==================================================
# ANALYZER
# ==================================================

analyzer = MockSceneAnalyzer()


analyzed_scenes = []


for scene in scenes:

    result = analyzer.analyze(
        scene
    )

    analyzed_scenes.append(
        result
    )


# ==================================================
# DISPLAY
# ==================================================

print()
print("=" * 70)
print("ANALYZED SCENES")
print("=" * 70)


for scene in analyzed_scenes:

    print()

    print(
        scene.scene_id.upper()
    )

    print(
        f"Time: "
        f"{scene.start:.2f}"
        f" -> "
        f"{scene.end:.2f}"
    )

    print(
        "Dialogue:",
        scene.dialogue
    )

    print(
        "Context:",
        scene.analysis.context
    )

    print(
        "Subject:",
        scene.analysis.subject
    )

    print(
        "Action:",
        scene.analysis.action
    )

    print(
        "Location:",
        scene.analysis.location
    )

    print(
        "Mood:",
        scene.analysis.mood
    )

    print(
        "Shot:",
        scene.analysis.shot
    )

    print(
        "Motion:",
        scene.analysis.motion
    )

    print(
        "Media:",
        scene.media.preferred_type
    )

    print(
        "Primary keyword:",
        scene.search.primary_keyword
    )

    print(
        "Keywords:"
    )

    for keyword in (
        scene.search.keywords
    ):

        print(
            "   -",
            keyword
        )


# ==================================================
# SAVE JSON
# ==================================================

output_path = (
    ROOT
    / "projects"
    / "analyzed_scenes.json"
)


output_data = {

    "source_srt": str(
        srt_path
    ),

    "scene_count": len(
        analyzed_scenes
    ),

    "scenes": [

        scene.to_dict()

        for scene in analyzed_scenes
    ]
}


with open(
    output_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        output_data,
        file,
        indent=4,
        ensure_ascii=False
    )


print()
print("=" * 70)
print("ANALYSIS JSON SAVED")
print("=" * 70)

print(
    output_path
)