from pathlib import Path
import sys


ROOT = Path(
    __file__
).resolve().parent.parent


sys.path.insert(
    0,
    str(ROOT)
)


from pipeline.batch_pipeline import (
    BatchPipeline
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("BATCH PIPELINE TEST")
print("=" * 70)


manifest_path = (
    ROOT
    / "projects"
    / "analysis_manifest.json"
)


download_dir = (
    ROOT
    / "media"
    / "downloads"
)


pipeline = BatchPipeline(

    manifest_path=manifest_path,

    download_dir=download_dir,

    review_mode="auto",

    resume=True,

    visual_top_n=10
)


summary = pipeline.run()


print()
print("=" * 70)
print("TEST RESULT")
print("=" * 70)

print(
    "Total:",
    summary["total"]
)

print(
    "Validated:",
    summary["validated"]
)

print(
    "Skipped:",
    summary["skipped"]
)

print(
    "Needs review:",
    summary["needs_review"]
)

print(
    "Search again:",
    summary["search_again"]
)

print(
    "Failed:",
    summary["failed"]
)