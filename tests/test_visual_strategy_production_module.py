from pathlib import Path
import json
import sys


ROOT = Path(
    r"D:\YouTubeTools\AI_Video_Editor"
)

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from pipeline.context_geo import (
    enrich_manifest_with_project_context,
)

from pipeline.visual_strategy import (
    enrich_manifest_with_visual_strategy,
)


MANIFEST = (
    ROOT
    / "projects"
    / "runs"
    / "file_chay_thu_01_1356b5b5"
    / "ai_manifest.json"
)


with open(
    MANIFEST,
    "r",
    encoding="utf-8",
) as file:

    manifest = json.load(
        file
    )


manifest = (
    enrich_manifest_with_project_context(
        manifest
    )
)


manifest = (
    enrich_manifest_with_visual_strategy(
        manifest,
        activate_search=False,
    )
)


expected = {
    "scene_001": "VISUAL_PROXY",
    "scene_002": "STRICT",
    "scene_003": "VISUAL_PROXY",
    "scene_004": "VISUAL_PROXY",
    "scene_005": "STRICT",
    "scene_006": "REGIONAL_PROXY",
    "scene_007": "VISUAL_PROXY",
    "scene_008": "REGIONAL_PROXY",
    "scene_009": "VISUAL_PROXY",
    "scene_010": "REGIONAL_PROXY",
    "scene_011": "REGIONAL_PROXY",
}


passed = 0


for scene in manifest.get(
    "scenes",
    [],
):

    scene_id = scene.get(
        "scene_id"
    )

    if scene_id not in expected:
        continue

    strategy = scene.get(
        "visual_strategy",
        {},
    )

    actual = strategy.get(
        "geo_policy"
    )

    wanted = expected[
        scene_id
    ]

    ok = (
        actual == wanted
    )

    if ok:
        passed += 1

    print(
        scene_id,
        actual,
        "->",
        "PASS"
        if ok
        else
        "FAIL",
    )

    print(
        "  queries:",
        len(
            strategy.get(
                "search_queries",
                []
            )
        ),
    )


print()

print(
    "Policy checks:",
    f"{passed}/11",
)


if passed == 11:

    print(
        "PRODUCTION VISUAL STRATEGY MODULE: PASS"
    )

else:

    print(
        "PRODUCTION VISUAL STRATEGY MODULE: REVIEW REQUIRED"
    )


print(
    "Search behavior was NOT activated."
)