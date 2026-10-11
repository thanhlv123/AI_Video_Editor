from pathlib import Path
import shutil
import py_compile


ROOT = Path(
    r"D:\YouTubeTools\AI_Video_Editor"
)

SCENE_PIPELINE = (
    ROOT
    / "pipeline"
    / "scene_pipeline.py"
)

BALANCED_SEARCH = (
    ROOT
    / "stock"
    / "balanced_search_manager.py"
)

VISUAL_STRATEGY = (
    ROOT
    / "pipeline"
    / "visual_strategy.py"
)

CONTEXT_GEO = (
    ROOT
    / "pipeline"
    / "context_geo.py"
)


BACKUPS = {
    SCENE_PIPELINE:
        ROOT
        / "pipeline"
        / "scene_pipeline_before_visual_proxy_v1.py",

    BALANCED_SEARCH:
        ROOT
        / "stock"
        / "balanced_search_manager_before_visual_proxy_v1.py",

    VISUAL_STRATEGY:
        ROOT
        / "pipeline"
        / "visual_strategy_before_search_activation_v1.py",

    CONTEXT_GEO:
        ROOT
        / "pipeline"
        / "context_geo_before_visual_proxy_v1.py",
}


print("=" * 80)
print("ENABLE VISUAL PROXY SEARCH V1")
print("=" * 80)


# ==================================================
# VERIFY FILES
# ==================================================

for path in (
    SCENE_PIPELINE,
    BALANCED_SEARCH,
    VISUAL_STRATEGY,
    CONTEXT_GEO,
):

    if not path.exists():

        raise FileNotFoundError(
            path
        )


# ==================================================
# BACKUPS
# ==================================================

for source, backup in BACKUPS.items():

    if not backup.exists():

        shutil.copy2(
            source,
            backup,
        )

        print(
            "Backup created:",
            backup,
        )

    else:

        print(
            "Backup already exists:",
            backup,
        )


# ==================================================
# 1. CONTEXT GEO
#
# Add Morocco proxy countries to country detection.
# ==================================================

geo_text = CONTEXT_GEO.read_text(
    encoding="utf-8"
)


if (
    '"algeria": ('
    not in geo_text
):

    marker = '''    "morocco": (
        "morocco",
        "moroccan",
    ),
'''


    replacement = '''    "morocco": (
        "morocco",
        "moroccan",
    ),

    "algeria": (
        "algeria",
        "algerian",
    ),

    "tunisia": (
        "tunisia",
        "tunisian",
    ),
'''


    if marker not in geo_text:

        raise RuntimeError(
            "Could not locate Morocco alias block "
            "in context_geo.py."
        )


    geo_text = geo_text.replace(
        marker,
        replacement,
        1,
    )


    print(
        "Country aliases: "
        "Algeria + Tunisia ADDED"
    )

else:

    print(
        "Country aliases already installed."
    )


# ==================================================
# 2. UPDATE ADAPTIVE GEO FILTER
#
# Proxy mode:
#
# ACCEPT:
# - project country
# - configured similar country
# - unknown country metadata
#
# REJECT:
# - explicitly detected unrelated country
#
# Generic mode remains geography-independent.
# ==================================================

strategy_text = VISUAL_STRATEGY.read_text(
    encoding="utf-8"
)


function_start = (
    strategy_text.find(
        "def filter_adaptive_geography_candidates("
    )
)


if function_start < 0:

    raise RuntimeError(
        "filter_adaptive_geography_candidates() "
        "not found."
    )


