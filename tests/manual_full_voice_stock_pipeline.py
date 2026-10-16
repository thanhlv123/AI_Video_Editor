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


from pipeline.batch_pipeline import (
    BatchPipeline
)


# ==================================================
# PATHS
# ==================================================

SOURCE_AI_MANIFEST = (
    ROOT
    / "projects"
    / "voice_ai_full_manifest.json"
)


SPEECH_STOCK_MANIFEST = (
    ROOT
    / "projects"
    / "voice_stock_speech_manifest.json"
)


SMOKE_MANIFEST = (
    ROOT
    / "projects"
    / "voice_stock_smoke_manifest.json"
)


FULL_STOCK_MANIFEST = (
    ROOT
    / "projects"
    / "voice_stock_full_manifest.json"
)


DOWNLOAD_DIR = (
    ROOT
    / "media"
    / "downloads"
)


DURATION_TOLERANCE = 0.05


# ==================================================
# JSON HELPERS
# ==================================================

def load_json(
    path,
):

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def save_json(
    data,
    path,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False,
        )


# ==================================================
# NUMBER HELPER
# ==================================================

def to_float(
    value,
    default=0.0,
):

    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return float(
            default
        )


# ==================================================
# VALIDATED STOCK CHECK
# ==================================================

def stock_is_valid_for_scene(
    scene,
    stock,
):

    if not isinstance(
        stock,
        dict,
    ):

        return False


    if (
        stock.get(
            "status"
        )
        != "validated"
    ):

        return False


    validation = stock.get(
        "validation",
        {},
    )


    if (
        validation.get(
            "valid"
        )
        is not True
    ):

        return False


    download = stock.get(
        "download",
        {},
    )


    download_path = download.get(
        "path"
    )


    if not download_path:

        return False


    if not Path(
        download_path
    ).exists():

        return False


    selected_media = stock.get(
        "selected_media",
        {},
    )


    media_type = str(
        selected_media.get(
            "media_type",
            ""
        )
        or ""
    ).lower()


    # Images have no duration requirement.

    if media_type != "video":

        return True


    scene_duration = to_float(
        scene.get(
            "duration"
        ),
        0.0,
    )


    actual_duration = to_float(
        validation.get(
            "duration"
        ),
        0.0,
    )


    if (
        actual_duration
        + DURATION_TOLERANCE
        < scene_duration
    ):

        return False


    return True


# ==================================================
# HEADER
# ==================================================

print("=" * 70)

print(
    "AI VIDEO EDITOR"
)

print(
    "FULL VOICE STOCK PIPELINE"
)

print("=" * 70)


print()

print(
    "AI manifest:",
    SOURCE_AI_MANIFEST,
)

print(
    "Speech progress:",
    SPEECH_STOCK_MANIFEST,
)

print(
    "Smoke results:",
    SMOKE_MANIFEST,
)

print(
    "Final stock manifest:",
    FULL_STOCK_MANIFEST,
)

print(
    "Download directory:",
    DOWNLOAD_DIR,
)


# ==================================================
# CHECK SOURCE
# ==================================================

if not SOURCE_AI_MANIFEST.exists():

    raise FileNotFoundError(
        f"Missing AI manifest: "
        f"{SOURCE_AI_MANIFEST}"
    )


# ==================================================
# LOAD SOURCE 30-SCENE MANIFEST
# ==================================================

print()

print("=" * 70)

print(
    "[1/7] LOAD FULL AI MANIFEST"
)

print("=" * 70)


source_manifest = load_json(
    SOURCE_AI_MANIFEST
)


source_scenes = source_manifest.get(
    "scenes",
    [],
)


if not source_scenes:

    raise RuntimeError(
        "AI manifest contains no scenes."
    )


speech_source = [

    scene

    for scene
    in source_scenes

    if (
        scene.get(
            "scene_type"
        )
        == "speech"
    )
]


gap_source = [

    scene

    for scene
    in source_scenes

    if (
        scene.get(
            "scene_type"
        )
        == "gap"
    )
]


print(
    "Total scenes:",
    len(
        source_scenes
    ),
)

print(
    "Speech scenes:",
    len(
        speech_source
    ),
)

