from pathlib import Path
import sys
import json


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)


from stock.pexels import PexelsProvider
from stock.search_manager import StockSearchManager


print("=" * 70)
print("AI VIDEO EDITOR")
print("STOCK SEARCH MANAGER TEST")
print("=" * 70)


# ==================================================
# LOAD MANIFEST
# ==================================================

manifest_path = (
    ROOT
    / "projects"
    / "analysis_manifest.json"
)


if not manifest_path.exists():

    raise FileNotFoundError(
        f"Manifest not found: {manifest_path}"
    )


with open(
    manifest_path,
    "r",
    encoding="utf-8"
) as file:

    manifest = json.load(file)


if not manifest.get("scenes"):

    raise RuntimeError(
        "Manifest contains no scenes."
    )


scene = manifest["scenes"][0]


print()
print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Primary:",
    scene["search"]["primary_keyword"]
)

print(
    "Preferred type:",
    scene["stock"].get(
        "preferred_type",
        "video"
    )
)


# ==================================================
# PROVIDER
# ==================================================

pexels = PexelsProvider()


manager = StockSearchManager(

    providers=[
        pexels
    ],

    per_query=5,

    max_candidates=20
)


# ==================================================
# SEARCH
# ==================================================

print()
print("=" * 70)
print("SEARCHING")
print("=" * 70)
print()


candidates = manager.search_scene(
    scene
)


# ==================================================
# RESULTS
# ==================================================

print()
print("=" * 70)
print("CANDIDATE POOL")
print("=" * 70)

print()
print(
    "Unique candidates:",
    len(candidates)
)


for index, item in enumerate(
    candidates[:10],
    start=1
):

    print()

    print(
        f"{index}. "
        f"{item['provider']} / "
        f"{item['media_id']}"
    )

    print(
        "   Query:",
        item.get(
            "matched_query"
        )
    )

    print(
        "   Type:",
        item.get(
            "media_type"
        )
    )

    print(
        "   Resolution:",
        f"{item.get('width')}x"
        f"{item.get('height')}"
    )

    print(
        "   Duration:",
        item.get(
            "duration"
        )
    )

    print(
        "   Creator:",
        item.get(
            "photographer"
        )
    )

    print(
        "   Title:",
        item.get(
            "title"
        )
    )


# ==================================================
# SAVE UPDATED MANIFEST
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
print("STOCK SEARCH MANAGER TEST SUCCESS")
print("=" * 70)

print(
    "Status:",
    scene["stock"]["status"]
)

print(
    "Candidates:",
    len(
        scene["stock"]["candidates"]
    )
)

print(
    "Manifest updated:",
    manifest_path
)