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


from stock.pexels import (
    PexelsProvider
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("PEXELS STOCK PROVIDER TEST")
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


query = scene[
    "search"
][
    "primary_keyword"
]


print()
print(
    "Scene:",
    scene["scene_id"]
)

print(
    "AI keyword:",
    query
)


# ==================================================
# PEXELS
# ==================================================

provider = PexelsProvider()


print()
print(
    "Searching Pexels videos..."
)


results = provider.search_videos(

    query=query,

    per_page=10
)


print()
print("=" * 70)
print("PEXELS RESULTS")
print("=" * 70)


print()
print(
    "Results:",
    len(results)
)


for index, item in enumerate(
    results,
    start=1
):

    print()
    print(
        f"{index}. "
        f"{item.media_id}"
    )

    print(
        "   Type:",
        item.media_type
    )

    print(
        "   Resolution:",
        f"{item.width}x{item.height}"
    )

    print(
        "   Duration:",
        item.duration
    )

    print(
        "   Creator:",
        item.photographer
    )

    print(
        "   Source:",
        item.source_url
    )


# ==================================================
# SAVE CANDIDATES
# ==================================================

output_path = (
    ROOT
    / "projects"
    / "pexels_test_results.json"
)


with open(
    output_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(

        {
            "scene_id": (
                scene["scene_id"]
            ),

            "query": query,

            "provider": (
                provider.name
            ),

            "result_count": (
                len(results)
            ),

            "results": [

                item.to_dict()

                for item in results
            ]
        },

        file,

        indent=4,

        ensure_ascii=False
    )


print()
print("=" * 70)


if results:

    print(
        "PEXELS PROVIDER TEST SUCCESS"
    )

else:

    print(
        "PEXELS CONNECTION WORKED, "
        "BUT NO RESULTS FOUND"
    )


print("=" * 70)


print(
    "Saved:",
    output_path
)