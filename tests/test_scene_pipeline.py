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


from pipeline.scene_pipeline import (
    ScenePipeline
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("SCENE PIPELINE TEST")
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


print()
print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Narration:",
    scene["dialogue"]
)


# ==================================================
# RUN PIPELINE
# ==================================================

pipeline = ScenePipeline(
    download_dir=(
        ROOT
        / "media"
        / "downloads"
    ),
    review_mode="auto"
)


result = pipeline.run(
    scene
)


# ==================================================
# SAVE MANIFEST
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
print("PIPELINE RESULT")
print("=" * 70)


for key, value in result.items():

    if key not in (
        "selected_media",
        "download",
        "validation",
        "decision"
    ):

        print(
            f"{key}: {value}"
        )


print()
print(
    "Manifest status:",
    scene["stock"]["status"]
)

print(
    "Manifest saved:",
    manifest_path
)