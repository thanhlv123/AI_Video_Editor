from pathlib import Path
from copy import deepcopy
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
    filter_adaptive_geography_candidates,
    infer_query_tier,
)

import stock.balanced_search_manager as bsm


MANIFEST = (
    ROOT
    / "projects"
    / "runs"
    / "file_chay_thu_01_1356b5b5"
    / "ai_manifest.json"
)


print("=" * 80)
print("58D-2C VISUAL PROXY INTEGRATION V2")
print("=" * 80)


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
        activate_search=True,
    )
)


scene_map = {

    scene.get(
        "scene_id"
    ):
        scene

    for scene
    in manifest.get(
        "scenes",
        []
    )
}


scene_005 = scene_map[
    "scene_005"
]

scene_006 = scene_map[
    "scene_006"
]

scene_007 = scene_map[
    "scene_007"
]


passed = []


# ==================================================
# TEST 1
# SCENE 006 QUERY EXPANSION
# ==================================================

queries = (
    scene_006[
        "visual_strategy"
    ][
        "search_queries"
    ]
)


print()
print(
    "Scene006 policy:",
    scene_006[
        "visual_strategy"
    ][
        "geo_policy"
    ],
)


print(
    "Scene006 queries:"
)


for query in queries:

    print(
        "  -",
        query,
    )


query_text = " | ".join(
    queries
).lower()


query_checks = {

    "North Africa":
        "north africa"
        in query_text,

    "Maghreb":
        "maghreb"
        in query_text,

    "Algeria":
        "algeria"
        in query_text,

    "Tunisia":
        "tunisia"
        in query_text,

    "Generic ski":
        (
            "ski resort snow"
            in query_text
            or
            "snowy mountain ski resort"
            in query_text
        ),
}


for name, value in query_checks.items():

    print(
        name,
        "->",
        "PASS"
        if value
        else "FAIL",
    )


passed.append(
    all(
        query_checks.values()
    )
)


# ==================================================
# TEST 2
# FIRST FOUR QUERY TIERS
# ==================================================

first_four = [

    infer_query_tier(
        scene_006,
        query,
    )

    for query
    in queries[:4]
]


print()
print(
    "First four tiers:",
    first_four,
)


tier_ok = (
    first_four
    ==
    [
        "exact_geo",
        "regional_proxy",
        "visual_proxy",
        "generic",
    ]
)


print(
    "Interleaved tier order:",
    "PASS"
    if tier_ok
    else "FAIL",
)


passed.append(
    tier_ok
)


# ==================================================
# TEST 3
# STRICT SCENE REJECTS SWITZERLAND
# ==================================================

strict_candidates = [

    {
        "provider":
            "pixabay",

        "media_id":
            "swiss_test",

        "title":
            "Switzerland Alps ski resort",

        "matched_query":
            "Morocco Atlas Mountains winter snow",
    },

    {
        "provider":
            "pexels",

        "media_id":
            "morocco_test",

        "title":
            "Morocco Atlas Mountains winter",

        "matched_query":
            "Morocco Atlas Mountains winter snow",
    },
]


(
    strict_kept,
    strict_rejected,
    strict_bypass,
) = filter_adaptive_geography_candidates(
    scene_005,
    strict_candidates,
)


strict_rejected_ids = {

    item.get(
        "media_id"
    )

    for item
    in strict_rejected
}


strict_ok = (
    "swiss_test"
    in strict_rejected_ids

    and

    any(
        item.get(
            "media_id"
        )
        == "morocco_test"

        for item
        in strict_kept
    )

    and

    not strict_bypass
)


print()
print(
    "STRICT Switzerland rejection:",
    "PASS"
    if strict_ok
    else "FAIL",
)


passed.append(
    strict_ok
)


# ==================================================
# TEST 4
# VISUAL PROXY GEO FILTER
# ==================================================

proxy_candidates = [

    {
        "provider":
            "pexels",

        "media_id":
            "alg",

        "title":
            "Algeria modern city street",
    },

    {
        "provider":
            "pixabay",

        "media_id":
            "tun",

        "title":
            "Tunisia city lifestyle",
    },

    {
        "provider":
            "pexels",

        "media_id":
            "ind",

        "title":
            "India city street",
    },

    {
        "provider":
            "pixabay",

        "media_id":
            "unknown",

        "title":
            "Young women modern city street",
    },
]


