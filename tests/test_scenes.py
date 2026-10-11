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


from scenes.srt_parser import SRTParser
from scenes.scene_builder import SceneBuilder


print("=" * 70)
print("AI VIDEO EDITOR")
print("SRT -> SCENE ENGINE TEST")
print("=" * 70)


srt_path = (
    ROOT
    / "subtitles"
    / "test_voice.srt"
)


# ==================================================
# PARSE SRT
# ==================================================

parser = SRTParser()


subtitles = parser.parse(
    srt_path
)


print()
print("SUBTITLES")
print("=" * 70)


for subtitle in subtitles:

    print(
        f"{subtitle.index:02d}"
        f" | {subtitle.start:05.2f}"
        f" -> {subtitle.end:05.2f}"
        f" | {subtitle.text}"
    )


# ==================================================
# BUILD SCENES
# ==================================================

builder = SceneBuilder(
    target_duration=5.0,
    max_duration=8.0
)


scenes = builder.build(
    subtitles
)


print()
print("=" * 70)
print("SCENES")
print("=" * 70)


for scene in scenes:

    print()

    print(
        scene.id
    )

    print(
        f"Time: "
        f"{scene.start:.2f}"
        f" -> "
        f"{scene.end:.2f}"
    )

    print(
        f"Duration: "
        f"{scene.duration:.2f}"
    )

    print(
        "Text:",
        scene.text
    )

    print(
        "Subtitles:",
        scene.subtitle_ids
    )


# ==================================================
# SAVE SCENE JSON
# ==================================================

output_path = (
    ROOT
    / "projects"
    / "test_scenes.json"
)


data = {
    "source_srt": str(
        srt_path
    ),

    "scene_count": len(
        scenes
    ),

    "scenes": [
        scene.to_dict()
        for scene in scenes
    ]
}


with open(
    output_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        data,
        file,
        indent=4,
        ensure_ascii=False
    )


print()
print("=" * 70)
print("SCENE JSON SAVED")
print("=" * 70)

print(
    output_path
)