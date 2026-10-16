from pathlib import Path
from copy import deepcopy
import json
import sys


# ==================================================
# PROJECT ROOT
# ==================================================

ROOT = Path(
    r"D:\YouTubeTools\AI_Video_Editor"
)


# Make project imports available when this script
# is executed from the tests folder.
if str(ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(ROOT),
    )


# ==================================================
# PROJECT IMPORTS
# ==================================================

from pipeline.context_geo import (
    enrich_manifest_with_project_context,
    filter_geography_candidates,
)


# ==================================================
# MANIFEST
# ==================================================

MANIFEST = (
    ROOT
    / "projects"
    / "runs"
    / "1006_129e62dc"
    / "speech_stock_manifest.json"
)


print("=" * 78)
print("OFFLINE CONTEXT + GEOGRAPHY TEST")
print("=" * 78)

print()

print(
    "Manifest:"
)

print(
    MANIFEST
)


# ==================================================
# VERIFY MANIFEST
# ==================================================

if not MANIFEST.exists():

    raise FileNotFoundError(
        MANIFEST
    )


# ==================================================
# LOAD ORIGINAL MANIFEST
#
# IMPORTANT:
# This file is READ ONLY.
# We work on a deepcopy below.
# ==================================================

with open(
    MANIFEST,
    "r",
    encoding="utf-8",
) as file:

    original = json.load(
        file
    )


manifest = deepcopy(
    original
)


# ==================================================
# SAVE ORIGINAL LOCATIONS
# ==================================================

old_locations = {}


for scene in manifest.get(
    "scenes",
    [],
):

    scene_id = scene.get(
        "scene_id"
    )

    old_locations[
        scene_id
    ] = (
        scene.get(
            "analysis",
            {},
        ).get(
            "location",
            "",
        )
    )


# ==================================================
# APPLY CONTEXT CARRYOVER
# ==================================================

manifest = (
    enrich_manifest_with_project_context(
        manifest
    )
)


project_context = (
    manifest.get(
        "project_context",
        {},
    )
)


print()

print("=" * 78)
print("PROJECT CONTEXT")
print("=" * 78)


print(
    "Required country:",
    project_context.get(
        "required_country"
    ),
)


print(
    "Country key:",
    project_context.get(
        "required_country_key"
    ),
)


required_country = (
    project_context.get(
        "required_country_key"
    )
)


# ==================================================
# COUNTRY MUST BE ESTABLISHED
# ==================================================

if not required_country:

    print()

    print("=" * 78)

    print(
        "RESULT: PROJECT COUNTRY NOT ESTABLISHED"
    )

    print("=" * 78)

    print()

    print(
        "Stop here and send this output."
    )

    raise SystemExit(
        2
    )


# ==================================================
# TEST ALL SCENES
# ==================================================

total_candidates = 0

total_rejected = 0

scenes_with_rejections = 0

selected_rejected = []

carryover_count = 0


important_scenes = {

    "scene_008",
    "scene_009",
    "scene_010",
    "scene_011",
    "scene_013",
    "scene_014",
    "scene_015",
    "scene_018",
    "scene_019",
    "scene_021",
}


