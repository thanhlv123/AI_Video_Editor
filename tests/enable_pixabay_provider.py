from pathlib import Path
import py_compile
import shutil


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
    / "scene_pipeline_before_pixabay.py"
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("ENABLE PIXABAY PROVIDER V2")
print("=" * 70)


# ==================================================
# CHECK TARGET
# ==================================================

if not TARGET.exists():

    raise FileNotFoundError(
        f"Missing file: {TARGET}"
    )


# ==================================================
# BACKUP
#
# Do NOT overwrite the original backup.
# ==================================================

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


# ==================================================
# LOAD CURRENT FILE
# ==================================================

text = TARGET.read_text(
    encoding="utf-8"
)

lines = text.splitlines()


# ==================================================
# STEP 1
# IMPORT PIXABAY
# ==================================================

pixabay_import = (
    "from stock.pixabay import PixabayProvider"
)

pexels_import = (
    "from stock.pexels import PexelsProvider"
)


if pixabay_import in lines:

    print(
        "Pixabay import: ALREADY PRESENT"
    )

else:

    try:

        import_index = lines.index(
            pexels_import
        )

    except ValueError:

        raise RuntimeError(
            "Could not find PexelsProvider import."
        )


    lines.insert(
        import_index + 1,
        pixabay_import,
    )


    print(
        "Pixabay import: ADDED"
    )


# ==================================================
# STEP 2
# ADD self.pixabay
# ==================================================

pexels_instance_index = None


for index, line in enumerate(lines):

    if (
        "self.pexels"
        in line
        and "PexelsProvider()"
        in line
    ):

        pexels_instance_index = index

        break


if pexels_instance_index is None:

    raise RuntimeError(
        "Could not find self.pexels = PexelsProvider()."
    )


pixabay_instance_exists = any(

    (
        "self.pixabay"
        in line
        and "PixabayProvider()"
        in line
    )

    for line in lines
)


if pixabay_instance_exists:

    print(
        "Pixabay instance: ALREADY PRESENT"
    )

else:

    pexels_line = lines[
        pexels_instance_index
    ]


    indentation = (
        pexels_line[
            : len(pexels_line)
            - len(pexels_line.lstrip())
        ]
    )


    lines.insert(

        pexels_instance_index + 1,

        (
            indentation
            + "self.pixabay = PixabayProvider()"
        ),
    )


    print(
        "Pixabay instance: ADDED"
    )


# ==================================================
# STEP 3
# FIND StockSearchManager providers LIST
# ==================================================

search_manager_index = None


for index, line in enumerate(lines):

    if (
        "self.search_manager"
        in line
        and "StockSearchManager"
        in line
    ):

        search_manager_index = index

        break


if search_manager_index is None:

    raise RuntimeError(
        "Could not find StockSearchManager."
    )


providers_start = None
providers_end = None


for index in range(
    search_manager_index,
    min(
        len(lines),
        search_manager_index + 30,
    ),
):

    compact = (
        lines[index]
        .replace(" ", "")
        .replace("\t", "")
    )


    if (
        providers_start is None
        and "providers=[" in compact
    ):

        providers_start = index

        continue


    if (
        providers_start is not None
        and compact.startswith("],")
    ):

        providers_end = index

        break


if providers_start is None:

    raise RuntimeError(
        "Could not find providers=[ in StockSearchManager."
    )


if providers_end is None:

    raise RuntimeError(
        "Could not find end of providers list."
    )


# ==================================================
# CHECK PROVIDERS
# ==================================================

provider_section = "\n".join(

    lines[
        providers_start:
        providers_end + 1
    ]
)


if "self.pixabay" in provider_section:

    print(
        "Pixabay in provider list: ALREADY PRESENT"
    )

else:

    pexels_provider_line_index = None


    for index in range(
        providers_start,
        providers_end,
    ):

        if "self.pexels" in lines[index]:

            pexels_provider_line_index = index

            break


    if pexels_provider_line_index is None:

        raise RuntimeError(
            "Could not find self.pexels "
            "inside providers list."
        )


    current_line = lines[
        pexels_provider_line_index
    ]


    indentation = (
        current_line[
            : len(current_line)
            - len(current_line.lstrip())
        ]
    )


    # Make sure Pexels has a comma.

    if not current_line.rstrip().endswith(
        ","
    ):

        lines[
            pexels_provider_line_index
        ] = (
            current_line.rstrip()
            + ","
        )


    lines.insert(

        pexels_provider_line_index + 1,

        indentation
        + "self.pixabay",
    )


    print(
        "Pixabay in provider list: ADDED"
    )


# ==================================================
# BUILD FINAL SOURCE
# ==================================================

new_text = (
    "\n".join(lines)
    + "\n"
)


# ==================================================
# SAFETY CHECKS BEFORE WRITE
# ==================================================

required_fragments = [

    "from stock.pixabay import PixabayProvider",

    "self.pixabay = PixabayProvider()",

    "self.pexels,",

    "self.pixabay",
]


for fragment in required_fragments:

    if fragment not in new_text:

        raise RuntimeError(
            "Safety check failed: "
            + fragment
        )


# ==================================================
# WRITE
# ==================================================

TARGET.write_text(
    new_text,
    encoding="utf-8",
)


# ==================================================
# COMPILE CHECK
# ==================================================

try:

    py_compile.compile(

        str(TARGET),

        doraise=True,
    )


except Exception as error:

    print()
    print(
        "COMPILE FAILED."
    )

    print(
        "Restoring backup..."
    )


    shutil.copy2(
        BACKUP,
        TARGET,
    )


    raise RuntimeError(
        f"scene_pipeline.py compile failed: {error}"
    )


# ==================================================
# SUCCESS
# ==================================================

print()
print("=" * 70)
print("PIXABAY PROVIDER ENABLED: PASS")
print("=" * 70)

print(
    "Pexels instance: PASS"
)

print(
    "Pixabay instance: PASS"
)

print(
    "StockSearchManager:"
)

print(
    "  - Pexels"
)

print(
    "  - Pixabay"
)

print()
print(
    "scene_pipeline.py compile: PASS"
)