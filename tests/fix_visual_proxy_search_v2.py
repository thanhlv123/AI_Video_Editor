from pathlib import Path
import shutil
import py_compile


ROOT = Path(
    r"D:\YouTubeTools\AI_Video_Editor"
)

VISUAL = (
    ROOT
    / "pipeline"
    / "visual_strategy.py"
)

SCENE = (
    ROOT
    / "pipeline"
    / "scene_pipeline.py"
)

BALANCED = (
    ROOT
    / "stock"
    / "balanced_search_manager.py"
)


BACKUPS = {
    VISUAL:
        ROOT
        / "pipeline"
        / "visual_strategy_before_query_order_v2.py",

    SCENE:
        ROOT
        / "pipeline"
        / "scene_pipeline_before_query_order_v2.py",

    BALANCED:
        ROOT
        / "stock"
        / "balanced_search_manager_before_query_order_v2.py",
}


print("=" * 80)
print("FIX VISUAL PROXY SEARCH V2")
print("=" * 80)


for path in (
    VISUAL,
    SCENE,
    BALANCED,
):

    if not path.exists():
        raise FileNotFoundError(
            path
        )


for source, backup in BACKUPS.items():

    if not backup.exists():

        shutil.copy2(
            source,
            backup,
        )

        print(
            "Backup:",
            backup,
        )


# ==================================================
# 1. GENERICIZE PROXY QUERY
#
# Remove named places such as:
#
# Atlas Mountains
# Casablanca
#
# from proxy/generic queries.
#
# STRICT scenes are unaffected because their
# generic query is never used.
# ==================================================

visual_text = VISUAL.read_text(
    encoding="utf-8"
)


if (
    "VISUAL PROXY GENERICIZE 58D V2"
    not in visual_text
):

    old_block = '''    remove_terms = [

        project_context.get(
            "required_country",
            ""
        ),

        *profile.get(
            "regions",
            []
        ),
    ]
'''


    new_block = '''    # VISUAL PROXY GENERICIZE 58D V2
    #
    # Proxy scenes should search by visible meaning,
    # not remain locked to an AI-inherited place name.
    remove_terms = [

        project_context.get(
            "required_country",
            ""
        ),

        *profile.get(
            "regions",
            []
        ),

        *KNOWN_PLACES,
    ]
'''


    if old_block not in visual_text:

        raise RuntimeError(
            "genericize_query remove_terms "
            "block not found."
        )


    visual_text = visual_text.replace(
        old_block,
        new_block,
        1,
    )


    print(
        "Proxy place-name removal: ADDED"
    )

else:

    print(
        "Proxy place-name removal already installed."
    )


# ==================================================
# 2. SCENE PIPELINE
#
# Explicitly tell Balanced Search:
#
# attempt 0 -> use Visual Strategy query order
# retry     -> preserve existing retry queries
# ==================================================

scene_text = SCENE.read_text(
    encoding="utf-8"
)


if (
    "VISUAL QUERY ORDER 58D V2"
    not in scene_text
):

    visual_marker = (
        "# VISUAL PROXY SEARCH 58D V1"
    )


    marker_pos = scene_text.find(
        visual_marker
    )


    if marker_pos < 0:

        raise RuntimeError(
            "VISUAL PROXY SEARCH 58D V1 "
            "marker not found."
        )


    candidate_pos = scene_text.find(
        "        candidates = (\n",
        marker_pos,
    )


    if candidate_pos < 0:

        raise RuntimeError(
            "search_manager candidate call "
            "not found after Visual Proxy marker."
        )


    insert_block = '''        # VISUAL QUERY ORDER 58D V2
        #
        # First attempt uses interleaved Visual Strategy
        # queries.
        #
        # Retry attempts keep the old retry-search logic.
        scene.setdefault(
            "search",
            {},
        )[
            "visual_strategy_query_order_active"
        ] = (
            attempt == 0
        )


'''


    scene_text = (
        scene_text[
            :candidate_pos
        ]

        + insert_block

        + scene_text[
            candidate_pos:
        ]
    )


    print(
        "Scene attempt query-order flag: ADDED"
    )

