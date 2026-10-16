from pathlib import Path
import json
import sys


# ==================================================
# PROJECT ROOT
# ==================================================

ROOT = Path(
    __file__
).resolve().parent.parent


sys.path.insert(
    0,
    str(ROOT)
)


# ==================================================
# IMPORT PROJECT MODULES
# ==================================================

from scenes.scene_builder import Scene

from ai.providers.kie_provider import (
    KieAIProvider,
)

from ai.scene_ai_analyzer import (
    SceneAIAnalyzer,
)

from ai.batch_analyzer import (
    BatchSceneAnalyzer,
)

from ai.manifest_builder import (
    AnalysisManifestBuilder,
)


# ==================================================
# HEADER
# ==================================================

print("=" * 70)
print("AI VIDEO EDITOR")
print("VOICE -> AI ANALYZER BRIDGE TEST")
print("=" * 70)


# ==================================================
# PATHS
# ==================================================

voice_scenes_path = (
    ROOT
    / "projects"
    / "voice_pipeline_scenes.json"
)


source_srt_path = (
    ROOT
    / "subtitles"
    / "test_voice_clean.srt"
)


output_manifest_path = (
    ROOT
    / "projects"
    / "voice_ai_bridge_test.json"
)


cache_dir = (
    ROOT
    / "cache"
    / "voice_ai_bridge"
)


# ==================================================
# VALIDATE FILES
# ==================================================

if not voice_scenes_path.exists():

    raise FileNotFoundError(
        "Voice scenes JSON not found: "
        f"{voice_scenes_path}"
    )


if not source_srt_path.exists():

    raise FileNotFoundError(
        "Clean SRT not found: "
        f"{source_srt_path}"
    )


print()
print(
    "Voice scenes:",
    voice_scenes_path
)

print(
    "Source SRT:",
    source_srt_path
)

print(
    "Output manifest:",
    output_manifest_path
)

print(
    "Cache:",
    cache_dir
)


# ==================================================
# LOAD VOICE PIPELINE JSON
# ==================================================

print()
print("=" * 70)
print("[1/6] LOAD VOICE SCENES")
print("=" * 70)


with open(
    voice_scenes_path,
    "r",
    encoding="utf-8"
) as file:

    voice_data = json.load(
        file
    )


raw_scenes = voice_data.get(
    "scenes",
    []
)


if not raw_scenes:

    raise RuntimeError(
        "voice_pipeline_scenes.json "
        "contains no scenes."
    )


print(
    "Scenes loaded:",
    len(raw_scenes)
)


# ==================================================
# REBUILD SCENE OBJECTS
# ==================================================

print()
print("=" * 70)
print("[2/6] REBUILD SCENE OBJECTS")
print("=" * 70)


scenes = []


for item in raw_scenes:

    scene = Scene(

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
                ""
            )
            or ""
        ),

        subtitle_ids=list(
            item.get(
                "subtitle_ids",
                []
            )
        ),

        scene_type=str(
            item.get(
                "scene_type",
                "speech"
            )
        ),
    )


    scenes.append(
        scene
    )


speech_scenes = [
    scene
    for scene in scenes
    if (
        scene.scene_type
        == "speech"
        and scene.text.strip()
    )
]


gap_scenes = [
    scene
    for scene in scenes
    if scene.scene_type == "gap"
]


print(
    "Total scenes:",
    len(scenes)
)

print(
    "Speech scenes:",
    len(speech_scenes)
)

print(
    "Gap scenes:",
    len(gap_scenes)
)


if not speech_scenes:

    raise RuntimeError(
        "No speech scenes found."
    )


# ==================================================
# SELECT ONLY 3 SPEECH SCENES
#
# IMPORTANT:
# We deliberately test only 3 scenes first
# so we do not waste KIE API credits.
# ==================================================

test_scenes = (
    speech_scenes[:3]
)


print()
print(
    "AI test scenes:",
    len(test_scenes)
)


for scene in test_scenes:

    print()

    print(
        scene.id
    )

    print(
        "  Time:",
        f"{scene.start:.3f}",
        "->",
        f"{scene.end:.3f}"
    )

    print(
        "  Duration:",
        f"{scene.duration:.3f}"
    )

    print(
        "  Text:",
        scene.text
    )


# ==================================================
# CREATE KIE PROVIDER
# ==================================================

print()
print("=" * 70)
print("[3/6] CREATE AI ANALYZER")
print("=" * 70)


provider = KieAIProvider(

    model="gpt-6-luna",

    reasoning_effort="low",
)


analyzer = SceneAIAnalyzer(
    provider=provider
)


batch_analyzer = BatchSceneAnalyzer(

    analyzer=analyzer,

    # Separate cache from old 3-scene tests.
    # This prevents old scene IDs from contaminating
    # the new voice pipeline test.
    cache_dir=cache_dir,
)


print(
    "Provider:",
    "KieAIProvider:gpt-6-luna"
)

print(
    "Reasoning effort:",
    "low"
)


# ==================================================
# ANALYZE 3 SPEECH SCENES
# ==================================================

print()
print("=" * 70)
print("[4/6] ANALYZE SPEECH SCENES")
print("=" * 70)


analyses = []


