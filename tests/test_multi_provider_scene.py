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
    str(ROOT)
)


from config.api_key_manager import APIKeyManager
from stock.pexels import PexelsProvider
from stock.pixabay import PixabayProvider
from stock.search_manager import StockSearchManager


# ==================================================
# HELPER
# Supports both dict and object candidate formats.
# ==================================================

def get_field(
    item,
    *names,
    default=None,
):

    if isinstance(
        item,
        dict,
    ):

        for name in names:

            if name in item:

                return item.get(
                    name,
                    default,
                )

        return default


    for name in names:

        if hasattr(
            item,
            name,
        ):

            return getattr(
                item,
                name,
            )


    return default


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

    os.environ[
        key
    ] = value


# ==================================================
# CHECK KEYS
# ==================================================

print("=" * 70)
print("MULTI PROVIDER STOCK SMOKE TEST V2")
print("=" * 70)

print(
    "KIE:",
    bool(
        os.getenv(
            "KIE_API_KEY"
        )
    ),
)

print(
    "PEXELS:",
    bool(
        os.getenv(
            "PEXELS_API_KEY"
        )
    ),
)

print(
    "PIXABAY:",
    bool(
        os.getenv(
            "PIXABAY_API_KEY"
        )
    ),
)


if not os.getenv(
    "PEXELS_API_KEY"
):

    raise RuntimeError(
        "PEXELS_API_KEY missing."
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


print()

print(
    "Providers:",
    [
        provider.name
        for provider
        in providers
    ],
)


# ==================================================
# SEARCH MANAGER
#
# IMPORTANT:
# 40 candidates = enough room for both providers.
# ==================================================

search_manager = (
    StockSearchManager(

        providers=providers,

        per_query=5,

        max_candidates=40,
    )
)


# ==================================================
# TEST SCENE
# ==================================================

scene = {

    "scene_id":
        "test_scene_001",

    "start":
        0.0,

    "end":
        6.0,

    "duration":
        6.0,

    "dialogue":
        (
            "A person walks peacefully "
            "toward the morning sunlight."
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

            "person walking toward sunlight",

            "walking morning sunlight",

            "hopeful person outdoors",
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
# SEARCH
# ==================================================

results = (
    search_manager.search_scene(
        scene
    )
)


# ==================================================
# RESULT SUMMARY
# ==================================================

print()
print("=" * 70)
print("RESULTS")
print("=" * 70)

print(
    "Candidate data type:",
    (
        type(results[0]).__name__
        if results
        else "none"
    ),
)

print(
    "Total:",
    len(results)
)


counts = {}


for item in results:

    source = get_field(

        item,

        "source",

        "provider",

        default="unknown",
    )


    source = str(
        source
        or "unknown"
    ).lower()


    counts[source] = (

        counts.get(
            source,
            0,
        )
        + 1
    )


print(
    "By provider:",
    counts
)


# ==================================================
# PRINT SAMPLE RESULTS
# ==================================================

for index, item in enumerate(
    results[:20],
    start=1,
):

    source = get_field(

        item,

        "source",

        "provider",

        default="unknown",
    )


    media_id = get_field(

        item,

        "id",

        "media_id",

        default="unknown",
    )


    media_type = get_field(

        item,

        "type",

        "media_type",

        default="unknown",
    )


    duration = get_field(

        item,

        "duration",

        default=0,
    )


    width = get_field(

        item,

        "width",

        default=0,
    )


    height = get_field(

        item,

        "height",

        default=0,
    )


    print()

    print(
        f"[{index}]"
    )

    print(
        "Provider:",
        source
    )

    print(
        "ID:",
        media_id
    )

    print(
        "Type:",
        media_type
    )

    print(
        "Duration:",
        duration
    )

    print(
        "Resolution:",
        f"{width}x{height}"
    )


# ==================================================
# PASS / FAIL
# ==================================================

pexels_count = (
    counts.get(
        "pexels",
        0,
    )
)

pixabay_count = (
    counts.get(
        "pixabay",
        0,
    )
)


print()
print("=" * 70)

print(
    "PEXELS CANDIDATES:",
    pexels_count
)

print(
    "PIXABAY CANDIDATES:",
    pixabay_count
)


if (
    pexels_count > 0
    and pixabay_count > 0
):

    print()
    print(
        "MULTI PROVIDER SEARCH: PASS"
    )

else:

    print()
    print(
        "MULTI PROVIDER SEARCH: FAIL"
    )


print("=" * 70)