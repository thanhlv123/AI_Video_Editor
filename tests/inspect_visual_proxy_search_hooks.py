from pathlib import Path
import inspect
import sys


ROOT = Path(
    r"D:\YouTubeTools\AI_Video_Editor"
)

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


print("=" * 80)
print("58D-2A VISUAL PROXY SEARCH HOOK INSPECTOR")
print("=" * 80)


def show_source(
    title,
    obj,
):

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    try:

        print(
            inspect.getsource(
                obj
            )
        )

    except Exception as error:

        print(
            "SOURCE READ FAILED:",
            error,
        )


# ==================================================
# BALANCED SEARCH MANAGER
# ==================================================

from stock.balanced_search_manager import (
    BalancedStockSearchManager,
)

show_source(
    "BALANCED STOCK SEARCH MANAGER CLASS",
    BalancedStockSearchManager,
)


# ==================================================
# SCENE PIPELINE
# ==================================================

from pipeline.scene_pipeline import (
    ScenePipeline,
)

show_source(
    "SCENE PIPELINE _search_and_select",
    ScenePipeline._search_and_select,
)


# ==================================================
# STOCK RANKER
# ==================================================

from stock.ranker import (
    MediaRanker,
)

show_source(
    "MEDIA RANKER CLASS",
    MediaRanker,
)


# ==================================================
# OPTIONAL SEARCH MANAGER
# ==================================================

try:

    from stock.search_manager import (
        StockSearchManager,
    )

    show_source(
        "STOCK SEARCH MANAGER CLASS",
        StockSearchManager,
    )

except Exception as error:

    print()
    print(
        "StockSearchManager inspection skipped:",
        error,
    )


# ==================================================
# CURRENT CONTEXT GEO MODULE
# ==================================================

try:

    import pipeline.context_geo as context_geo

    show_source(
        "CONTEXT GEO MODULE",
        context_geo,
    )

except Exception as error:

    print()
    print(
        "Context geo inspection skipped:",
        error,
    )


print()
print("=" * 80)
print("58D-2A INSPECTION COMPLETE")
print("=" * 80)

print(
    "No production file was modified."
)