(
    proxy_kept,
    proxy_rejected,
    proxy_bypass,
) = filter_adaptive_geography_candidates(
    scene_007,
    proxy_candidates,
)


kept_ids = {

    item.get(
        "media_id"
    )

    for item
    in proxy_kept
}


rejected_ids = {

    item.get(
        "media_id"
    )

    for item
    in proxy_rejected
}


proxy_ok = (

    "alg"
    in kept_ids

    and

    "tun"
    in kept_ids

    and

    "unknown"
    in kept_ids

    and

    "ind"
    in rejected_ids

    and

    not proxy_bypass
)


print()
print(
    "VISUAL_PROXY Algeria KEEP:",
    "PASS"
    if "alg" in kept_ids
    else "FAIL",
)


print(
    "VISUAL_PROXY Tunisia KEEP:",
    "PASS"
    if "tun" in kept_ids
    else "FAIL",
)


print(
    "VISUAL_PROXY India REJECT:",
    "PASS"
    if "ind" in rejected_ids
    else "FAIL",
)


print(
    "VISUAL_PROXY unknown KEEP:",
    "PASS"
    if "unknown" in kept_ids
    else "FAIL",
)


passed.append(
    proxy_ok
)


# ==================================================
# TEST 5
# BALANCED SEARCH FIRST ATTEMPT VS RETRY
# ==================================================

captured = []


class DummyProvider:

    name = "dummy"


class FakeLegacyManager:

    def __init__(
        self,
        providers,
        per_query=5,
        max_candidates=20,
    ):

        pass


    def search_scene(
        self,
        scene,
    ):

        captured.append(
            {
                "primary":
                    scene[
                        "search"
                    ].get(
                        "primary_keyword"
                    ),

                "keywords":
                    list(
                        scene[
                            "search"
                        ].get(
                            "keywords",
                            [],
                        )
                    ),
            }
        )

        return []


original_legacy = (
    bsm.LegacyStockSearchManager
)


try:

    bsm.LegacyStockSearchManager = (
        FakeLegacyManager
    )


    manager = (
        bsm.BalancedStockSearchManager(
            providers=[
                DummyProvider()
            ],
            per_query=5,
            max_candidates=20,
        )
    )


    first_scene = deepcopy(
        scene_006
    )


    first_scene.setdefault(
        "search",
        {},
    )[
        "visual_strategy_query_order_active"
    ] = True


    manager._search_provider(
        DummyProvider(),
        first_scene,
    )


    first_expected = queries[
        0
    ]


    first_actual = captured[
        -1
    ][
        "primary"
    ]


    first_order_ok = (
        first_actual
        == first_expected
    )


    print()
    print(
        "First-attempt provider order:",
        "PASS"
        if first_order_ok
        else "FAIL",
    )


    print(
        "Expected first:",
        first_expected,
    )


    print(
        "Actual first:",
        first_actual,
    )


    passed.append(
        first_order_ok
    )


    retry_scene = deepcopy(
        scene_006
    )


    retry_scene[
        "search"
    ][
        "primary_keyword"
    ] = (
        "snow mountain skiing"
    )


    retry_scene[
        "search"
    ][
        "keywords"
    ] = [
        "small ski resort mountain"
    ]


    retry_scene[
        "search"
    ][
        "visual_strategy_query_order_active"
    ] = False


    manager._search_provider(
        DummyProvider(),
        retry_scene,
    )


    retry_actual = captured[
        -1
    ][
        "primary"
    ]


    retry_ok = (
        retry_actual
        == "snow mountain skiing"
    )


    print()
    print(
        "Retry query preserved:",
        "PASS"
        if retry_ok
        else "FAIL",
    )


    print(
        "Retry actual:",
        retry_actual,
    )


    passed.append(
        retry_ok
    )


finally:

    bsm.LegacyStockSearchManager = (
        original_legacy
    )


# ==================================================
# FINAL
# ==================================================

print()
print("=" * 80)


if all(
    passed
):

    print(
        "VISUAL PROXY INTEGRATION V2: PASS"
    )

else:

    print(
        "VISUAL PROXY INTEGRATION V2: FAIL"
    )


print("=" * 80)

print(
    "No network/API request was made."
)