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

from ai.batch_analyzer import (
    BatchSceneAnalyzer
)

from ai.manifest_builder import (
    AnalysisManifestBuilder
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("FULL SCENE ANALYSIS MANIFEST TEST")
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


print()
print(
    "Scenes found:",
    len(scenes)
)


# ==================================================
# KIE PROVIDER
# ==================================================

provider = KieAIProvider(

    model="gpt-6-luna",

    reasoning_effort="low"
)


scene_analyzer = SceneAIAnalyzer(
    provider=provider
)


# ==================================================
# BATCH + CACHE
# ==================================================

batch = BatchSceneAnalyzer(

    analyzer=scene_analyzer,

    cache_dir=(
        ROOT
        / "cache"
        / "scene_analysis"
    )
)


print()
print("=" * 70)
print("ANALYZING SCENES")
print("=" * 70)


analyses, stats = (
    batch.analyze_all(
        scenes,
        use_cache=True
    )
)


# ==================================================
# STATISTICS
# ==================================================

print()
print("=" * 70)
print("ANALYSIS STATISTICS")
print("=" * 70)


print(
    "Total:",
    stats["total"]
)

print(
    "API calls:",
    stats["api_calls"]
)

print(
    "Cache hits:",
    stats["cache_hits"]
)

print(
    "Failed:",
    stats["failed"]
)


# ==================================================
# BUILD MANIFEST
# ==================================================

manifest_builder = (
    AnalysisManifestBuilder()
)


provider_name = (
    provider.__class__.__name__
    + ":"
    + provider.model
)


manifest = (
    manifest_builder.build(

        analyses=analyses,

        source_srt=srt_path,

        provider=provider_name
    )
)


# ==================================================
# SAVE
# ==================================================

output_path = (
    ROOT
    / "projects"
    / "analysis_manifest.json"
)


manifest_builder.save(
    manifest,
    output_path
)


# ==================================================
# DISPLAY
# ==================================================

print()
print("=" * 70)
print("VISUAL PLAN")
print("=" * 70)


for scene in manifest["scenes"]:

    print()

    print(
        scene["scene_id"].upper()
    )

    print(
        "Time:",
        f'{scene["start"]:.2f}',
        "->",
        f'{scene["end"]:.2f}'
    )

    print(
        "Context:",
        scene[
            "analysis"
        ][
            "context"
        ]
    )

    print(
        "Primary keyword:",
        scene[
            "search"
        ][
            "primary_keyword"
        ]
    )

    print(
        "Stock status:",
        scene[
            "stock"
        ][
            "status"
        ]
    )


print()
print("=" * 70)
print("ANALYSIS MANIFEST SAVED")
print("=" * 70)

print(
    output_path
)