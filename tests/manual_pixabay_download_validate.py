from pathlib import Path
import os
import sys


ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

sys.path.insert(
    0,
    str(ROOT),
)


from config.api_key_manager import APIKeyManager

from stock.pexels import PexelsProvider
from stock.pixabay import PixabayProvider

from stock.balanced_search_manager import (
    BalancedStockSearchManager,
)

from stock.ranker import MediaRanker

from stock.downloader import (
    DownloadManager,
    DownloadError,
)

from stock.validator import (
    MediaValidator,
    MediaValidationError,
)


# ==================================================
# LOAD API KEYS
# ==================================================

manager = APIKeyManager(
    ROOT
)

runtime = (
    manager.runtime_environment()
)

for key, value in runtime.items():
    os.environ[key] = value


print("=" * 70)
print("PIXABAY DOWNLOAD + VALIDATION TEST")
print("=" * 70)

print(
    "PEXELS:",
    bool(os.getenv("PEXELS_API_KEY")),
)

print(
    "PIXABAY:",
    bool(os.getenv("PIXABAY_API_KEY")),
)


if not os.getenv(
    "PIXABAY_API_KEY"
):
    raise RuntimeError(
        "PIXABAY_API_KEY missing."
    )


# ==================================================
# PROVIDERS
# ==================================================

providers = [
    PexelsProvider(),
    PixabayProvider(),
]


search_manager = (
    BalancedStockSearchManager(
        providers=providers,
        per_query=5,
        max_candidates=20,
    )
)


# ==================================================
# TEST SCENE
# ==================================================

scene = {

    "scene_id":
        "pixabay_test_001",

    "start":
        0.0,

    "end":
        6.0,

    "duration":
        6.0,

    "dialogue":
        (
            "A person walks toward "
            "the warm morning sunlight."
        ),

    "analysis": {

        "context":
            "hopeful outdoor scene",

        "subject":
            "person walking",

        "action":
            "walking forward",

        "location":
            "outdoors",

        "mood":
            "hopeful",

        "shot":
            "medium wide",

        "motion":
            "slow walking",
    },

    "search": {

        "primary_keyword":
            "person walking sunlight",

        "keywords": [
            "person walking outdoors",
            "walking morning sunlight",
            "person walking nature",
        ],

        "avoid":
            [],
    },

    "stock": {

        "status":
            "pending",

        "preferred_type":
            "video",

        "searches":
            [],

        "candidates":
            [],

        "selected_media":
            None,
    },
}


# ==================================================
# 1. BALANCED SEARCH
# ==================================================

print()
print("=" * 70)
print("[1/4] BALANCED SEARCH")
print("=" * 70)


candidates = (
    search_manager.search_scene(
        scene
    )
)


print()
print(
    "Total candidates:",
    len(candidates),
)


counts = {}


for item in candidates:

    provider = (
        item.get("provider")
        or item.get("source")
        or "unknown"
    )

    provider = str(
        provider
    ).lower()

    counts[provider] = (
        counts.get(
            provider,
            0,
        )
        + 1
    )


print(
    "By provider:",
    counts,
)


if counts.get(
    "pixabay",
    0,
) <= 0:

    raise RuntimeError(
        "No Pixabay candidates."
    )


# ==================================================
# 2. LOCAL RANKING
# ==================================================

print()
print("=" * 70)
print("[2/4] LOCAL RANKING")
print("=" * 70)


ranker = MediaRanker(
    target_width=1920,
    target_height=1080,
)


ranked = ranker.rank(
    scene=scene,
    candidates=candidates,
)


print(
    "Ranked candidates:",
    len(ranked),
)


if not ranked:

    raise RuntimeError(
        "MediaRanker returned no candidates."
    )


# ==================================================
# FIND BEST PIXABAY CANDIDATE
# ==================================================

pixabay_candidates = []


for item in ranked:

    provider = (
        item.get("provider")
        or item.get("source")
        or ""
    )

    if (
        str(provider).lower()
        == "pixabay"
    ):

        pixabay_candidates.append(
            item
        )


if not pixabay_candidates:

    raise RuntimeError(
        "Pixabay disappeared after ranking."
    )


