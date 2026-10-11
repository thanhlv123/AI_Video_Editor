from pathlib import Path
import inspect
import json
import sys


# ==================================================
# PROJECT ROOT
# ==================================================

ROOT = Path(
    r"D:\YouTubeTools\AI_Video_Editor"
)

if str(ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(ROOT),
    )


# ==================================================
# IMPORT CURRENT PRODUCTION CODE
# ==================================================

from scenes.scene_builder import (
    SceneBuilder,
    Scene,
)

from pipeline.full_video_pipeline import (
    FullVideoPipeline,
)

from ai.scene_ai_analyzer import (
    SceneAIAnalyzer,
)

from ai.providers.kie_provider import (
    KieAIProvider,
)


print("=" * 80)
print("58C SEMANTIC CONTEXT HOOK INSPECTOR")
print("=" * 80)


# ==================================================
# HELPER
# ==================================================

def show_source(
    title,
    obj,
):

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    try:

        source = inspect.getsource(
            obj
        )

    except Exception as error:

        print(
            "SOURCE READ FAILED:",
            error,
        )

        return

    print(
        source
    )


# ==================================================
# 1. SCENE DATA STRUCTURE
# ==================================================

show_source(
    "SCENE CLASS",
    Scene,
)


# ==================================================
# 2. SCENE BUILDER
# ==================================================

show_source(
    "SCENE BUILDER CLASS",
    SceneBuilder,
)


# ==================================================
# 3. AI STAGE
# ==================================================

show_source(
    "FULL VIDEO PIPELINE _run_ai_stage",
    FullVideoPipeline._run_ai_stage,
)


# ==================================================
# 4. SCENE AI ANALYZER
# ==================================================

show_source(
    "SCENE AI ANALYZER analyze",
    SceneAIAnalyzer.analyze,
)


# ==================================================
# 5. KIE ANALYZE SCENE
# ==================================================

show_source(
    "KIE PROVIDER analyze_scene",
    KieAIProvider.analyze_scene,
)


# ==================================================
# MOROCCO MANIFEST
# ==================================================

MOROCCO_MANIFEST = (
    ROOT
    / "projects"
    / "runs"
    / "morocco_88fd372c"
    / "ai_manifest.json"
)


print()
print("=" * 80)
print("MOROCCO SEMANTIC BOUNDARY ANALYSIS")
print("=" * 80)

print(
    "Manifest:",
    MOROCCO_MANIFEST,
)


if not MOROCCO_MANIFEST.exists():

    print()
    print(
        "Morocco ai_manifest.json not found."
    )

    print(
        "Source inspection above is still valid."
    )

    raise SystemExit(
        0
    )


with open(
    MOROCCO_MANIFEST,
    "r",
    encoding="utf-8",
) as file:

    manifest = json.load(
        file
    )


scenes = manifest.get(
    "scenes",
    [],
)


speech_scenes = [

    scene

    for scene in scenes

    if scene.get(
        "scene_type",
        "speech",
    ) != "gap"
]


print(
    "Speech scenes:",
    len(
        speech_scenes
    ),
)


# ==================================================
# SHOW PREVIOUS / CURRENT / NEXT
# ==================================================