for index, scene in enumerate(
    test_scenes,
    start=1
):

    print()
    print("-" * 70)

    print(
        f"Analyzing "
        f"{index}/{len(test_scenes)}"
    )

    print(
        "Scene:",
        scene.id
    )

    print(
        "Text:",
        scene.text
    )


    try:

        analysis = (
            batch_analyzer.analyze_one(
                scene=scene,
                use_cache=True,
            )
        )

    except Exception as error:

        print()
        print("=" * 70)
        print("AI ANALYSIS FAILED")
        print("=" * 70)

        print(
            "Scene:",
            scene.id
        )

        print(
            "Error:",
            error
        )

        raise


    analyses.append(
        analysis
    )


    print(
        "Analysis:",
        "SUCCESS"
    )


# ==================================================
# BUILD MANIFEST
# ==================================================

print()
print("=" * 70)
print("[5/6] BUILD AI MANIFEST")
print("=" * 70)


manifest_builder = (
    AnalysisManifestBuilder()
)


manifest = (
    manifest_builder.build(

        analyses=analyses,

        source_srt=str(
            source_srt_path
        ),

        provider=(
            "KieAIProvider:"
            "gpt-6-luna"
        ),
    )
)


print(
    "Manifest scenes:",
    manifest.get(
        "scene_count"
    )
)


# ==================================================
# SAVE MANIFEST
# ==================================================

print()
print("=" * 70)
print("[6/6] SAVE AI MANIFEST")
print("=" * 70)


output_manifest_path.parent.mkdir(
    parents=True,
    exist_ok=True
)


manifest_builder.save(
    manifest=manifest,
    output_path=output_manifest_path,
)


if not output_manifest_path.exists():

    raise RuntimeError(
        "AI manifest was not created."
    )


print(
    "Saved:",
    output_manifest_path
)

print(
    "Size:",
    output_manifest_path.stat().st_size,
    "bytes"
)


# ==================================================
# DISPLAY ANALYSIS RESULTS
# ==================================================

print()
print("=" * 70)
print("AI ANALYSIS RESULTS")
print("=" * 70)


manifest_scenes = (
    manifest.get(
        "scenes",
        []
    )
)


for scene in manifest_scenes:

    print()

    print(
        scene.get(
            "scene_id"
        )
    )

    print(
        "Dialogue:",
        scene.get(
            "dialogue"
        )
    )


    analysis_data = (
        scene.get(
            "analysis",
            {}
        )
    )


    search_data = (
        scene.get(
            "search",
            {}
        )
    )


    print(
        "Context:",
        analysis_data.get(
            "context"
        )
    )

    print(
        "Subject:",
        analysis_data.get(
            "subject"
        )
    )

    print(
        "Action:",
        analysis_data.get(
            "action"
        )
    )

    print(
        "Location:",
        analysis_data.get(
            "location"
        )
    )

    print(
        "Mood:",
        analysis_data.get(
            "mood"
        )
    )

    print(
        "Shot:",
        analysis_data.get(
            "shot"
        )
    )

    print(
        "Motion:",
        analysis_data.get(
            "motion"
        )
    )

    print(
        "Primary keyword:",
        search_data.get(
            "primary_keyword"
        )
    )

    print(
        "Keywords:",
        search_data.get(
            "keywords"
        )
    )

    print(
        "Avoid:",
        search_data.get(
            "avoid"
        )
    )


# ==================================================
# VALIDATION
# ==================================================

print()
print("=" * 70)
print("VALIDATING AI BRIDGE")
print("=" * 70)


if (
    len(analyses)
    != 3
):

    raise RuntimeError(
        "Expected exactly "
        "3 AI analyses."
    )


if (
    len(manifest_scenes)
    != 3
):

    raise RuntimeError(
        "Expected exactly "
        "3 manifest scenes."
    )


for scene in manifest_scenes:

    if not scene.get(
        "scene_id"
    ):

        raise RuntimeError(
            "Manifest scene "
            "missing scene_id."
        )


    analysis_data = (
        scene.get(
            "analysis",
            {}
        )
    )


    search_data = (
        scene.get(
            "search",
            {}
        )
    )


    required_analysis = [

        "context",

        "subject",

        "action",

        "location",

        "mood",

        "shot",

        "motion",
    ]


    for field in required_analysis:

        if field not in analysis_data:

            raise RuntimeError(
                f"{scene.get('scene_id')}: "
                f"missing analysis field "
                f"{field}"
            )


    if not search_data.get(
        "primary_keyword"
    ):

        raise RuntimeError(
            f"{scene.get('scene_id')}: "
            "missing primary_keyword"
        )


print(
    "Scene count: PASS"
)

print(
    "AI analysis fields: PASS"
)

print(
    "Search keywords: PASS"
)

print(
    "Manifest creation: PASS"
)


# ==================================================
# SUCCESS
# ==================================================

print()
print("=" * 70)
print("VOICE -> AI BRIDGE SUCCESS")
print("=" * 70)


print(
    "Voice scenes available:",
    len(scenes)
)

print(
    "Speech scenes available:",
    len(speech_scenes)
)

print(
    "Gap scenes available:",
    len(gap_scenes)
)

print(
    "AI scenes tested:",
    len(analyses)
)

print(
    "Manifest:",
    output_manifest_path
)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)