from pathlib import Path
import json
import shutil


ROOT = Path(
    __file__
).resolve().parent.parent


VISUAL_RANKER = (
    ROOT
    / "stock"
    / "visual_ranker.py"
)


MANIFEST = (
    ROOT
    / "projects"
    / "voice_stock_speech_manifest.json"
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("FIX REMAINING STOCK SCENES")
print("=" * 70)


# ==================================================
# 1. PATCH KIE RETRY CODES
# ==================================================

print()
print("[1/3] PATCH KIE VISUAL RETRY")


if not VISUAL_RANKER.exists():

    raise FileNotFoundError(
        VISUAL_RANKER
    )


source = VISUAL_RANKER.read_text(
    encoding="utf-8"
)


# Keep a backup before modifying.

backup = VISUAL_RANKER.with_suffix(
    ".py.bak"
)


if not backup.exists():

    shutil.copy2(
        VISUAL_RANKER,
        backup,
    )

    print(
        "Backup created:",
        backup,
    )


# ==================================================
# ADD CLOUDFLARE / TRANSIENT CODES
#
# 520 = unknown server error
# 522 = connection timed out
# 523 = origin unreachable
# 524 = upstream timeout
# ==================================================

if "            524," in source:

    print(
        "HTTP 524 retry already installed."
    )


else:

    old = """            504,
        }"""


    new = """            504,

            520,

            522,

            523,

            524,
        }"""


    if old not in source:

        raise RuntimeError(
            "Could not locate retry HTTP "
            "code block in visual_ranker.py"
        )


    source = source.replace(
        old,
        new,
        1,
    )


    VISUAL_RANKER.write_text(
        source,
        encoding="utf-8",
    )


    print(
        "Added retry codes:",
        "520, 522, 523, 524",
    )


# ==================================================
# 2. PATCH SEARCH TERMS
# ==================================================

print()
print("[2/3] PATCH REMAINING SEARCH TERMS")


if not MANIFEST.exists():

    raise FileNotFoundError(
        MANIFEST
    )


with open(
    MANIFEST,
    "r",
    encoding="utf-8",
) as file:

    data = json.load(
        file
    )


# More concrete, stock-friendly queries.
#
# The previous queries were too abstract:
#
# scene_012:
#   abstract rhythm visual
#
# scene_016:
#   singing hearts animation
#
# Pexels generally performs better with
# visible objects / motion / environments.

patches = {

    "scene_012": {

        "primary_keyword":
            "music equalizer lights",

        "keywords": [

            "audio waveform animation",

            "pulsing lights music",

            "equalizer animation",

            "sound wave animation",

            "abstract moving lights",
        ],
    },


    "scene_016": {

        "primary_keyword":
            "floating hearts animation",

        "keywords": [

            "colorful heart animation",

            "heart background animation",

            "romantic hearts moving",

            "music notes animation",

            "love hearts background",
        ],
    },
}


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


    search = scene.setdefault(
        "search",
        {},
    )


    search[
        "primary_keyword"
    ] = patch[
        "primary_keyword"
    ]


    search[
        "keywords"
    ] = list(
        patch[
            "keywords"
        ]
    )


    # Remove stale generated retry queries.

    search.pop(
        "search_queries",
        None,
    )

    search.pop(
        "queries",
        None,
    )


    # ==================================================
    # RESET ONLY STOCK RESULT FOR THIS SCENE
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

        "searches":
            [],

        "candidates":
            [],

        "selected_media":
            None,
    }


    patched.append(
        scene_id
    )


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


print(
    "Patched scenes:",
    patched,
)


if set(
    patched
) != {
    "scene_012",
    "scene_016",
}:

    raise RuntimeError(
        "Could not patch both remaining scenes."
    )


# ==================================================
# 3. VERIFY
# ==================================================

print()
print("[3/3] VERIFY")


source = VISUAL_RANKER.read_text(
    encoding="utf-8"
)


if "            524," not in source:

    raise RuntimeError(
        "HTTP 524 retry patch failed."
    )


with open(
    MANIFEST,
    "r",
    encoding="utf-8",
) as file:

    verify_data = json.load(
        file
    )


verify_map = {

    scene.get(
        "scene_id"
    ):
        scene

    for scene
    in verify_data.get(
        "scenes",
        []
    )
}


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
        "Primary:",
        scene[
            "search"
        ][
            "primary_keyword"
        ],
    )

    print(
        "Keywords:",
        scene[
            "search"
        ][
            "keywords"
        ],
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
print("FIX COMPLETE")
print("=" * 70)

print(
    "KIE HTTP 524 retry: PASS"
)

print(
    "scene_012 search patch: PASS"
)

print(
    "scene_016 search patch: PASS"
)

print(
    "Existing validated scenes preserved: PASS"
)