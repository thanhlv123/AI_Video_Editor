from pathlib import Path
import shutil
import py_compile


ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

TARGET = (
    ROOT
    / "pipeline"
    / "scene_pipeline.py"
)

BACKUP = (
    ROOT
    / "pipeline"
    / "scene_pipeline_before_balanced_search.py"
)


if not TARGET.exists():

    raise FileNotFoundError(
        TARGET
    )


if not BACKUP.exists():

    shutil.copy2(
        TARGET,
        BACKUP,
    )

    print(
        "Backup created:",
        BACKUP,
    )

else:

    print(
        "Backup already exists:",
        BACKUP,
    )


text = TARGET.read_text(
    encoding="utf-8"
)


old_import = (
    "from stock.search_manager "
    "import StockSearchManager"
)


new_import = (
    "from stock.balanced_search_manager "
    "import BalancedStockSearchManager "
    "as StockSearchManager"
)


if new_import in text:

    print(
        "Balanced import: ALREADY PRESENT"
    )

elif old_import in text:

    text = text.replace(

        old_import,

        new_import,

        1,
    )

    print(
        "Balanced import: ADDED"
    )

else:

    raise RuntimeError(
        "Could not find StockSearchManager import."
    )


TARGET.write_text(
    text,
    encoding="utf-8",
)


try:

    py_compile.compile(
        str(TARGET),
        doraise=True,
    )

except Exception:

    shutil.copy2(
        BACKUP,
        TARGET,
    )

    raise


print()
print("=" * 70)
print(
    "BALANCED STOCK SEARCH: PASS"
)
print("=" * 70)