for index, scene in enumerate(
    speech_scenes
):

    previous_scene = (
        speech_scenes[
            index - 1
        ]
        if index > 0
        else None
    )

    next_scene = (
        speech_scenes[
            index + 1
        ]
        if (
            index + 1
            < len(
                speech_scenes
            )
        )
        else None
    )


    scene_id = scene.get(
        "scene_id",
        "unknown",
    )


    current_text = str(
        scene.get(
            "dialogue",
            "",
        )
        or ""
    ).strip()


    previous_text = ""

    if previous_scene:

        previous_text = str(
            previous_scene.get(
                "dialogue",
                "",
            )
            or ""
        ).strip()


    next_text = ""

    if next_scene:

        next_text = str(
            next_scene.get(
                "dialogue",
                "",
            )
            or ""
        ).strip()


    analysis = scene.get(
        "analysis",
        {},
    )


    search = scene.get(
        "search",
        {},
    )


    print()
    print("-" * 80)

    print(
        "SCENE:",
        scene_id,
    )

    print(
        "TIME:",
        scene.get(
            "start"
        ),
        "->",
        scene.get(
            "end"
        ),
    )


    print()
    print(
        "PREVIOUS:"
    )

    print(
        previous_text
        or
        "[NONE]"
    )


    print()
    print(
        "CURRENT:"
    )

    print(
        current_text
    )


    print()
    print(
        "NEXT:"
    )

    print(
        next_text
        or
        "[NONE]"
    )


    print()
    print(
        "AI CONTEXT:"
    )

    print(
        analysis.get(
            "context",
            "",
        )
    )


    print()
    print(
        "AI SUBJECT:"
    )

    print(
        analysis.get(
            "subject",
            "",
        )
    )


    print()
    print(
        "AI LOCATION:"
    )

    print(
        analysis.get(
            "location",
            "",
        )
    )


    print()
    print(
        "PRIMARY QUERY:"
    )

    print(
        search.get(
            "primary_keyword",
            "",
        )
    )


    # ----------------------------------------------
    # SIMPLE BOUNDARY WARNINGS
    # ----------------------------------------------

    warnings = []


    lower_current = (
        current_text.lower()
    )


    weak_starts = (
        "and ",
        "but ",
        "while ",
        "because ",
        "which ",
        "where ",
        "that ",
        "dating ",
        "sometimes ",
        "attend ",
        "africa ",
    )


    if lower_current.startswith(
        weak_starts
    ):

        warnings.append(
            "CURRENT MAY DEPEND ON PREVIOUS SCENE"
        )


    weak_end_words = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "with",
        "from",
        "to",
        "in",
        "on",
        "of",
        "for",
        "before",
        "while",
        "that",
        "where",
        "north",
    }


    words = (
        current_text
        .lower()
        .replace(
            ",",
            "",
        )
        .replace(
            ".",
            "",
        )
        .split()
    )


    if words:

        last_word = words[
            -1
        ]

        if (
            last_word
            in weak_end_words
        ):

            warnings.append(
                "CURRENT MAY CONTINUE INTO NEXT SCENE"
            )


    if warnings:

        print()
        print(
            "BOUNDARY WARNING:"
        )

        for warning in warnings:

            print(
                "  -",
                warning,
            )


# ==================================================
# FOCUS ON KNOWN MOROCCO PROBLEM SCENES
# ==================================================

focus_ids = {
    "scene_004",
    "scene_008",
    "scene_010",
    "scene_011",
}


scene_map = {

    scene.get(
        "scene_id"
    ):
        scene

    for scene
    in speech_scenes
}


print()
print("=" * 80)
print("KNOWN SEMANTIC PROBLEM SCENES")
print("=" * 80)


for scene_id in sorted(
    focus_ids
):

    scene = scene_map.get(
        scene_id
    )


    if not scene:

        print(
            scene_id,
            "-> NOT FOUND",
        )

        continue


    index = speech_scenes.index(
        scene
    )


    previous_text = ""

    next_text = ""


    if index > 0:

        previous_text = str(
            speech_scenes[
                index - 1
            ].get(
                "dialogue",
                "",
            )
            or ""
        )


    if (
        index + 1
        < len(
            speech_scenes
        )
    ):

        next_text = str(
            speech_scenes[
                index + 1
            ].get(
                "dialogue",
                "",
            )
            or ""
        )


    current_text = str(
        scene.get(
            "dialogue",
            "",
        )
        or ""
    )


    semantic_window = (
        previous_text
        + " || CURRENT: "
        + current_text
        + " || NEXT: "
        + next_text
    )


    print()
    print(
        scene_id
    )

    print(
        semantic_window
    )


print()
print("=" * 80)
print("INSPECTION COMPLETE")
print("=" * 80)

print(
    "No production file was modified."
)