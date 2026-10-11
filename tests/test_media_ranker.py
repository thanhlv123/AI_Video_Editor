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


from stock.ranker import (
    MediaRanker
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("MEDIA RANKER TEST")
print("=" * 70)


# ==================================================
# LOAD MANIFEST
# ==================================================

manifest_path = (
    ROOT
    / "projects"
    / "analysis_manifest.json"
)


with open(
    manifest_path,
    "r",
    encoding="utf-8"
) as file:

    manifest = json.load(
        file
    )


scene = manifest[
    "scenes"
][0]


candidates = scene[
    "stock"
][
    "candidates"
]


print()
print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Primary keyword:",
    scene[
        "search"
    ][
        "primary_keyword"
    ]
)

print(
    "Scene duration:",
    scene["duration"]
)

print(
    "Candidates:",
    len(candidates)
)


if not candidates:

    raise RuntimeError(
        "No candidates found. "
        "Run test_stock_search_manager.py first."
    )


# ==================================================
# RANK
# ==================================================

ranker = MediaRanker(

    target_width=1920,

    target_height=1080
)


ranked = ranker.rank(

    scene=scene,

    candidates=candidates
)


# ==================================================
# DISPLAY TOP 10
# ==================================================

print()
print("=" * 70)
print("TOP RANKED CANDIDATES")
print("=" * 70)


for index, item in enumerate(
    ranked[:10],
    start=1
):

    print()

    print(
        f"{index}. "
        f"{item['provider']} / "
        f"{item['media_id']}"
    )

    print(
        "   Score:",
        item["score"]
    )

    print(
        "   Query:",
        item.get(
            "matched_query"
        )
    )

    print(
        "   Duration:",
        item.get(
            "duration"
        )
    )

    print(
        "   Resolution:",
        f"{item.get('width')}x"
        f"{item.get('height')}"
    )

    print(
        "   Title:",
        item.get(
            "title"
        )
    )

    print(
        "   Score details:",
        item[
            "score_details"
        ]
    )


# ==================================================
# STORE RANKED CANDIDATES
# ==================================================

scene[
    "stock"
][
    "candidates"
] = ranked


scene[
    "stock"
][
    "status"
] = "ranked"


with open(
    manifest_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        manifest,
        file,
        indent=4,
        ensure_ascii=False
    )


print()
print("=" * 70)
print("MEDIA RANKER TEST SUCCESS")
print("=" * 70)


print(
    "Best candidate:",
    ranked[0]["media_id"]
)

print(
    "Best score:",
    ranked[0]["score"]
)

print(
    "Manifest status:",
    scene["stock"]["status"]
)