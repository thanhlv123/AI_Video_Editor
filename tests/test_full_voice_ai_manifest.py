from pathlib import Path
from copy import deepcopy
from datetime import datetime
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
# IMPORTS
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
print("FULL VOICE -> AI MANIFEST TEST")
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
    / "voice_ai_full_manifest.json"
)


# IMPORTANT:
# Reuse exactly the same cache used by the
# successful 3-scene bridge test.
#
# scene_004, scene_005 and scene_006
# should already be cached.

cache_dir = (
    ROOT
    / "cache"
    / "voice_ai_bridge"
)


# ==================================================
# CHECK FILES
# ==================================================

if not voice_scenes_path.exists():

    raise FileNotFoundError(
        f"Voice scenes not found: "
        f"{voice_scenes_path}"
    )


if not source_srt_path.exists():

    raise FileNotFoundError(
        f"Clean SRT not found: "
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
    "AI cache:",
    cache_dir
)


# ==================================================
# LOAD VOICE SCENES
# ==================================================

print()
print("=" * 70)
print("[1/7] LOAD VOICE SCENES")
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
        "No scenes found in "
        "voice_pipeline_scenes.json"
    )


print(
    "Loaded:",
    len(raw_scenes)
)


# ==================================================
# REBUILD SCENE OBJECTS
# ==================================================

print()
print("=" * 70)
print("[2/7] REBUILD SCENE OBJECTS")
print("=" * 70)


scenes = []