selected = dict(
    pixabay_candidates[0]
)


# ==================================================
# NORMALIZE FIELD NAMES
#
# This also makes the test robust if the search
# provider uses source/id/type aliases.
# ==================================================

selected["provider"] = (
    selected.get("provider")
    or selected.get("source")
    or "pixabay"
)

selected["media_id"] = (
    selected.get("media_id")
    or selected.get("id")
)

selected["media_type"] = (
    selected.get("media_type")
    or selected.get("type")
    or "video"
)


print()
print(
    "Selected provider:",
    selected.get("provider"),
)

print(
    "Selected media ID:",
    selected.get("media_id"),
)

print(
    "Media type:",
    selected.get("media_type"),
)

print(
    "Provider duration:",
    selected.get("duration"),
)

print(
    "Resolution:",
    (
        f"{selected.get('width')}x"
        f"{selected.get('height')}"
    ),
)

print(
    "Local score:",
    selected.get("score"),
)


if not selected.get(
    "download_url"
):

    raise RuntimeError(
        "Selected Pixabay candidate "
        "has no download_url."
    )


# ==================================================
# 3. DOWNLOAD
# ==================================================

print()
print("=" * 70)
print("[3/4] DOWNLOAD PIXABAY VIDEO")
print("=" * 70)


download_dir = (
    ROOT
    / "media"
    / "downloads"
    / "pixabay_provider_test"
)


download_dir.mkdir(
    parents=True,
    exist_ok=True,
)


downloader = DownloadManager(
    output_dir=download_dir,
)


try:

    download_result = (
        downloader.download(
            media=selected,
            scene_id="pixabay_test_001",
        )
    )

except DownloadError as error:

    raise RuntimeError(
        f"Pixabay download failed: {error}"
    )


print(
    "Download status:",
    download_result.get(
        "status"
    ),
)

print(
    "Filename:",
    download_result.get(
        "filename"
    ),
)

print(
    "Path:",
    download_result.get(
        "path"
    ),
)

print(
    "Size:",
    download_result.get(
        "size"
    ),
)


download_path = Path(
    download_result[
        "path"
    ]
)


if not download_path.exists():

    raise RuntimeError(
        "Downloaded file does not exist."
    )


if download_path.stat().st_size <= 0:

    raise RuntimeError(
        "Downloaded file is empty."
    )


# ==================================================
# 4. FFPROBE VALIDATION
# ==================================================

print()
print("=" * 70)
print("[4/4] FFPROBE VALIDATION")
print("=" * 70)


validator = MediaValidator()


try:

    validation = (
        validator.validate(
            file_path=
                download_result[
                    "path"
                ],

            expected_type=
                selected.get(
                    "media_type"
                ),
        )
    )

except MediaValidationError as error:

    raise RuntimeError(
        f"Validation failed: {error}"
    )


print(
    "Validated:",
    validation.get(
        "valid"
    ),
)

print(
    "Duration:",
    validation.get(
        "duration"
    ),
)

print(
    "Resolution:",
    (
        f"{validation.get('width')}x"
        f"{validation.get('height')}"
    ),
)

print(
    "FPS:",
    validation.get(
        "fps"
    ),
)


# ==================================================
# FINAL CHECKS
# ==================================================

if not validation.get(
    "valid"
):

    raise RuntimeError(
        "Validator returned valid=False."
    )


if float(
    validation.get(
        "duration",
        0,
    )
    or 0
) <= 0:

    raise RuntimeError(
        "Invalid video duration."
    )


filename = str(
    download_result.get(
        "filename",
        ""
    )
).lower()


print()
print("=" * 70)


if "pixabay" in filename:

    print(
        "FILENAME PROVIDER TAG: PASS"
    )

else:

    print(
        "FILENAME PROVIDER TAG: WARNING"
    )

    print(
        "Current filename:",
        filename,
    )


print()
print(
    "PIXABAY DOWNLOAD: PASS"
)

print(
    "PIXABAY FFPROBE VALIDATION: PASS"
)

print()
print(
    "PIXABAY PROVIDER END-TO-END: PASS"
)

print("=" * 70)