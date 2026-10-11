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


from stock.visual_ranker import (
    VisualRanker
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("AI VISUAL RANKER TEST")
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


if not candidates:

    raise RuntimeError(
        "No ranked candidates found."
    )


print()
print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Narration:",
    scene["dialogue"]
)

print(
    "Candidates available:",
    len(candidates)
)


# ==================================================
# ONLY TOP 5
# ==================================================

top_candidates = candidates[
    :5
]


print()
print("=" * 70)
print("SENDING TOP 5 TO KIE")
print("=" * 70)


for index, item in enumerate(
    top_candidates,
    start=1
):

    print()

    print(
        f"{index}. "
        f"{item['media_id']}"
    )

    print(
        "   Local score:",
        item.get(
            "score"
        )
    )

    print(
        "   Thumbnail:",
        item.get(
            "thumbnail_url"
        )
    )


# ==================================================
# VISUAL RANKER
# ==================================================

ranker = VisualRanker(

    model="gpt-6-luna",

    reasoning_effort="low",

    local_weight=0.30,

    visual_weight=0.70
)


print()
print(
    "Calling Kie visual model..."
)


ranked = ranker.rank(

    scene=scene,

    candidates=top_candidates,

    top_n=5
)


# ==================================================
# RESULTS
# ==================================================

print()
print("=" * 70)
print("AI VISUAL RANKING")
print("=" * 70)


for index, item in enumerate(
    ranked,
    start=1
):

    print()

    print(
        f"{index}. "
        f"{item['provider']} / "
        f"{item['media_id']}"
    )

    print(
        "   Local:",
        item[
            "local_score"
        ]
    )

    print(
        "   Visual:",
        item[
            "visual_score"
        ]
    )

    print(
        "   FINAL:",
        item[
            "final_score"
        ]
    )

    print(
        "   Reason:",
        item[
            "visual_reason"
        ]
    )


# ==================================================
# SAVE VISUAL RANKING
# ==================================================

scene[
    "stock"
][
    "visual_ranking"
] = ranked


scene[
    "stock"
][
    "status"
] = "visual_ranked"


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
print("AI VISUAL RANKER TEST SUCCESS")
print("=" * 70)


print(
    "Best candidate:",
    ranked[0][
        "media_id"
    ]
)

print(
    "Final score:",
    ranked[0][
        "final_score"
    ]
)

print(
    "Status:",
    scene[
        "stock"
    ][
        "status"
    ]
)