for item in raw_scenes:

    scene = Scene(

        id=str(
            item[
                "id"
            ]
        ),

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


scenes.sort(
    key=lambda scene: (
        scene.start,
        scene.end
    )
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
# CREATE AI ANALYZER
# ==================================================

print()
print("=" * 70)
print("[3/7] CREATE AI ANALYZER")
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

    cache_dir=cache_dir,
)


manifest_builder = (
    AnalysisManifestBuilder()
)


print(
    "Provider:",
    "KieAIProvider:gpt-6-luna"
)

print(
    "Reasoning effort:",
    "low"
)

print(
    "Cache enabled:",
    True
)


# ==================================================
# ANALYZE ALL SPEECH SCENES
# ==================================================

print()
print("=" * 70)
print("[4/7] ANALYZE ALL SPEECH SCENES")
print("=" * 70)


analysis_results = []


for index, scene in enumerate(
    speech_scenes,
    start=1
):

    print()
    print("-" * 70)

    print(
        f"Speech scene "
        f"{index}/{len(speech_scenes)}"
    )

    print(
        "Scene ID:",
        scene.id
    )

    print(
        "Time:",
        f"{scene.start:.3f}",
        "->",
        f"{scene.end:.3f}"
    )

    print(
        "Text:",
        scene.text
    )


    try:

        result = (
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

        print()
        print(
            "Already completed scenes "
            "remain in cache."
        )

        print(
            "Run this test again to resume."
        )

        raise


    analysis_results.append(
        result
    )


    print(
        "Result: SUCCESS"
    )


print()
print(
    "Speech analyses completed:",
    len(analysis_results)
)


# ==================================================
# BUILD SPEECH MANIFEST
# ==================================================

print()
print("=" * 70)
print("[5/7] BUILD SPEECH MANIFEST")
print("=" * 70)


speech_manifest = (
    manifest_builder.build(

        analyses=analysis_results,

        source_srt=str(
            source_srt_path
        ),

        provider=(
            "KieAIProvider:"
            "gpt-6-luna"
        ),
    )
)


speech_entries = {}


for item in speech_manifest.get(
    "scenes",
    []
):

    scene_id = item.get(
        "scene_id"
    )


    if scene_id:

        speech_entries[
            scene_id
        ] = deepcopy(
            item
        )


print(
    "Speech manifest scenes:",
    len(speech_entries)
)


if (
    len(speech_entries)
    != len(speech_scenes)
):

    raise RuntimeError(
        "Speech manifest count mismatch. "
        f"Expected {len(speech_scenes)}, "
        f"got {len(speech_entries)}."
    )


# ==================================================
# FIND GAP REFERENCE SPEECH
# ==================================================

def find_gap_reference(
    gap_scene,
    all_scenes
):

    previous_speech = None
    next_speech = None


    # ----------------------------------------------
    # FIND PREVIOUS SPEECH
    # ----------------------------------------------

    for candidate in all_scenes:

        if (
            candidate.scene_type
            != "speech"
        ):
            continue


        if (
            candidate.end
            <= gap_scene.start
        ):

            previous_speech = (
                candidate
            )


    # ----------------------------------------------
    # FIND NEXT SPEECH
    # ----------------------------------------------

    for candidate in all_scenes:

        if (
            candidate.scene_type
            != "speech"
        ):
            continue


        if (
            candidate.start
            >= gap_scene.end
        ):

            next_speech = (
                candidate
            )

            break


    # ----------------------------------------------
    # PREFERENCE
    #
    # Internal gap:
    # continue previous visual.
    #
    # Leading gap:
    # use first following speech scene.
    # ----------------------------------------------

    if previous_speech is not None:

        return previous_speech


    if next_speech is not None:

        return next_speech


    return None


# ==================================================
# BUILD FULL 30-SCENE MANIFEST
# ==================================================

print()
print("=" * 70)
print("[6/7] ADD GAP SCENES")
print("=" * 70)


full_manifest_scenes = []


for scene in scenes:

    # ==================================================
    # SPEECH
    # ==================================================

    if scene.scene_type == "speech":

        entry = deepcopy(
            speech_entries.get(
                scene.id
            )
        )


        if entry is None:

            raise RuntimeError(
                f"Missing AI result for "
                f"{scene.id}"
            )


        entry[
            "scene_type"
        ] = "speech"


        entry[
            "subtitle_ids"
        ] = list(
            scene.subtitle_ids
        )


        full_manifest_scenes.append(
            entry
        )


        continue


    # ==================================================
    # GAP
    #
    # NO KIE REQUEST.
    # ==================================================

    reference_scene = (
        find_gap_reference(
            gap_scene=scene,
            all_scenes=scenes,
        )
    )


    if reference_scene is None:

        raise RuntimeError(
            f"No reference speech scene "
            f"found for gap {scene.id}"
        )


    reference_entry = (
        speech_entries.get(
            reference_scene.id
        )
    )


    if reference_entry is None:

        raise RuntimeError(
            f"Missing reference AI data "
            f"for {reference_scene.id}"
        )


    entry = deepcopy(
        reference_entry
    )


    # ----------------------------------------------
    # CHANGE ID / TIMING
    # ----------------------------------------------

    entry[
        "scene_id"
    ] = scene.id


    entry[
        "start"
    ] = float(
        scene.start
    )


    entry[
        "end"
    ] = float(
        scene.end
    )


    entry[
        "duration"
    ] = float(
        scene.duration
    )


    entry[
        "dialogue"
    ] = ""


    entry[
        "scene_type"
    ] = "gap"


    entry[
        "subtitle_ids"
    ] = []


    entry[
        "gap_source_scene_id"
    ] = (
        reference_scene.id
    )


    # ----------------------------------------------
    # MARK CONTINUATION CONTEXT
    # ----------------------------------------------

    original_context = (
        entry.get(
            "analysis",
            {}
        )
        .get(
            "context",
            ""
        )
    )


    entry[
        "analysis"
    ][
        "context"
    ] = (
        "Visual continuation during "
        "a non-speech section. "
        + original_context
    ).strip()


    # ----------------------------------------------
    # RESET STOCK STATE
    # ----------------------------------------------

    preferred_type = (
        entry.get(
            "stock",
            {}
        )
        .get(
            "preferred_type",
            "video"
        )
    )


    entry[
        "stock"
    ] = {

        "status":
            "pending",

        "preferred_type":
            preferred_type,

        "searches":
            [],

        "candidates":
            [],

        "selected_media":
            None,
    }


    # ----------------------------------------------
    # RESET TIMELINE STATE
    # ----------------------------------------------

    entry[
        "timeline"
    ] = {

        "clip_id":
            None,

        "media_id":
            None,

        "track_id":
            "video_1",
    }


    full_manifest_scenes.append(
        entry
    )


    print(
        f"{scene.id}: GAP "
        f"{scene.start:.3f}"
        f" -> "
        f"{scene.end:.3f}"
        f" inherits "
        f"{reference_scene.id}"
    )


# ==================================================
# FINAL MANIFEST
# ==================================================

full_manifest = {

    "version":
        speech_manifest.get(
            "version",
            1
        ),

    "created_at": (
        datetime.now()
        .astimezone()
        .isoformat()
    ),

    "source": {

        "srt":
            str(
                source_srt_path
            ),

        "voice_scenes":
            str(
                voice_scenes_path
            ),
    },

    "ai": {

        "provider":
            "KieAIProvider:gpt-6-luna",

        "reasoning_effort":
            "low",

        "speech_scenes_analyzed":
            len(
                speech_scenes
            ),

        "gap_scenes_inherited":
            len(
                gap_scenes
            ),
    },

    "scene_count":
        len(
            full_manifest_scenes
        ),

    "scenes":
        full_manifest_scenes,
}


# ==================================================
# SAVE
# ==================================================

print()
print("=" * 70)
print("[7/7] SAVE + VALIDATE")
print("=" * 70)


manifest_builder.save(
    manifest=full_manifest,
    output_path=output_manifest_path,
)


if not output_manifest_path.exists():

    raise RuntimeError(
        "Full AI manifest was not created."
    )


print(
    "Saved:",
    output_manifest_path
)

print(
    "File size:",
    output_manifest_path.stat().st_size,
    "bytes"
)


# ==================================================
# VALIDATION
# ==================================================

manifest_scenes = (
    full_manifest.get(
        "scenes",
        []
    )
)


if (
    len(manifest_scenes)
    != len(scenes)
):

    raise RuntimeError(
        "Full scene count mismatch."
    )


# ----------------------------------------------
# EXACT ORDER CHECK
# ----------------------------------------------

expected_ids = [
    scene.id
    for scene in scenes
]


manifest_ids = [
    scene.get(
        "scene_id"
    )
    for scene in manifest_scenes
]


if (
    expected_ids
    != manifest_ids
):

    raise RuntimeError(
        "Manifest scene order "
        "does not match voice timeline."
    )


# ----------------------------------------------
# TYPE COUNTS
# ----------------------------------------------

manifest_speech_count = sum(

    1

    for item in manifest_scenes

    if (
        item.get(
            "scene_type"
        )
        == "speech"
    )
)


manifest_gap_count = sum(

    1

    for item in manifest_scenes

    if (
        item.get(
            "scene_type"
        )
        == "gap"
    )
)


if (
    manifest_speech_count
    != len(
        speech_scenes
    )
):

    raise RuntimeError(
        "Speech scene count mismatch."
    )


if (
    manifest_gap_count
    != len(
        gap_scenes
    )
):

    raise RuntimeError(
        "Gap scene count mismatch."
    )


# ----------------------------------------------
# SEARCH CHECK
# ----------------------------------------------

for item in manifest_scenes:

    search = item.get(
        "search",
        {}
    )


    if not search.get(
        "primary_keyword"
    ):

        raise RuntimeError(
            f"{item.get('scene_id')}: "
            "missing primary_keyword."
        )


# ----------------------------------------------
# GAP CHECK
# ----------------------------------------------

for item in manifest_scenes:

    if (
        item.get(
            "scene_type"
        )
        != "gap"
    ):

        continue


    if not item.get(
        "gap_source_scene_id"
    ):

        raise RuntimeError(
            f"{item.get('scene_id')}: "
            "gap source missing."
        )


# ----------------------------------------------
# TIMELINE CHECK
# ----------------------------------------------

previous_end = 0.0


for item in manifest_scenes:

    start = float(
        item[
            "start"
        ]
    )

    end = float(
        item[
            "end"
        ]
    )


    if abs(
        start
        - previous_end
    ) > 0.01:

        raise RuntimeError(
            "Timeline discontinuity before "
            f"{item['scene_id']}: "
            f"{previous_end:.3f}"
            f" -> "
            f"{start:.3f}"
        )


    previous_end = end


audio_duration = float(
    voice_data[
        "audio_duration"
    ]
)


if abs(
    previous_end
    - audio_duration
) > 0.01:

    raise RuntimeError(
        "Manifest does not reach "
        "audio duration."
    )


# ==================================================
# SUMMARY
# ==================================================

print()
print("=" * 70)
print("VALIDATION RESULT")
print("=" * 70)


print(
    "Total scene count: PASS"
)

print(
    "Scene order: PASS"
)

print(
    "Speech scenes: PASS"
)

print(
    "Gap scenes: PASS"
)

print(
    "Search keywords: PASS"
)

print(
    "Gap inheritance: PASS"
)

print(
    "Continuous timeline: PASS"
)


print()
print("=" * 70)
print("FULL VOICE -> AI MANIFEST SUCCESS")
print("=" * 70)


print(
    "Total scenes:",
    len(
        manifest_scenes
    )
)

print(
    "Speech scenes:",
    manifest_speech_count
)

print(
    "Gap scenes:",
    manifest_gap_count
)

print(
    "Timeline:",
    f"{manifest_scenes[0]['start']:.3f}",
    "->",
    f"{manifest_scenes[-1]['end']:.3f}"
)

print(
    "Manifest:",
    output_manifest_path
)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)