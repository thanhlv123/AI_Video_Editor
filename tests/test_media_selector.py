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


from stock.selector import (
    MediaSelector
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("MEDIA SELECTOR TEST")
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


ranked = (
    scene["stock"]
    .get(
        "visual_ranking",
        []
    )
)


if not ranked:

    raise RuntimeError(
        "No visual ranking found. "
        "Run test_visual_ranker.py first."
    )


# ==================================================
# SELECTOR
# ==================================================

selector = MediaSelector(

    auto_threshold=0.85,

    margin_threshold=0.08,

    minimum_threshold=0.75
)


decision = selector.decide(
    ranked
)


# ==================================================
# DISPLAY
# ==================================================

print()

print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Best candidate:",
    ranked[0]["media_id"]
)

print(
    "Best score:",
    decision["best_score"]
)

print(
    "Second score:",
    decision["second_score"]
)

print(
    "Margin:",
    decision["margin"]
)


print()
print("=" * 70)
print("SELECTION DECISION")
print("=" * 70)

print()

print(
    "Decision:",
    decision["decision"]
)

print(
    "Reason:",
    decision["reason"]
)


# ==================================================
# UPDATE MANIFEST
# ==================================================

scene[
    "stock"
][
    "selection"
] = {

    "decision": (
        decision["decision"]
    ),

    "best_score": (
        decision["best_score"]
    ),

    "second_score": (
        decision["second_score"]
    ),

    "margin": (
        decision["margin"]
    ),

    "reason": (
        decision["reason"]
    )
}


if (
    decision["decision"]
    == "auto_selected"
):

    scene[
        "stock"
    ][
        "selected_media"
    ] = decision[
        "selected"
    ]


    scene[
        "stock"
    ][
        "status"
    ] = "selected"


elif (
    decision["decision"]
    == "needs_review"
):

    scene[
        "stock"
    ][
        "selected_media"
    ] = None


    scene[
        "stock"
    ][
        "status"
    ] = "needs_review"


else:

    scene[
        "stock"
    ][
        "selected_media"
    ] = None


    scene[
        "stock"
    ][
        "status"
    ] = "search_again"


# ==================================================
# SAVE
# ==================================================

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
print("MEDIA SELECTOR TEST SUCCESS")
print("=" * 70)

print(
    "Manifest status:",
    scene[
        "stock"
    ][
        "status"
    ]
)