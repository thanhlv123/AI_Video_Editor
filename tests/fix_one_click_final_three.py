from pathlib import Path
import copy
import json
import shutil


ROOT = Path(
    __file__
).resolve().parent.parent


RUN_DIR = (
    ROOT
    / "projects"
    / "runs"
    / "test_voice_06671e51"
)


AI_MANIFEST = (
    RUN_DIR
    / "ai_manifest.json"
)


STOCK_MANIFEST = (
    RUN_DIR
    / "speech_stock_manifest.json"
)


FULL_MANIFEST = (
    RUN_DIR
    / "full_stock_manifest.json"
)


BACKUP = (
    RUN_DIR
    / "speech_stock_manifest_before_final_three.json"
)


TARGET_IDS = {
    "scene_012",
    "scene_017",
    "scene_025",
}


PATCHES = {

    # ==================================================
    # Still inside a rhythm stays, no
    # ==================================================

    "scene_012": {

        "dialogue":
            "Still inside a rhythm stays, "
            "no one can take that song away.",

        "analysis": {

            "context":
                "A person quietly feels music "
                "and holds onto an inner sense "
                "of rhythm and hope.",

            "subject":
                "Person listening to music with headphones",

            "action":
                "Listening peacefully to music",

            "location":
                "Quiet indoor room or personal space",

            "mood":
                "Introspective, calm, hopeful",

            "shot":
                "medium_close_up",

            "motion":
                "slow",
        },

        "search": {

            "primary_keyword":
                "person listening music headphones",

            "keywords": [

                "woman listening music headphones",

                "man listening music headphones",

                "person headphones eyes closed",

                "listening music alone",

                "relaxed person wearing headphones",
            ],

            "avoid": [

                "abstract waveform",

                "equalizer",

                "computer animation",
            ],
        },
    },


    # ==================================================
    # Silence breaks when hope is found...
    # ==================================================

    "scene_017": {

        "dialogue":
            "Silence breaks when hope is found, "
            "if you were taught to fall before.",

        "analysis": {

            "context":
                "A person moves from hardship "
                "toward hope and renewed confidence.",

            "subject":
                "Hopeful person in warm natural light",

            "action":
                "Walking forward confidently toward sunlight",

            "location":
                "Outdoor path or bright natural setting",

            "mood":
                "Hopeful, uplifting, resilient",

            "shot":
                "medium",

            "motion":
                "slow",
        },

        "search": {

            "primary_keyword":
                "person walking toward sunlight",

            "keywords": [

                "woman walking in sunlight",

                "man walking morning sunlight",

                "hopeful person outdoors",

                "person looking at sunrise",

                "person walking forward nature",
            ],

            "avoid": [

                "falling person",

                "injury",

                "dark abstract animation",
            ],
        },
    },


    # ==================================================
    # Fragment from:
    # And when the world feels close again,
    # the song remains our home.
    # ==================================================

    "scene_025": {

        "dialogue":
            "And when the world feels close again, "
            "the song remains our home.",

        "analysis": {

            "context":
                "A warm peaceful sense of returning "
                "to safety, comfort and home.",

            "subject":
                "Person relaxing in a warm comfortable home",

            "action":
                "Resting peacefully in a welcoming home",

            "location":
                "Cozy home interior",

            "mood":
                "Safe, warm, peaceful, comforting",

            "shot":
                "medium_wide",

            "motion":
                "slow",
        },

        "search": {

            "primary_keyword":
                "cozy home warm light",

            "keywords": [

                "person relaxing cozy home",

                "warm home interior evening",

                "person sitting by window home",

                "peaceful home interior",

                "comfortable living room warm light",
            ],

            "avoid": [

                "abstract background",

                "random texture",

                "computer animation",
            ],
        },
    },
}


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
    path,
    data,
):

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