new_filter = r'''def filter_adaptive_geography_candidates(
    scene,
    candidates,
):

    candidates = list(
        candidates
        or []
    )

    project_context = scene.get(
        "project_context",
        {},
    )

    required_country = _norm(
        project_context.get(
            "required_country_key"
        )
    )

    strategy = scene.get(
        "visual_strategy",
        {},
    )

    policy = strategy.get(
        "geo_policy",
        STRICT,
    )

    proxy_countries = set(

        _norm(item)

        for item
        in strategy.get(
            "proxy_countries",
            []
        )

        if _norm(item)
    )

    kept = []
    rejected = []

    for candidate in candidates:

        item = dict(
            candidate
        )

        metadata_text = " ".join(
            [
                str(
                    item.get(
                        "title",
                        ""
                    )
                    or ""
                ),

                str(
                    item.get(
                        "source_url",
                        ""
                    )
                    or ""
                ),

                str(
                    item.get(
                        "page_url",
                        ""
                    )
                    or ""
                ),

                str(
                    item.get(
                        "photographer",
                        ""
                    )
                    or ""
                ),

                str(
                    item.get(
                        "author",
                        ""
                    )
                    or ""
                ),
            ]
        )

        detected = detect_countries(
            metadata_text
        )

        item[
            "detected_countries"
        ] = sorted(
            detected
        )

        tier = infer_query_tier(
            scene,
            item.get(
                "matched_query",
                ""
            ),
        )

        item[
            "matched_query_tier"
        ] = tier

        # ==================================================
        # ADAPTIVE CONFLICT
        # ==================================================

        geography_conflict = False


        if (
            detected
            and
            required_country
        ):

            # ----------------------------------------------
            # STRICT
            #
            # Exact geography remains mandatory.
            # ----------------------------------------------

            if policy == STRICT:

                geography_conflict = (
                    required_country
                    not in detected
                )


            # ----------------------------------------------
            # REGIONAL / VISUAL PROXY
            #
            # Explicitly named unrelated countries are
            # rejected.
            #
            # Project country and configured proxy countries
            # are allowed.
            # ----------------------------------------------

            elif policy in (
                REGIONAL_PROXY,
                VISUAL_PROXY,
            ):

                project_match = (
                    required_country
                    in detected
                )

                proxy_match = bool(
                    detected
                    &
                    proxy_countries
                )

                geography_conflict = not (
                    project_match
                    or
                    proxy_match
                )


            # ----------------------------------------------
            # GENERIC
            #
            # Geography is deliberately ignored.
            # ----------------------------------------------

            else:

                geography_conflict = False


        if geography_conflict:

            rejected.append(
                {
                    "provider":
                        item.get(
                            "provider"
                        ),

                    "media_id":
                        item.get(
                            "media_id"
                        ),

                    "detected_countries":
                        sorted(
                            detected
                        ),

                    "title":
                        item.get(
                            "title",
                            ""
                        ),

                    "reason":
                        "adaptive_geography_conflict",

                    "geo_policy":
                        policy,
                }
            )

            continue


        # ==================================================
        # GEO COMPATIBILITY METADATA
        #
        # Stored for future ranking.
        # V1 does NOT change MediaRanker weights yet.
        # ==================================================

        if not detected:

            geo_score = 0.75

        elif (
            required_country
            and
            required_country in detected
        ):

            geo_score = 1.0

        elif (
            detected
            &
            proxy_countries
        ):

            geo_score = 0.90

        elif policy == GENERIC:

            geo_score = 0.75

        else:

            geo_score = 0.50


        item[
            "geo_compatibility"
        ] = round(
            geo_score,
            3
        )

        kept.append(
            item
        )


    # ==================================================
    # SAFETY BYPASS
    #
    # Preserve old V1 safety philosophy.
    # ==================================================

    bypassed = False


    if (
        candidates
        and
        not kept
    ):

        kept = candidates

        bypassed = True


    return (
        kept,
        rejected,
        bypassed,
    )
'''


strategy_text = (

    strategy_text[
        :function_start
    ]

    +

    new_filter

    +

    "\n"
)


print(
    "Adaptive geography filter: UPDATED"
)


# ==================================================
# 3. SCENE PIPELINE
# ==================================================

scene_text = SCENE_PIPELINE.read_text(
    encoding="utf-8"
)


# ----------------------------------------------
# IMPORT VISUAL STRATEGY
# ----------------------------------------------