print(
    "Gap scenes:",
    len(
        gap_source
    ),
)


if len(
    speech_source
) != 26:

    raise RuntimeError(
        "Expected 26 speech scenes, "
        f"found {len(speech_source)}."
    )


if len(
    gap_source
) != 4:

    raise RuntimeError(
        "Expected 4 gap scenes, "
        f"found {len(gap_source)}."
    )


# ==================================================
# CREATE OR RESUME SPEECH MANIFEST
# ==================================================

print()

print("=" * 70)

print(
    "[2/7] PREPARE PERSISTENT SPEECH MANIFEST"
)

print("=" * 70)


if not SPEECH_STOCK_MANIFEST.exists():

    print(
        "Creating new persistent "
        "speech stock manifest..."
    )


    speech_manifest = deepcopy(
        source_manifest
    )


    speech_manifest[
        "scene_count"
    ] = len(
        speech_source
    )


    speech_manifest[
        "scenes"
    ] = deepcopy(
        speech_source
    )


    speech_manifest[
        "stock_pipeline"
    ] = {

        "type":
            "speech_only",

        "resume":
            True,

        "created_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),
    }


    # ==================================================
    # SEED SUCCESSFUL SMOKE RESULTS
    # ==================================================

    seeded = 0


    if SMOKE_MANIFEST.exists():

        print()

        print(
            "Importing validated smoke results..."
        )


        smoke_manifest = load_json(
            SMOKE_MANIFEST
        )


        smoke_map = {

            scene.get(
                "scene_id"
            ):
                scene

            for scene
            in smoke_manifest.get(
                "scenes",
                [],
            )
        }


        for scene in speech_manifest[
            "scenes"
        ]:

            scene_id = scene.get(
                "scene_id"
            )


            smoke_scene = smoke_map.get(
                scene_id
            )


            if smoke_scene is None:

                continue


            smoke_stock = smoke_scene.get(
                "stock",
                {},
            )


            if not stock_is_valid_for_scene(
                scene,
                smoke_stock,
            ):

                continue


            scene[
                "stock"
            ] = deepcopy(
                smoke_stock
            )


            seeded += 1


            print(
                "Seeded:",
                scene_id,
            )


    print()

    print(
        "Validated smoke scenes imported:",
        seeded,
    )


    save_json(
        speech_manifest,
        SPEECH_STOCK_MANIFEST,
    )


    print(
        "Created:",
        SPEECH_STOCK_MANIFEST,
    )


else:

    print(
        "Existing progress manifest found."
    )

    print(
        "RESUME MODE: existing progress "
        "will NOT be overwritten."
    )


# ==================================================
# CHECK CURRENT PROGRESS
# ==================================================

speech_manifest = load_json(
    SPEECH_STOCK_MANIFEST
)


speech_scenes = speech_manifest.get(
    "scenes",
    [],
)


if len(
    speech_scenes
) != 26:

    raise RuntimeError(
        "Speech progress manifest must "
        "contain exactly 26 scenes."
    )


already_validated = []


pending = []


for scene in speech_scenes:

    if stock_is_valid_for_scene(
        scene,
        scene.get(
            "stock",
            {},
        ),
    ):

        already_validated.append(
            scene.get(
                "scene_id"
            )
        )

    else:

        pending.append(
            scene.get(
                "scene_id"
            )
        )


print()

print(
    "Already validated:",
    len(
        already_validated
    ),
)

print(
    "Pending:",
    len(
        pending
    ),
)


if already_validated:

    print()

    print(
        "Validated scene IDs:"
    )


    for scene_id in already_validated:

        print(
            "  -",
            scene_id,
        )


# ==================================================
# RUN BATCH PIPELINE
# ==================================================

print()

print("=" * 70)

print(
    "[3/7] RUN STOCK PIPELINE"
)

print("=" * 70)


pipeline = BatchPipeline(

    manifest_path=(
        SPEECH_STOCK_MANIFEST
    ),

    download_dir=(
        DOWNLOAD_DIR
    ),

    review_mode="auto",

    resume=True,

    visual_top_n=10,
)


