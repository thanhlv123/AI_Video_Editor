from pathlib import Path
from copy import deepcopy
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
# IMPORT
# ==================================================

from pipeline.batch_pipeline import (
    BatchPipeline
)


# ==================================================
# HEADER
# ==================================================

print("=" * 70)
print("AI VIDEO EDITOR")
print("FULL VOICE STOCK SMOKE TEST")
print("=" * 70)


# ==================================================
# PATHS
# ==================================================

source_manifest_path = (
    ROOT
    / "projects"
    / "voice_ai_full_manifest.json"
)


smoke_manifest_path = (
    ROOT
    / "projects"
    / "voice_stock_smoke_manifest.json"
)


download_dir = (
    ROOT
    / "media"
    / "downloads"
)


# ==================================================
# TEST SCENES
# ==================================================

TEST_SCENE_IDS = [

    "scene_004",

    "scene_005",

    "scene_006",
]


# ==================================================
# CHECK SOURCE MANIFEST
# ==================================================

if not source_manifest_path.exists():

    raise FileNotFoundError(
        f"Full voice AI manifest not found: "
        f"{source_manifest_path}"
    )


print()
print(
    "Source manifest:",
    source_manifest_path
)

print(
    "Smoke manifest:",
    smoke_manifest_path
)

print(
    "Download directory:",
    download_dir
)

print(
    "Test scenes:",
    TEST_SCENE_IDS
)


# ==================================================
# LOAD FULL MANIFEST
# ==================================================

print()
print("=" * 70)
print("[1/6] LOAD FULL AI MANIFEST")
print("=" * 70)


with open(
    source_manifest_path,
    "r",
    encoding="utf-8"
) as file:

    full_manifest = json.load(
        file
    )


full_scenes = full_manifest.get(
    "scenes",
    []
)


if not full_scenes:

    raise RuntimeError(
        "Full manifest contains no scenes."
    )


print(
    "Full manifest scenes:",
    len(full_scenes)
)


# ==================================================
# SELECT 3 SPEECH SCENES
# ==================================================

print()
print("=" * 70)
print("[2/6] SELECT SMOKE TEST SCENES")
print("=" * 70)


selected_scenes = []


for scene in full_scenes:

    scene_id = scene.get(
        "scene_id"
    )


    if scene_id not in TEST_SCENE_IDS:
        continue


    if (
        scene.get(
            "scene_type"
        )
        != "speech"
    ):

        raise RuntimeError(
            f"{scene_id} is not a speech scene."
        )


    selected_scenes.append(
        deepcopy(
            scene
        )
    )


# Preserve requested order.

selected_scenes.sort(
    key=lambda scene: (
        TEST_SCENE_IDS.index(
            scene[
                "scene_id"
            ]
        )
    )
)


if (
    len(selected_scenes)
    != len(TEST_SCENE_IDS)
):

    found_ids = [

        scene.get(
            "scene_id"
        )

        for scene in selected_scenes
    ]


    raise RuntimeError(
        "Could not find all smoke test scenes. "
        f"Found: {found_ids}"
    )


for scene in selected_scenes:

    print()

    print(
        scene[
            "scene_id"
        ]
    )

    print(
        "  Time:",
        f"{scene['start']:.3f}",
        "->",
        f"{scene['end']:.3f}"
    )

    print(
        "  Dialogue:",
        scene.get(
            "dialogue"
        )
    )

    print(
        "  Primary keyword:",
        scene.get(
            "search",
            {}
        ).get(
            "primary_keyword"
        )
    )

    print(
        "  Preferred type:",
        scene.get(
            "stock",
            {}
        ).get(
            "preferred_type"
        )
    )


# ==================================================
# BUILD ISOLATED SMOKE MANIFEST
# ==================================================

print()
print("=" * 70)
print("[3/6] CREATE SMOKE MANIFEST")
print("=" * 70)


smoke_manifest = deepcopy(
    full_manifest
)


smoke_manifest[
    "scene_count"
] = len(
    selected_scenes
)


smoke_manifest[
    "scenes"
] = selected_scenes


# Add metadata describing this test.

smoke_manifest[
    "smoke_test"
] = {

    "enabled":
        True,

    "source_manifest":
        str(
            source_manifest_path
        ),

    "scene_ids":
        TEST_SCENE_IDS,
}


smoke_manifest_path.parent.mkdir(
    parents=True,
    exist_ok=True
)


with open(
    smoke_manifest_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        smoke_manifest,
        file,
        indent=4,
        ensure_ascii=False
    )


print(
    "Created:",
    smoke_manifest_path
)

print(
    "Scene count:",
    len(
        selected_scenes
    )
)


# ==================================================
# CREATE BATCH PIPELINE
# ==================================================

