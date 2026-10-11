from pathlib import Path
import json
import shutil


ROOT = Path(
    __file__
).resolve().parent.parent


MANIFEST = (
    ROOT
    / "projects"
    / "voice_stock_speech_manifest.json"
)


BACKUP = (
    ROOT
    / "projects"
    / "voice_stock_speech_manifest_before_final2.json"
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("FIX FINAL TWO STOCK SCENES")
print("=" * 70)


# ==================================================
# CHECK
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

    print()
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


# ==================================================
# NEW STOCK-FRIENDLY VISUAL INTERPRETATIONS
# ==================================================

patches = {

    # --------------------------------------------------
    # "Still inside a rhythm stays, no..."
    #
    # Instead of abstract equalizers, use a real
    # person privately listening to music.
    # --------------------------------------------------

    "scene_012": {

        "analysis": {

            "context": (
                "A quiet person holds onto music "
                "internally despite a difficult "
                "or restrictive atmosphere."
            ),

            "subject":
                "Person listening to music with headphones",

            "action":
                "Listening quietly to music and feeling the rhythm",

            "location":
                "Simple indoor room or quiet personal space",

            "mood":
                "Introspective, resilient, hopeful",

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

                "listening to music alone",

                "headphones music close up",
            ],

            "avoid": [

                "audio equalizer graphic",

                "abstract waveform",

                "computer generated animation",
            ],
        },
    },


    # --------------------------------------------------
    # "Sing little hearts, don't hide your sound."
    #
    # "little hearts" is metaphorical.
    # Search for a real singer expressing a voice.
    # --------------------------------------------------

    "scene_016": {

        "analysis": {

            "context": (
                "A person finds the courage to sing "
                "openly instead of hiding their voice."
            ),

            "subject":
                "Singer performing with a microphone",

            "action":
                "Singing confidently and expressing emotion",

            "location":
                "Small stage, music room, or intimate performance space",

            "mood":
                "Hopeful, expressive, uplifting",

            "shot":
                "medium_close_up",

            "motion":
                "natural",
        },

        "search": {

            "primary_keyword":
                "singer singing microphone",

            "keywords": [

                "woman singing microphone",

                "young singer performing",

                "singer performance close up",

                "person singing on stage",

                "people singing together",
            ],

            "avoid": [

                "heart animation",

                "heart graphic",

                "cartoon hearts",
            ],
        },
    },
}


# ==================================================
# PATCH
# ==================================================

patched = []


for scene in data.get(
    "scenes",
    [],
):

    scene_id = scene.get(
        "scene_id"
    )


    if scene_id not in patches:

        continue


    patch = patches[
        scene_id
    ]


    print()
    print(
        "-" * 70
    )

    print(
        "Patching:",
        scene_id,
    )


    # ==================================================
    # ANALYSIS
    # ==================================================

    scene[
        "analysis"
    ] = patch[
        "analysis"
    ]


    # ==================================================
    # SEARCH
    # ==================================================

    scene[
        "search"
    ] = patch[
        "search"
    ]


    # ==================================================
    # RESET ONLY THIS SCENE'S STOCK STATE
    # ==================================================

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

        "candidates":
            [],

        "visual_ranking":
            [],

        "search_history":
            [],

        "selected_media":
            None,

        "download":
            None,

        "validation":
            None,

        "selection":
            None,
    }


    patched.append(
        scene_id
    )


# ==================================================
# VERIFY PATCH IDS
# ==================================================

expected = {
    "scene_012",
    "scene_016",
}


if set(
    patched
) != expected:

    raise RuntimeError(
        f"Patch mismatch. "
        f"Expected {expected}, "
        f"got {set(patched)}"
    )


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
# VERIFY SAVED FILE
# ==================================================

with open(
    MANIFEST,
    "r",
    encoding="utf-8",
) as file:

    verify = json.load(
        file
    )


verify_map = {

    scene.get(
        "scene_id"
    ):
        scene

    for scene
    in verify.get(
        "scenes",
        []
    )
}


print()

print("=" * 70)
print("VERIFICATION")
print("=" * 70)


for scene_id in (
    "scene_012",
    "scene_016",
):

    scene = verify_map[
        scene_id
    ]


    print()
    print(
        scene_id
    )

    print(
        "Context:",
        scene[
            "analysis"
        ][
            "context"
        ],
    )

    print(
        "Subject:",
        scene[
            "analysis"
        ][
            "subject"
        ],
    )

    print(
        "Primary keyword:",
        scene[
            "search"
        ][
            "primary_keyword"
        ],
    )

    print(
        "Keywords:"
    )


    for query in scene[
        "search"
    ][
        "keywords"
    ]:

        print(
            "  -",
            query,
        )


    print(
        "Stock status:",
        scene[
            "stock"
        ][
            "status"
        ],
    )


# ==================================================
# CHECK OTHER 24 SCENES
# ==================================================

validated_others = 0


for scene in verify.get(
    "scenes",
    [],
):

    if scene.get(
        "scene_id"
    ) in expected:

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

        validated_others += 1


print()

print(
    "Other validated scenes:",
    validated_others,
)


if validated_others != 24:

    raise RuntimeError(
        "Expected 24 previously validated scenes "
        f"but found {validated_others}."
    )


print()

print("=" * 70)
print("FINAL TWO SCENES PATCH SUCCESS")
print("=" * 70)

print(
    "scene_012 -> human listening to music"
)

print(
    "scene_016 -> real singer / microphone"
)

print(
    "24 existing validated scenes preserved"
)