summary = pipeline.run()


print()

print("=" * 70)

print(
    "BATCH SUMMARY"
)

print("=" * 70)


for key in (

    "total",

    "validated",

    "skipped",

    "needs_review",

    "search_again",

    "failed",

):

    print(
        f"{key}:",
        summary.get(
            key
        ),
    )


# ==================================================
# RELOAD SAVED PROGRESS
# ==================================================

print()

print("=" * 70)

print(
    "[4/7] VERIFY ALL SPEECH SCENES"
)

print("=" * 70)


speech_manifest = load_json(
    SPEECH_STOCK_MANIFEST
)


speech_scenes = speech_manifest.get(
    "scenes",
    [],
)


invalid_speech = []


for scene in speech_scenes:

    if not stock_is_valid_for_scene(
        scene,
        scene.get(
            "stock",
            {},
        ),
    ):

        invalid_speech.append(
            scene.get(
                "scene_id"
            )
        )


if invalid_speech:

    print()

    print(
        "The following scenes are "
        "not complete yet:"
    )


    for scene_id in invalid_speech:

        print(
            "  -",
            scene_id,
        )


    print()

    print(
        "Progress has been saved."
    )

    print(
        "Run the SAME command again "
        "to resume."
    )


    raise RuntimeError(
        f"{len(invalid_speech)} speech "
        "scene(s) remain incomplete."
    )


print(
    "All 26 speech scenes validated: PASS"
)


# ==================================================
# BUILD SPEECH RESULT MAP
# ==================================================

speech_result_map = {

    scene.get(
        "scene_id"
    ):
        scene

    for scene
    in speech_scenes
}


# ==================================================
# BUILD FINAL 30-SCENE MANIFEST
# ==================================================

print()

print("=" * 70)

print(
    "[5/7] BUILD GAP MEDIA REUSE"
)

print("=" * 70)


final_manifest = deepcopy(
    source_manifest
)


final_scenes = final_manifest.get(
    "scenes",
    [],
)


gap_reused = 0


for scene in final_scenes:

    scene_id = scene.get(
        "scene_id"
    )


    scene_type = scene.get(
        "scene_type"
    )


    # ==================================================
    # SPEECH
    # ==================================================

    if scene_type == "speech":

        result_scene = (
            speech_result_map.get(
                scene_id
            )
        )


        if result_scene is None:

            raise RuntimeError(
                f"Missing speech stock result: "
                f"{scene_id}"
            )


        scene[
            "stock"
        ] = deepcopy(
            result_scene.get(
                "stock",
                {},
            )
        )


        continue


    # ==================================================
    # GAP
    # ==================================================

    if scene_type == "gap":

        reference_id = scene.get(
            "gap_source_scene_id"
        )


        if not reference_id:

            raise RuntimeError(
                f"{scene_id}: "
                "gap_source_scene_id missing."
            )


        reference_scene = (
            speech_result_map.get(
                reference_id
            )
        )


        if reference_scene is None:

            raise RuntimeError(
                f"{scene_id}: reference speech "
                f"scene not found: {reference_id}"
            )


        reference_stock = (
            reference_scene.get(
                "stock",
                {},
            )
        )


        if not stock_is_valid_for_scene(
            reference_scene,
            reference_stock,
        ):

            raise RuntimeError(
                f"{scene_id}: reference media "
                f"is not validated."
            )


        selected_media = deepcopy(
            reference_stock.get(
                "selected_media"
            )
        )


        download = deepcopy(
            reference_stock.get(
                "download"
            )
        )


        validation = deepcopy(
            reference_stock.get(
                "validation"
            )
        )


        # ==================================================
        # CHECK GAP DURATION
        # ==================================================

        media_type = str(
            selected_media.get(
                "media_type",
                ""
            )
            or ""
        ).lower()


        if media_type == "video":

            gap_duration = to_float(
                scene.get(
                    "duration"
                ),
                0.0,
            )


            actual_duration = to_float(
                validation.get(
                    "duration"
                ),
                0.0,
            )


            if (
                actual_duration
                + DURATION_TOLERANCE
                < gap_duration
            ):

                raise RuntimeError(
                    f"{scene_id}: reused media "
                    f"is too short. "
                    f"{actual_duration:.3f}s < "
                    f"{gap_duration:.3f}s"
                )


        preferred_type = (
            reference_stock.get(
                "preferred_type",
                "video",
            )
        )


        scene[
            "stock"
        ] = {

            "status":
                "validated",

            "preferred_type":
                preferred_type,

            "selected_media":
                selected_media,

            "download":
                download,

            "validation":
                validation,

            "candidates":
                [],

            "visual_ranking":
                [],

            "search_history":
                [],

            "reuse": {

                "enabled":
                    True,

                "source_scene_id":
                    reference_id,

                "reason":
                    "gap_scene_visual_continuation",
            },
        }


        gap_reused += 1


        print(
            f"{scene_id} -> reuse "
            f"{reference_id}"
        )


