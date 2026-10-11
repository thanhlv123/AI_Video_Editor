from pathlib import Path
import json
import shutil


ROOT = Path(
    __file__
).resolve().parent.parent


MANIFEST = (
    ROOT
    / "projects"
    / "voice_stock_full_manifest.json"
)


BACKUP = (
    ROOT
    / "projects"
    / "voice_stock_full_manifest_before_gap_v2.json"
)


TOLERANCE = 0.05


print("=" * 70)
print("AI VIDEO EDITOR")
print("GAP REUSE V2")
print("=" * 70)


# ==================================================
# HELPERS
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


def media_identity(
    scene,
):

    stock = scene.get(
        "stock",
        {},
    )


    selected = stock.get(
        "selected_media",
        {},
    )


    provider = str(
        selected.get(
            "provider",
            ""
        )
        or ""
    )


    media_id = str(
        selected.get(
            "media_id",
            ""
        )
        or ""
    )


    download = stock.get(
        "download",
        {},
    )


    path = str(
        download.get(
            "path",
            ""
        )
        or ""
    )


    if media_id:

        return (
            provider,
            media_id,
        )


    return (
        "path",
        path,
    )


# ==================================================
# CHECK MANIFEST
# ==================================================

if not MANIFEST.exists():

    raise FileNotFoundError(
        MANIFEST
    )


# ==================================================
# BACKUP
# ==================================================

if not BACKUP.exists():

    shutil.copy2(
        MANIFEST,
        BACKUP,
    )


    print(
        "Backup created:",
        BACKUP,
    )


# ==================================================
# LOAD
# ==================================================

with open(
    MANIFEST,
    "r",
    encoding="utf-8",
) as file:

    data = json.load(
        file
    )


scenes = data.get(
    "scenes",
    [],
)


if len(
    scenes
) != 30:

    raise RuntimeError(
        f"Expected 30 scenes, "
        f"found {len(scenes)}."
    )


scenes = sorted(

    scenes,

    key=lambda item: to_float(
        item.get(
            "start"
        )
    ),
)


# ==================================================
# CALCULATE SOURCE STARTS
# ==================================================

previous_identity = None

source_cursor = 0.0


results = []


for scene in scenes:

    scene_id = scene.get(
        "scene_id"
    )


    stock = scene.get(
        "stock",
        {},
    )


    if (
        stock.get(
            "status"
        )
        != "validated"
    ):

        raise RuntimeError(
            f"{scene_id}: "
            "stock is not validated."
        )


    selected = stock.get(
        "selected_media",
        {},
    )


    media_type = str(
        selected.get(
            "media_type",
            "video",
        )
        or "video"
    ).lower()


    scene_duration = to_float(
        scene.get(
            "duration"
        )
    )


    validation = stock.get(
        "validation",
        {},
    )


    media_duration = to_float(
        validation.get(
            "duration"
        )
    )


    identity = media_identity(
        scene
    )


    # ==================================================
    # IMAGES
    # ==================================================

    if media_type == "image":

        source_start = 0.0

        source_cursor = 0.0

        previous_identity = identity


    # ==================================================
    # VIDEOS
    # ==================================================

    else:

        if media_duration <= 0:

            raise RuntimeError(
                f"{scene_id}: "
                "invalid source video duration."
            )


        # ----------------------------------------------
        # NEW MEDIA
        # ----------------------------------------------

        if identity != previous_identity:

            source_start = 0.0


        # ----------------------------------------------
        # SAME MEDIA AS PREVIOUS SCENE
        # ----------------------------------------------

        else:

            proposed_start = (
                source_cursor
            )


            proposed_end = (
                proposed_start
                + scene_duration
            )


            # Continue from where previous clip ended.

            if (
                proposed_end
                <= media_duration
                + TOLERANCE
            ):

                source_start = (
                    proposed_start
                )


            # Not enough source remains.
            # Restart from the beginning.

            else:

                source_start = 0.0


        # ==================================================
        # FINAL SAFETY CHECK
        # ==================================================

        if (
            source_start
            + scene_duration
            > media_duration
            + TOLERANCE
        ):

            raise RuntimeError(

                f"{scene_id}: "

                f"source duration too short. "

                f"source_start="
                f"{source_start:.3f}, "

                f"scene_duration="
                f"{scene_duration:.3f}, "

                f"media_duration="
                f"{media_duration:.3f}"
            )


        source_cursor = (
            source_start
            + scene_duration
        )


        previous_identity = (
            identity
        )


    # ==================================================
    # UPDATE TIMELINE INFO
    # ==================================================

    timeline = stock.setdefault(
        "timeline",
        {},
    )


    timeline[
        "source_start"
    ] = round(
        source_start,
        6,
    )


    timeline[
        "source_end"
    ] = round(
        source_start
        + scene_duration,
        6,
    )


    timeline[
        "source_strategy"
    ] = (
        "gap_reuse_v2"
    )


    results.append({

        "scene_id":
            scene_id,

        "identity":
            identity,

        "source_start":
            source_start,

        "source_end":
            source_start
            + scene_duration,

        "scene_duration":
            scene_duration,

        "media_duration":
            media_duration,
    })