print()
print("=" * 70)
print("[4/6] CREATE STOCK PIPELINE")
print("=" * 70)


pipeline = BatchPipeline(

    manifest_path=smoke_manifest_path,

    download_dir=download_dir,

    # Automatically accept top visual result
    # when selector requests review.
    review_mode="auto",

    # Reuse completed scene on rerun.
    resume=True,

    # Important:
    # previous tests showed Top 10 produced
    # better semantic matching than Top 5.
    visual_top_n=10,
)


print(
    "Review mode:",
    "auto"
)

print(
    "Resume:",
    True
)

print(
    "Visual Top N:",
    10
)


# ==================================================
# RUN STOCK PIPELINE
# ==================================================

print()
print("=" * 70)
print("[5/6] RUN STOCK PIPELINE")
print("=" * 70)


summary = pipeline.run()


# ==================================================
# SUMMARY
# ==================================================

print()
print("=" * 70)
print("PIPELINE SUMMARY")
print("=" * 70)


print(
    "Total:",
    summary[
        "total"
    ]
)

print(
    "Validated:",
    summary[
        "validated"
    ]
)

print(
    "Skipped:",
    summary[
        "skipped"
    ]
)

print(
    "Needs review:",
    summary[
        "needs_review"
    ]
)

print(
    "Search again:",
    summary[
        "search_again"
    ]
)

print(
    "Failed:",
    summary[
        "failed"
    ]
)


# ==================================================
# RELOAD RESULT MANIFEST
# ==================================================

print()
print("=" * 70)
print("[6/6] VALIDATE STOCK RESULTS")
print("=" * 70)


with open(
    smoke_manifest_path,
    "r",
    encoding="utf-8"
) as file:

    result_manifest = json.load(
        file
    )


result_scenes = result_manifest.get(
    "scenes",
    []
)


if (
    len(result_scenes)
    != 3
):

    raise RuntimeError(
        "Expected exactly 3 result scenes."
    )


validated_count = 0


for scene in result_scenes:

    scene_id = scene.get(
        "scene_id"
    )


    stock = scene.get(
        "stock",
        {}
    )


    status = stock.get(
        "status"
    )


    selected_media = stock.get(
        "selected_media"
    )


    validation = stock.get(
        "validation",
        {}
    )


    download = stock.get(
        "download",
        {}
    )


    print()
    print("-" * 70)

    print(
        "Scene:",
        scene_id
    )

    print(
        "Status:",
        status
    )

    print(
        "Selected media:",
        selected_media
    )

    print(
        "Download:",
        download
    )

    print(
        "Validation:",
        validation
    )


    # ==================================================
    # VALIDATED SCENE
    # ==================================================

    if (
        status
        == "validated"
        and validation.get(
            "valid"
        )
        is True
    ):

        validated_count += 1


# ==================================================
# FINAL ASSERTIONS
# ==================================================

if (
    summary[
        "failed"
    ]
    != 0
):

    raise RuntimeError(
        "One or more smoke test scenes failed."
    )


if (
    summary[
        "needs_review"
    ]
    != 0
):

    raise RuntimeError(
        "Smoke test still contains "
        "needs_review scenes."
    )


if (
    summary[
        "search_again"
    ]
    != 0
):

    raise RuntimeError(
        "Smoke test still contains "
        "search_again scenes."
    )


# A rerun may report scenes as skipped because
# resume=True and they were already validated.
#
# Therefore:
#
# validated + skipped should equal 3.

completed_count = (
    summary[
        "validated"
    ]
    + summary[
        "skipped"
    ]
)


if completed_count != 3:

    raise RuntimeError(
        "Expected all 3 scenes to complete. "
        f"Completed: {completed_count}/3"
    )


# Reloaded manifest itself must contain
# three validated scenes.

if validated_count != 3:

    raise RuntimeError(
        "Result manifest does not contain "
        "3 validated scenes. "
        f"Validated: {validated_count}/3"
    )


# ==================================================
# SUCCESS
# ==================================================

print()
print("=" * 70)
print("STOCK SMOKE VALIDATION")
print("=" * 70)


print(
    "3 scenes completed: PASS"
)

print(
    "Stock selection: PASS"
)

print(
    "Download: PASS"
)

print(
    "FFprobe validation: PASS"
)

print(
    "Resume-compatible manifest: PASS"
)


print()
print("=" * 70)
print("FULL VOICE STOCK SMOKE SUCCESS")
print("=" * 70)


print(
    "Scenes:",
    len(
        result_scenes
    )
)

print(
    "Validated:",
    validated_count
)

print(
    "Manifest:",
    smoke_manifest_path
)

print(
    "Downloads:",
    download_dir
)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)