else:

    print(
        "Scene attempt query-order flag already installed."
    )


# ==================================================
# 3. BALANCED SEARCH PROVIDER ORDER
#
# Important:
#
# We modify ONLY provider_scene, a deepcopy.
#
# Original scene keeps its generic primary keyword
# for MediaRanker semantic scoring.
# ==================================================

balanced_text = BALANCED.read_text(
    encoding="utf-8"
)


if (
    "VISUAL QUERY ORDER 58D V2"
    not in balanced_text
):

    old_block = '''            provider_scene = deepcopy(
                scene
            )


            results = manager.search_scene(
                provider_scene
            )
'''


    new_block = '''            provider_scene = deepcopy(
                scene
            )


            # ==================================================
            # VISUAL QUERY ORDER 58D V2
            #
            # Only first search attempt uses the interleaved:
            #
            # Exact -> Regional -> Visual -> Generic
            #
            # Retry searches must keep retry_scene queries.
            # ==================================================

            provider_search = (
                provider_scene.setdefault(
                    "search",
                    {},
                )
            )


            strategy = (
                provider_scene.get(
                    "visual_strategy",
                    {},
                )
            )


            ordered_queries = list(
                strategy.get(
                    "search_queries",
                    [],
                )
                or []
            )


            ordered_queries = [

                str(query).strip()

                for query
                in ordered_queries

                if str(
                    query
                ).strip()
            ]


            if (
                provider_search.get(
                    "visual_strategy_query_order_active"
                )
                and
                ordered_queries
            ):

                provider_search[
                    "primary_keyword"
                ] = ordered_queries[
                    0
                ]


                provider_search[
                    "keywords"
                ] = ordered_queries[
                    1:
                ]


                print(
                    "Visual query order:"
                )


                for query in ordered_queries:

                    print(
                        "  ->",
                        query,
                    )


            results = manager.search_scene(
                provider_scene
            )
'''


    if old_block not in balanced_text:

        raise RuntimeError(
            "_search_provider deepcopy block "
            "not found."
        )


    balanced_text = balanced_text.replace(
        old_block,
        new_block,
        1,
    )


    print(
        "Balanced provider query order: ADDED"
    )

else:

    print(
        "Balanced provider query order already installed."
    )


# ==================================================
# COMPILE BEFORE WRITE
# ==================================================

compile(
    visual_text,
    str(VISUAL),
    "exec",
)

compile(
    scene_text,
    str(SCENE),
    "exec",
)

compile(
    balanced_text,
    str(BALANCED),
    "exec",
)


print(
    "In-memory compile: PASS"
)


# ==================================================
# WRITE
# ==================================================

try:

    VISUAL.write_text(
        visual_text,
        encoding="utf-8",
    )

    SCENE.write_text(
        scene_text,
        encoding="utf-8",
    )

    BALANCED.write_text(
        balanced_text,
        encoding="utf-8",
    )


    for path in (
        VISUAL,
        SCENE,
        BALANCED,
    ):

        py_compile.compile(
            str(path),
            doraise=True,
        )


except Exception:

    print(
        "FAILED - RESTORING BACKUPS"
    )


    for source, backup in BACKUPS.items():

        shutil.copy2(
            backup,
            source,
        )


    raise


print()
print("=" * 80)
print("VISUAL PROXY SEARCH V2 FIX: PASS")
print("=" * 80)

print(
    "Proxy named-place removal: ACTIVE"
)

print(
    "First-attempt interleaved queries: ACTIVE"
)

print(
    "Retry query preservation: ACTIVE"
)

print(
    "Adaptive Geography Guard: unchanged"
)

print(
    "V5 fallback: unchanged"
)

print(
    "MediaRanker weights: unchanged"
)

print(
    "Timeline/render: unchanged"
)