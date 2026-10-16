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

from ai.providers.kie_provider import (
    KieAIProvider
)

from ai.scene_ai_analyzer import (
    SceneAIAnalyzer
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("KIE REAL SCENE ANALYZER TEST")
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
# BUILD SCENES
# ==================================================

builder = SceneBuilder(
    target_duration=5.0,
    max_duration=8.0
)


scenes = builder.build(
    subtitles
)


if not scenes:

    raise RuntimeError(
        "No scenes created."
    )


# ==================================================
# KIE PROVIDER
# ==================================================

provider = KieAIProvider(

    model="gpt-6-luna",

    reasoning_effort="low"
)


analyzer = SceneAIAnalyzer(
    provider=provider
)


# ==================================================
# ONLY TEST SCENE 001
# ==================================================

scene = scenes[0]


print()
print("Scene:")
print(scene.id)

print()
print("Time:")
print(
    f"{scene.start:.2f}"
    f" -> "
    f"{scene.end:.2f}"
)

print()
print("Narration:")
print(scene.text)

print()
print(
    "Sending scene to Kie.ai..."
)


result = analyzer.analyze(
    scene
)


# ==================================================
# RESULT
# ==================================================

print()
print("=" * 70)
print("KIE SCENE ANALYSIS")
print("=" * 70)


print(
    json.dumps(
        result.to_dict(),
        indent=4,
        ensure_ascii=False
    )
)


# ==================================================
# IMPORTANT FIELDS
# ==================================================

print()
print("=" * 70)
print("STOCK SEARCH DATA")
print("=" * 70)


print()
print(
    "Context:",
    result.analysis.context
)

print(
    "Subject:",
    result.analysis.subject
)

print(
    "Action:",
    result.analysis.action
)

print(
    "Location:",
    result.analysis.location
)

print(
    "Mood:",
    result.analysis.mood
)

print(
    "Shot:",
    result.analysis.shot
)

print(
    "Motion:",
    result.analysis.motion
)


print()
print(
    "Primary keyword:",
    result.search.primary_keyword
)


print()
print("Keywords:")


for keyword in (
    result.search.keywords
):

    print(
        "  -",
        keyword
    )


print()
print("Avoid:")


for item in (
    result.search.avoid
):

    print(
        "  -",
        item
    )


print()
print(
    "Preferred media:",
    result.media.preferred_type
)


# ==================================================
# SAVE RESULT
# ==================================================

output_path = (
    ROOT
    / "projects"
    / "kie_scene_001.json"
)


with open(
    output_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        result.to_dict(),
        file,
        indent=4,
        ensure_ascii=False
    )


print()
print("=" * 70)
print("KIE SCENE TEST SUCCESS")
print("=" * 70)

print(
    "Saved:",
    output_path
)