for scene in manifest.get(
    "scenes",
    [],
):

    scene_id = scene.get(
        "scene_id",
        "unknown",
    )


    stock = scene.get(
        "stock",
        {},
    )


    candidates = stock.get(
        "candidates",
        [],
    )


    selected = (
        stock.get(
            "selected_media"
        )
        or {}
    )


    selected_id = str(
        selected.get(
            "media_id",
            "",
        )
    )


    (
        kept,
        rejected,
        bypassed,
    ) = filter_geography_candidates(
        scene,
        candidates,
    )


    # ----------------------------------------------
    # COUNTERS
    # ----------------------------------------------

    total_candidates += len(
        candidates
    )


    total_rejected += len(
        rejected
    )


    if scene.get(
        "context_carryover"
    ):

        carryover_count += 1


    if rejected:

        scenes_with_rejections += 1


    # ----------------------------------------------
    # WAS SELECTED MEDIA REJECTED?
    # ----------------------------------------------

    rejected_ids = {

        str(
            item.get(
                "media_id",
                "",
            )
        )

        for item
        in rejected
    }


    selected_was_rejected = (

        bool(
            selected_id
        )

        and

        selected_id
        in rejected_ids
    )


    if selected_was_rejected:

        selected_rejected.append(
            scene_id
        )


    # ----------------------------------------------
    # DISPLAY IMPORTANT SCENES
    # ----------------------------------------------

    if (
        rejected
        or
        scene_id in important_scenes
    ):

        print()

        print(
            "-" * 78
        )


        print(
            "SCENE:",
            scene_id,
        )


        print(
            "Dialogue:",
            scene.get(
                "dialogue",
                "",
            ),
        )


        print(
            "Original location:",
            old_locations.get(
                scene_id,
                "",
            ),
        )


        print(
            "New location:",
            scene.get(
                "analysis",
                {},
            ).get(
                "location",
                "",
            ),
        )


        print(
            "Project country:",
            scene.get(
                "project_context",
                {},
            ).get(
                "required_country"
            ),
        )


        print(
            "Original primary query:",
            scene.get(
                "search",
                {},
            ).get(
                "original_primary_keyword",
                "",
            ),
        )


        print(
            "New primary query:",
            scene.get(
                "search",
                {},
            ).get(
                "primary_keyword",
                "",
            ),
        )


        print(
            "Candidates:",
            len(
                candidates
            ),
        )


        print(
            "Kept:",
            len(
                kept
            ),
        )


        print(
            "Rejected:",
            len(
                rejected
            ),
        )


        print(
            "Safety bypass:",
            bypassed,
        )


        print(
            "Selected media:",
            selected_id
            or
            "NONE",
        )


        print(
            "Selected rejected:",
            selected_was_rejected,
        )


        # ------------------------------------------
        # REJECTED LIST
        # ------------------------------------------

        if rejected:

            print()

            print(
                "Rejected candidates:"
            )


            for item in rejected:

                print(
                    "  -",
                    item.get(
                        "provider"
                    ),
                    item.get(
                        "media_id"
                    ),
                    "| countries:",
                    item.get(
                        "detected_countries"
                    ),
                    "|",
                    str(
                        item.get(
                            "title",
                            "",
                        )
                    )[:120],
                )


# ==================================================
# SUMMARY
# ==================================================

print()

print("=" * 78)
print("SUMMARY")
print("=" * 78)


print(
    "Project country:",
    project_context.get(
        "required_country"
    ),
)


print(
    "Scenes:",
    len(
        manifest.get(
            "scenes",
            [],
        )
    ),
)


print(
    "Context carryover scenes:",
    carryover_count,
)


print(
    "Total candidates:",
    total_candidates,
)


print(
    "Rejected candidates:",
    total_rejected,
)


print(
    "Scenes with geography rejection:",
    scenes_with_rejections,
)


print(
    "Selected media rejected:",
    len(
        selected_rejected
    ),
)


print(
    "Selected rejected scene IDs:",
    selected_rejected,
)


# ==================================================
# KNOWN WRONG-GEOGRAPHY CASES
# ==================================================

known_bad = {

    "scene_008":
        "8698",

    "scene_009":
        "36844981",

    "scene_010":
        "206315",

    "scene_011":
        "33643211",

    "scene_013":
        "223273",

    "scene_015":
        "198477",

    "scene_018":
        "31956",

    "scene_021":
        "28721436",
}


print()

print("=" * 78)

print(
    "KNOWN WRONG-GEOGRAPHY CHECK"
)

print("=" * 78)


known_pass = 0


scene_map = {

    scene.get(
        "scene_id"
    ):
        scene

    for scene
    in manifest.get(
        "scenes",
        [],
    )
}


for (
    scene_id,
    media_id,
) in known_bad.items():

    scene = scene_map.get(
        scene_id
    )


    if scene is None:

        print(
            scene_id,
            media_id,
            "-> SCENE MISSING",
        )

        continue


    candidates = (
        scene.get(
            "stock",
            {},
        ).get(
            "candidates",
            [],
        )
    )


    (
        kept,
        rejected,
        bypassed,
    ) = filter_geography_candidates(
        scene,
        candidates,
    )


    rejected_ids = {

        str(
            item.get(
                "media_id",
                "",
            )
        )

        for item
        in rejected
    }


    passed = (

        media_id
        in rejected_ids
    )


    if passed:

        known_pass += 1


    print(
        scene_id,
        media_id,
        "->",
        (
            "REJECTED PASS"
            if passed
            else
            "NOT REJECTED"
        ),
    )


print()

print(
    "Known geography cases:",
    f"{known_pass}/{len(known_bad)}",
)


# ==================================================
# FINAL RESULT
# ==================================================

print()

print("=" * 78)


if (

    required_country
    == "serbia"

    and

    known_pass
    >= 7

):

    print(
        "OFFLINE GEOGRAPHY TEST: PASS"
    )

else:

    print(
        "OFFLINE GEOGRAPHY TEST: REVIEW REQUIRED"
    )


print("=" * 78)


print()

print(
    "Original manifest was NOT modified."
)