# ==================================================
# FINAL METADATA
# ==================================================

final_manifest[
    "scene_count"
] = len(
    final_scenes
)


final_manifest[
    "stock_pipeline"
] = {

    "completed_at": (
        datetime.now()
        .astimezone()
        .isoformat()
    ),

    "speech_scenes":
        26,

    "gap_scenes":
        4,

    "gap_media_reused":
        gap_reused,

    "download_dir":
        str(
            DOWNLOAD_DIR
        ),

    "review_mode":
        "auto",

    "visual_top_n":
        10,

    "duration_safety":
        True,
}


# ==================================================
# SAVE FULL STOCK MANIFEST
# ==================================================

print()

print("=" * 70)

print(
    "[6/7] SAVE FULL STOCK MANIFEST"
)

print("=" * 70)


save_json(
    final_manifest,
    FULL_STOCK_MANIFEST,
)


print(
    "Saved:",
    FULL_STOCK_MANIFEST,
)


print(
    "Size:",
    FULL_STOCK_MANIFEST.stat().st_size,
    "bytes",
)


# ==================================================
# FINAL VALIDATION
# ==================================================

print()

print("=" * 70)

print(
    "[7/7] FINAL VALIDATION"
)

print("=" * 70)


saved_manifest = load_json(
    FULL_STOCK_MANIFEST
)


saved_scenes = saved_manifest.get(
    "scenes",
    [],
)


if len(
    saved_scenes
) != 30:

    raise RuntimeError(
        "Final manifest must contain "
        "30 scenes."
    )


speech_count = 0

gap_count = 0

validated_count = 0


for scene in saved_scenes:

    scene_type = scene.get(
        "scene_type"
    )


    stock = scene.get(
        "stock",
        {},
    )


    if scene_type == "speech":

        speech_count += 1


    elif scene_type == "gap":

        gap_count += 1


    if (
        stock.get(
            "status"
        )
        == "validated"
        and stock.get(
            "validation",
            {},
        ).get(
            "valid"
        )
        is True
    ):

        validated_count += 1


if speech_count != 26:

    raise RuntimeError(
        f"Speech count invalid: "
        f"{speech_count}"
    )


if gap_count != 4:

    raise RuntimeError(
        f"Gap count invalid: "
        f"{gap_count}"
    )


if validated_count != 30:

    raise RuntimeError(
        f"Validated scene count invalid: "
        f"{validated_count}/30"
    )


print(
    "30 total scenes: PASS"
)

print(
    "26 speech scenes: PASS"
)

print(
    "4 gap scenes: PASS"
)

print(
    "26 speech media validated: PASS"
)

print(
    "4 gap media reused: PASS"
)

print(
    "Duration safety: PASS"
)

print(
    "Persistent resume manifest: PASS"
)


print()

print("=" * 70)

print(
    "FULL VOICE STOCK PIPELINE SUCCESS"
)

print("=" * 70)


print(
    "Total scenes:",
    len(
        saved_scenes
    )
)

print(
    "Validated:",
    validated_count
)

print(
    "Speech:",
    speech_count
)

print(
    "Gap:",
    gap_count
)

print(
    "Final manifest:",
    FULL_STOCK_MANIFEST
)


print()

print("=" * 70)

print(
    "TEST COMPLETE"
)

print("=" * 70)