# ==================================================
# SAVE
# ==================================================

with open(
    MANIFEST,
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
# PRINT RESULTS
# ==================================================

print()

print("=" * 70)

print(
    "SOURCE START PLAN"
)

print("=" * 70)


for item in results:

    print(

        f"{item['scene_id']} | "

        f"source "
        f"{item['source_start']:.3f}"
        f" -> "
        f"{item['source_end']:.3f} | "

        f"scene "
        f"{item['scene_duration']:.3f}s | "

        f"media "
        f"{item['media_duration']:.3f}s"
    )


# ==================================================
# SPECIFIC CHECKS
# ==================================================

result_map = {

    item[
        "scene_id"
    ]:
        item

    for item
    in results
}


print()

print("=" * 70)

print(
    "OPENING REUSE CHECK"
)

print("=" * 70)


for scene_id in (

    "scene_001",
    "scene_002",
    "scene_003",
    "scene_004",

):

    item = result_map[
        scene_id
    ]


    print(

        scene_id,

        "source_start =",

        round(
            item[
                "source_start"
            ],
            3,
        ),
    )


print()

print("=" * 70)

print(
    "ENDING GAP REUSE CHECK"
)

print("=" * 70)


for scene_id in (

    "scene_028",
    "scene_029",

):

    item = result_map[
        scene_id
    ]


    print(

        scene_id,

        "source_start =",

        round(
            item[
                "source_start"
            ],
            3,
        ),
    )


# ==================================================
# EXPECTED OPENING BEHAVIOR
# ==================================================

scene_001 = result_map[
    "scene_001"
]


scene_002 = result_map[
    "scene_002"
]


if (
    scene_002[
        "source_start"
    ]
    <= scene_001[
        "source_start"
    ]
):

    raise RuntimeError(
        "scene_002 did not continue "
        "from scene_001."
    )


# ==================================================
# EXPECTED GAP 029 BEHAVIOR
# ==================================================

scene_028 = result_map[
    "scene_028"
]


scene_029 = result_map[
    "scene_029"
]


if (
    scene_029[
        "source_start"
    ]
    <= scene_028[
        "source_start"
    ]
):

    raise RuntimeError(
        "scene_029 did not continue "
        "from scene_028."
    )


print()

print("=" * 70)

print(
    "GAP REUSE V2 SUCCESS"
)

print("=" * 70)


print(
    "Sequential source reuse: PASS"
)

print(
    "Automatic restart when source exhausted: PASS"
)

print(
    "Source duration safety: PASS"
)

print(
    "Manifest updated:",
    MANIFEST
)