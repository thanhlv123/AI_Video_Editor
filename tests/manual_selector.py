from pathlib import Path
import sys
import json


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)


from stock.manual_selector import (
    ManualSelector,
    ManualSelectorError
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("MANUAL MEDIA SELECTION")
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

    manifest = json.load(file)


scene = manifest["scenes"][0]

stock = scene["stock"]

ranked = stock.get(
    "visual_ranking",
    []
)


if not ranked:
    raise RuntimeError(
        "No visual ranking available."
    )


# ==================================================
# DISPLAY TOP 3
# ==================================================

review_candidates = ranked[:3]


print()
print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Narration:",
    scene.get(
        "dialogue",
        ""
    )
)

print()
print("=" * 70)
print("TOP 3 CANDIDATES")
print("=" * 70)


for index, item in enumerate(
    review_candidates,
    start=1
):

    print()

    print(
        f"[{index}] "
        f"{item['provider']} / "
        f"{item['media_id']}"
    )

    print(
        "    Final score:",
        item.get(
            "final_score"
        )
    )

    print(
        "    Visual score:",
        item.get(
            "visual_score"
        )
    )

    print(
        "    Duration:",
        item.get(
            "duration"
        )
    )

    print(
        "    Resolution:",
        f"{item.get('width')}x"
        f"{item.get('height')}"
    )

    print(
        "    Reason:",
        item.get(
            "visual_reason"
        )
    )

    print(
        "    Source:",
        item.get(
            "source_url"
        )
    )


# ==================================================
# USER CHOICE
# ==================================================

print()
print("=" * 70)

choice = input(
    "Choose candidate [1-3]: "
)


selector = ManualSelector()


try:

    selected = selector.select(
        review_candidates,
        choice
    )

except ManualSelectorError as error:

    print()
    print(
        "SELECTION ERROR:",
        error
    )

    raise SystemExit(1)


# ==================================================
# UPDATE MANIFEST
# ==================================================

stock[
    "selected_media"
] = selected


stock[
    "status"
] = "selected"


previous_selection = stock.get(
    "selection",
    {}
)


stock[
    "selection"
] = {

    "decision": (
        "manual_selected"
    ),

    "selected_media_id": (
        selected["media_id"]
    ),

    "final_score": (
        selected.get(
            "final_score"
        )
    ),

    "previous_decision": (
        previous_selection.get(
            "decision"
        )
    )
}


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


# ==================================================
# RESULT
# ==================================================

print()
print("=" * 70)
print("MANUAL SELECTION SUCCESS")
print("=" * 70)

print(
    "Selected:",
    selected["media_id"]
)

print(
    "Provider:",
    selected["provider"]
)

print(
    "Final score:",
    selected.get(
        "final_score"
    )
)

print(
    "Status:",
    stock["status"]
)

print(
    "Manifest:",
    manifest_path
)