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

from ai.providers.mock import (
    MockAIProvider
)

from ai.scene_ai_analyzer import (
    SceneAIAnalyzer
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("AI PROVIDER ARCHITECTURE TEST")
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


# ==================================================
# PROVIDER
# ==================================================

provider = MockAIProvider()


analyzer = SceneAIAnalyzer(
    provider=provider
)


# ==================================================
# ANALYZE
# ==================================================

results = []


for scene in scenes:

    print()
    print(
        "Analyzing:",
        scene.id
    )

    result = analyzer.analyze(
        scene
    )

    results.append(
        result
    )

    print(
        "  Context:",
        result.analysis.context
    )

    print(
        "  Keyword:",
        result.search.primary_keyword
    )

    print(
        "  Media:",
        result.media.preferred_type
    )


# ==================================================
# SAVE
# ==================================================

output_path = (
    ROOT
    / "projects"
    / "provider_analysis_test.json"
)


data = {

    "provider": (
        provider.__class__.__name__
    ),

    "scene_count": len(
        results
    ),

    "scenes": [

        scene.to_dict()

        for scene in results
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
print("PROVIDER TEST COMPLETE")
print("=" * 70)

print(
    "Provider:",
    provider.__class__.__name__
)

print(
    "Scenes:",
    len(results)
)

print(
    "Saved:",
    output_path
)