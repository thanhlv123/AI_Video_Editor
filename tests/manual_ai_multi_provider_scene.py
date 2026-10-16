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
from pipeline.scene_pipeline import ScenePipeline


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
print("AI MULTI-PROVIDER SCENE TEST")
print("=" * 70)

print(
    "KIE:",
    bool(os.getenv("KIE_API_KEY"))
)

print(
    "PEXELS:",
    bool(os.getenv("PEXELS_API_KEY"))
)

print(
    "PIXABAY:",
    bool(os.getenv("PIXABAY_API_KEY"))
)


if not os.getenv("KIE_API_KEY"):
    raise RuntimeError(
        "KIE_API_KEY missing."
    )

if not os.getenv("PEXELS_API_KEY"):
    raise RuntimeError(
        "PEXELS_API_KEY missing."
    )

if not os.getenv("PIXABAY_API_KEY"):
    raise RuntimeError(
        "PIXABAY_API_KEY missing."
    )


# ==================================================
# OUTPUT DIRECTORY
# ==================================================

download_dir = (
    ROOT
    / "media"
    / "downloads"
    / "ai_multi_provider_test"
)

download_dir.mkdir(
    parents=True,
    exist_ok=True,
)


# ==================================================
# CREATE PIPELINE
# ==================================================

pipeline = ScenePipeline(

    download_dir=download_dir,

    per_query=5,

    max_candidates=20,

    visual_top_n=10,

    review_mode="auto",
)


print()
print(
    "Search manager:",
    type(
        pipeline.search_manager
    ).__name__,
)

print(
    "Providers:",
    [
        provider.name
        for provider
        in pipeline.search_manager.providers
    ],
)


# ==================================================
# TEST SCENE
# ==================================================

scene = {

    "scene_id":
        "ai_multi_test_001",

    "start":
        0.0,

    "end":
        7.0,

    "duration":
        7.0,

    "dialogue":
        (
            "After a difficult journey, "
            "a person walks toward the warm "
            "morning light with renewed hope."
        ),

    "analysis": {

        "context":
            "hope after hardship",

        "subject":
            "single person",

        "action":
            "walking toward sunlight",

        "location":
            "outdoors",

        "mood":
            "hopeful and emotional",

        "shot":
            "wide cinematic shot",

        "motion":
            "slow forward walking",
    },

    "search": {

        "primary_keyword":
            "person walking toward sunlight",

        "keywords": [

            "silhouette walking toward light",

            "person walking sunrise",

            "hopeful person outdoors",

            "walking into morning light",

            "person overcoming hardship",
        ],

        "avoid": [
            "text",
            "logo",
            "watermark",
        ],
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
# RUN COMPLETE SCENE PIPELINE
# ==================================================

print()
print("=" * 70)
print("RUNNING COMPLETE SCENE PIPELINE")
print("=" * 70)


result = pipeline.run(
    scene
)


# ==================================================
# RESULT
# ==================================================

print()
print("=" * 70)
print("FINAL RESULT")
print("=" * 70)


print(
    "Success:",
    result.get("success")
)

print(
    "Status:",
    result.get("status")
)


selected = (
    result.get("selected_media")
    or scene.get(
        "stock",
        {}
    ).get(
        "selected_media"
    )
    or {}
)


print()
print(
    "Selected provider:",
    selected.get("provider")
)

print(
    "Selected media ID:",
    selected.get("media_id")
)

print(
    "Final score:",
    selected.get("final_score")
)

print(
    "Local score:",
    selected.get("score")
)


download = (
    result.get("download")
    or scene.get(
        "stock",
        {}
    ).get(
        "download",
        {}
    )
)


if download:

    print()
    print(
        "Downloaded file:",
        download.get("filename")
    )

    print(
        "Downloaded path:",
        download.get("path")
    )

    print(
        "Downloaded size:",
        download.get("size")
    )


validation = (
    result.get("validation")
    or scene.get(
        "stock",
        {}
    ).get(
        "validation",
        {}
    )
)


if validation:

    print()
    print(
        "Validated:",
        validation.get("valid")
    )

    print(
        "Duration:",
        validation.get("duration")
    )

    print(
        "Resolution:",
        (
            f"{validation.get('width')}x"
            f"{validation.get('height')}"
        )
    )

    print(
        "FPS:",
        validation.get("fps")
    )


# ==================================================
# CHECK PROVIDER
# ==================================================

provider = str(
    selected.get(
        "provider",
        ""
    )
).lower()


print()
print("=" * 70)


if (
    result.get("success")
    and result.get("status")
    == "validated"
    and provider
    in (
        "pexels",
        "pixabay",
    )
):

    print(
        "AI MULTI-PROVIDER SELECTION: PASS"
    )

    print(
        f"AI selected: {provider}"
    )

else:

    print(
        "AI MULTI-PROVIDER SELECTION: FAIL"
    )


print("=" * 70)