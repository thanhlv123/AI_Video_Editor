from pathlib import Path
import sys


ROOT = Path(
    __file__
).resolve().parent.parent


sys.path.insert(
    0,
    str(ROOT)
)


from scenes.srt_parser import SRTParser
from scenes.scene_builder import SceneBuilder

from ai.providers.kie_provider import (
    KieAIProvider
)

from ai.scene_ai_analyzer import (
    SceneAIAnalyzer
)

from ai.batch_analyzer import (
    BatchSceneAnalyzer
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("BATCH ANALYZER + CACHE TEST")
print("=" * 70)


# ==================================================
# BUILD SCENES
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


scene = scenes[0]


# ==================================================
# PROVIDER
# ==================================================

provider = KieAIProvider(

    model="gpt-6-luna",

    reasoning_effort="low"
)


analyzer = SceneAIAnalyzer(
    provider=provider
)


batch = BatchSceneAnalyzer(

    analyzer=analyzer,

    cache_dir=(
        ROOT
        / "cache"
        / "scene_analysis"
    )
)


# ==================================================
# FIRST RUN
# ==================================================

print()
print("=" * 70)
print("FIRST RUN")
print("=" * 70)


first = batch.analyze_one(
    scene,
    use_cache=True
)


print(
    "Source:",
    first["source"].upper()
)

print(
    "Keyword:",
    first[
        "analysis"
    ].search.primary_keyword
)

print(
    "Cache:",
    first["cache_path"]
)


# ==================================================
# SECOND RUN
# ==================================================

print()
print("=" * 70)
print("SECOND RUN")
print("=" * 70)


second = batch.analyze_one(
    scene,
    use_cache=True
)


print(
    "Source:",
    second["source"].upper()
)

print(
    "Keyword:",
    second[
        "analysis"
    ].search.primary_keyword
)

print(
    "Cache:",
    second["cache_path"]
)


# ==================================================
# VERIFY
# ==================================================

print()
print("=" * 70)


if (
    first["source"] == "api"
    and second["source"] == "cache"
):

    print(
        "CACHE TEST SUCCESS"
    )


elif (
    first["source"] == "cache"
    and second["source"] == "cache"
):

    print(
        "CACHE ALREADY EXISTED - SUCCESS"
    )


else:

    print(
        "UNEXPECTED CACHE RESULT"
    )


print("=" * 70)