if (
    "from pipeline.visual_strategy import"
    not in scene_text
):

    class_marker = (
        "\nclass ScenePipeline:"
    )


    import_block = '''

from pipeline.visual_strategy import (
    enrich_manifest_with_visual_strategy,
    filter_adaptive_geography_candidates,
)

'''


    if class_marker not in scene_text:

        raise RuntimeError(
            "ScenePipeline class marker not found."
        )


    scene_text = scene_text.replace(
        class_marker,
        import_block
        + "class ScenePipeline:",
        1,
    )


    print(
        "ScenePipeline visual strategy import: ADDED"
    )


# ----------------------------------------------
# ACTIVATE STRATEGY BEFORE FIRST SEARCH
# ----------------------------------------------

search_anchor = '''        candidates = (
            self.search_manager.search_scene(
                scene
            )
        )

        # GEOGRAPHY GUARD 58B V1
'''


search_replacement = '''        # ==================================================
        # VISUAL PROXY SEARCH 58D V1
        #
        # Only first search attempt activates the strategy.
        # Existing retry logic remains unchanged.
        # ==================================================

        if (
            attempt == 0
            and
            not scene.get(
                "search",
                {},
            ).get(
                "visual_proxy_search"
            )
        ):

            enrich_manifest_with_visual_strategy(
                {
                    "scenes": [
                        scene
                    ]
                },
                activate_search=True,
            )


        visual_strategy = scene.get(
            "visual_strategy",
            {},
        )


        print(
            "Visual strategy:",
            visual_strategy.get(
                "geo_policy",
                "STRICT",
            ),
        )


        if visual_strategy.get(
            "explicit_place"
        ):

            print(
                "Visual location:",
                visual_strategy.get(
                    "explicit_place"
                ),
            )


        candidates = (
            self.search_manager.search_scene(
                scene
            )
        )

        # ADAPTIVE GEOGRAPHY GUARD 58D V1
'''


if (
    "VISUAL PROXY SEARCH 58D V1"
    not in scene_text
):

    if search_anchor not in scene_text:

        raise RuntimeError(
            "Could not locate ScenePipeline "
            "search/geography hook."
        )


    scene_text = scene_text.replace(
        search_anchor,
        search_replacement,
        1,
    )


    print(
        "Visual Proxy Search hook: ADDED"
    )

else:

    print(
        "Visual Proxy Search hook already installed."
    )


# ----------------------------------------------
# REPLACE OLD HARD GEO FILTER CALL
# ----------------------------------------------

old_filter_call = '''        ) = filter_geography_candidates(
            scene,
            candidates,
        )
'''


new_filter_call = '''        ) = filter_adaptive_geography_candidates(
            scene,
            candidates,
        )
'''


if old_filter_call in scene_text:

    scene_text = scene_text.replace(
        old_filter_call,
        new_filter_call,
        1,
    )


    print(
        "Geography Guard: V1 -> ADAPTIVE"
    )

elif (
    "filter_adaptive_geography_candidates("
    in scene_text
):

    print(
        "Adaptive Geography Guard already active."
    )

else:

    raise RuntimeError(
        "Could not locate geography filter call."
    )


# ==================================================
# 4. BALANCED SEARCH
#
# STRICT  -> original max (20)
# PROXY   -> up to 40 globally
#
# Each provider still has its original per-provider
# ceiling, so Pexels/Pixabay remain balanced.
# ==================================================

balanced_text = BALANCED_SEARCH.read_text(
    encoding="utf-8"
)


method_start = balanced_text.find(
    "    def search_scene(\n"
)


if method_start < 0:

    raise RuntimeError(
        "Balanced search_scene() not found."
    )


next_method = balanced_text.find(
    "\n    def ",
    method_start + 10,
)


if next_method < 0:

    next_method = len(
        balanced_text
    )


before_method = balanced_text[
    :method_start
]

method_text = balanced_text[
    method_start:
    next_method
]