def reset_stock(
    scene,
):

    old_stock = scene.get(
        "stock",
        {},
    )

    preferred_type = (
        old_stock.get(
            "preferred_type",
            "video",
        )
    )

    scene[
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


def patch_manifest(
    path,
    reset_stock_state,
):

    data = load_json(
        path
    )

    found = []


    for scene in data.get(
        "scenes",
        [],
    ):

        scene_id = scene.get(
            "scene_id"
        )


        if scene_id not in PATCHES:

            continue


        patch = PATCHES[
            scene_id
        ]


        scene[
            "dialogue"
        ] = patch[
            "dialogue"
        ]


        scene[
            "analysis"
        ] = copy.deepcopy(
            patch[
                "analysis"
            ]
        )


        scene[
            "search"
        ] = copy.deepcopy(
            patch[
                "search"
            ]
        )


        if reset_stock_state:

            reset_stock(
                scene
            )


        found.append(
            scene_id
        )


    if set(
        found
    ) != TARGET_IDS:

        raise RuntimeError(

            f"{path.name}: "

            f"expected {TARGET_IDS}, "

            f"found {set(found)}"
        )


    save_json(
        path,
        data,
    )


    return data


print("=" * 70)
print("AI VIDEO EDITOR")
print("FIX FINAL THREE STOCK SCENES")
print("=" * 70)


if not AI_MANIFEST.exists():

    raise FileNotFoundError(
        AI_MANIFEST
    )


if not STOCK_MANIFEST.exists():

    raise FileNotFoundError(
        STOCK_MANIFEST
    )


# ==================================================
# BACKUP
# ==================================================

if not BACKUP.exists():

    shutil.copy2(
        STOCK_MANIFEST,
        BACKUP,
    )

    print(
        "Backup:",
        BACKUP,
    )


# ==================================================
# PATCH AI MANIFEST
# ==================================================

patch_manifest(

    AI_MANIFEST,

    reset_stock_state=False,
)


print(
    "AI manifest patched: PASS"
)


# ==================================================
# PATCH STOCK PROGRESS
# ==================================================

stock_data = patch_manifest(

    STOCK_MANIFEST,

    reset_stock_state=True,
)


print(
    "Speech stock manifest patched: PASS"
)


# ==================================================
# REMOVE STALE FULL MANIFEST
# ==================================================

if FULL_MANIFEST.exists():

    FULL_MANIFEST.unlink()

    print(
        "Old full stock manifest removed."
    )


# ==================================================
# VERIFY 23 EXISTING VALIDATED SCENES
# ==================================================

validated_others = []


for scene in stock_data.get(
    "scenes",
    [],
):

    scene_id = scene.get(
        "scene_id"
    )


    if scene_id in TARGET_IDS:

        continue


    stock = scene.get(
        "stock",
        {},
    )


    if (
        stock.get(
            "status"
        )
        == "validated"
    ):

        validated_others.append(
            scene_id
        )


print()

print(
    "Existing validated scenes:",
    len(
        validated_others
    ),
)


if len(
    validated_others
) != 23:

    raise RuntimeError(

        "Expected 23 existing "
        "validated scenes, found "

        f"{len(validated_others)}"
    )


# ==================================================
# DISPLAY PATCH
# ==================================================

for scene in stock_data.get(
    "scenes",
    [],
):

    scene_id = scene.get(
        "scene_id"
    )


    if scene_id not in TARGET_IDS:

        continue


    print()
    print(
        "-" * 70
    )

    print(
        scene_id
    )

    print(
        "Dialogue:",
        scene.get(
            "dialogue"
        ),
    )

    print(
        "Primary:",
        scene[
            "search"
        ][
            "primary_keyword"
        ],
    )

    print(
        "Keywords:"
    )


    for keyword in scene[
        "search"
    ][
        "keywords"
    ]:

        print(
            "  -",
            keyword,
        )


    print(
        "Stock status:",
        scene[
            "stock"
        ][
            "status"
        ],
    )


print()

print("=" * 70)
print("FINAL THREE PATCH SUCCESS")
print("=" * 70)

print(
    "scene_012 -> real person listening to music"
)

print(
    "scene_017 -> hopeful person walking into sunlight"
)

print(
    "scene_025 -> warm cozy home"
)

print(
    "23 validated scenes preserved: PASS"
)