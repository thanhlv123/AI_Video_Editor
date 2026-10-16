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

from ai.providers.openai_provider import (
    OpenAIProvider
)

from ai.scene_ai_analyzer import (
    SceneAIAnalyzer
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("OPENAI REAL PROVIDER TEST")
print("=" * 70)


# ==================================================
# SRT -> SCENES
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


builder = SceneBuilder(
    target_duration=5.0,
    max_duration=8.0
)


scenes = builder.build(
    subtitles
)


if not scenes:

    raise RuntimeError(
        "No scenes were created."
    )


# ==================================================
# OPENAI
# ==================================================

provider = OpenAIProvider()

analyzer = SceneAIAnalyzer(
    provider=provider
)


# ==================================================
# ONLY TEST SCENE 1
# ==================================================

scene = scenes[0]


print()
print("Sending scene:")
print(scene.id)

print()
print("Narration:")
print(scene.text)

print()
print("Calling OpenAI...")


result = analyzer.analyze(
    scene
)


# ==================================================
# RESULT
# ==================================================

print()
print("=" * 70)
print("OPENAI RESULT")
print("=" * 70)

print(
    json.dumps(
        result.to_dict(),
        indent=4,
        ensure_ascii=False
    )
)


print()
print("=" * 70)
print("IMPORTANT SEARCH DATA")
print("=" * 70)

print(
    "Context:",
    result.analysis.context
)

print(
    "Primary keyword:",
    result.search.primary_keyword
)

print(
    "Keywords:"
)

for keyword in (
    result.search.keywords
):

    print(
        " -",
        keyword
    )


print()
print(
    "Preferred media:",
    result.media.preferred_type
)

print()
print(
    "Shot:",
    result.analysis.shot
)

print(
    "Motion:",
    result.analysis.motion
)


print()
print("=" * 70)
print("OPENAI PROVIDER TEST COMPLETE")
print("=" * 70)