after_method = balanced_text[
    next_method:
]


if (
    "VISUAL PROXY POOL 58D V1"
    not in method_text
):

    old_print = '''        print(
            "Global max candidates:",
            self.max_candidates,
        )
'''


    new_print = '''        # ==================================================
        # VISUAL PROXY POOL 58D V1
        #
        # STRICT scenes retain the original pool.
        # Proxy scenes may combine up to 20 results from
        # each of the two enabled providers -> 40 global.
        # ==================================================

        strategy = scene.get(
            "visual_strategy",
            {},
        )

        policy = strategy.get(
            "geo_policy",
            "STRICT",
        )

        visual_proxy_search = bool(
            scene.get(
                "search",
                {},
            ).get(
                "visual_proxy_search"
            )
        )


        if (
            visual_proxy_search
            and
            policy != "STRICT"
        ):

            effective_max_candidates = max(
                self.max_candidates,
                40,
            )

        else:

            effective_max_candidates = (
                self.max_candidates
            )


        print(
            "Global max candidates:",
            effective_max_candidates,
        )

        print(
            "Search policy:",
            policy,
        )
'''


    if old_print not in method_text:

        raise RuntimeError(
            "Balanced search max-candidate "
            "print block not found."
        )


    method_text = method_text.replace(
        old_print,
        new_print,
        1,
    )


    # Only inside search_scene().
    method_text = method_text.replace(
        "< self.max_candidates",
        "< effective_max_candidates",
    )


    method_text = method_text.replace(
        ">= self.max_candidates",
        ">= effective_max_candidates",
    )


    print(
        "Proxy candidate pool 20 -> 40: ADDED"
    )

else:

    print(
        "Proxy candidate pool already installed."
    )


balanced_text = (
    before_method
    + method_text
    + after_method
)


# ==================================================
# IN-MEMORY COMPILE
# ==================================================

compile(
    geo_text,
    str(CONTEXT_GEO),
    "exec",
)

compile(
    strategy_text,
    str(VISUAL_STRATEGY),
    "exec",
)

compile(
    scene_text,
    str(SCENE_PIPELINE),
    "exec",
)

compile(
    balanced_text,
    str(BALANCED_SEARCH),
    "exec",
)


print(
    "In-memory compile: PASS"
)


# ==================================================
# WRITE FILES
# ==================================================

try:

    CONTEXT_GEO.write_text(
        geo_text,
        encoding="utf-8",
    )

    VISUAL_STRATEGY.write_text(
        strategy_text,
        encoding="utf-8",
    )

    SCENE_PIPELINE.write_text(
        scene_text,
        encoding="utf-8",
    )

    BALANCED_SEARCH.write_text(
        balanced_text,
        encoding="utf-8",
    )


    for path in (
        CONTEXT_GEO,
        VISUAL_STRATEGY,
        SCENE_PIPELINE,
        BALANCED_SEARCH,
    ):

        py_compile.compile(
            str(path),
            doraise=True,
        )


except Exception:

    print()
    print(
        "PATCH FAILED - RESTORING BACKUPS"
    )

    for source, backup in BACKUPS.items():

        shutil.copy2(
            backup,
            source,
        )

    raise


# ==================================================
# SUCCESS
# ==================================================

print()
print("=" * 80)
print("VISUAL PROXY SEARCH V1: PASS")
print("=" * 80)

print(
    "Visual Strategy V3: ACTIVE"
)

print(
    "Multi-tier queries: ACTIVE"
)

print(
    "Adaptive Geography Guard: ACTIVE"
)

print(
    "Proxy candidate pool: 40"
)

print(
    "Strict candidate pool: unchanged"
)

print(
    "Pexels/Pixabay balancing: unchanged"
)

print(
    "MediaRanker weights: unchanged"
)

print(
    "KIE visual weights: unchanged"
)

print(
    "V5 fallback: unchanged"
)

print(
    "Timeline/render: unchanged"
)