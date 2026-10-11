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
    / "scene_pipeline_before_provider_flags_v2.py"
)


print("=" * 70)
print("ENABLE STOCK PROVIDER FLAGS V2")
print("=" * 70)


# ==================================================
# CHECK TARGET
# ==================================================

if not TARGET.exists():

    raise FileNotFoundError(
        f"Missing: {TARGET}"
    )


# ==================================================
# BACKUP CURRENT WORKING VERSION
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
# LOAD
# ==================================================

text = TARGET.read_text(
    encoding="utf-8"
)

lines = text.splitlines()


# ==================================================
# 1. IMPORT OS
# ==================================================

if not any(
    line.strip() == "import os"
    for line in lines
):

    lines.insert(
        0,
        "import os",
    )

    print(
        "import os: ADDED"
    )

else:

    print(
        "import os: ALREADY PRESENT"
    )


# ==================================================
# 2. ADD _env_enabled()
# ==================================================

if not any(
    "def _env_enabled(" in line
    for line in lines
):

    class_index = None

    for index, line in enumerate(
        lines
    ):

        if (
            line.strip()
            == "class ScenePipeline:"
        ):

            class_index = index
            break


    if class_index is None:

        raise RuntimeError(
            "Could not find class ScenePipeline."
        )


    helper_lines = [

        "",

        "    @staticmethod",

        "    def _env_enabled(",

        "        name,",

        "        default=True,",

        "    ):",
        "",

        "        raw = os.getenv(",

        "            name",

        "        )",
        "",

        "        if raw is None:",

        "            return bool(",

        "                default",

        "            )",
        "",

        "        value = str(",

        "            raw",

        "        ).strip().lower()",
        "",

        "        return value not in (",

        '            "0",',

        '            "false",',

        '            "no",',

        '            "off",',

        '            "disabled",',

        "        )",
        "",
    ]


    insert_at = (
        class_index
        + 1
    )


    lines[
        insert_at:
        insert_at
    ] = helper_lines


    print(
        "_env_enabled(): ADDED"
    )

else:

    print(
        "_env_enabled(): ALREADY PRESENT"
    )


# ==================================================
# 3. RELOAD TEXT AFTER HELPER INSERTION
# ==================================================

text = (
    "\n".join(lines)
    + "\n"
)

lines = text.splitlines()


# ==================================================
# 4. CHECK IF PROVIDER FLAGS ALREADY INSTALLED
# ==================================================

flags_already_present = (

    any(
        "STOCK_PROVIDER_PEXELS"
        in line
        for line in lines
    )

    and

    any(
        "STOCK_PROVIDER_PIXABAY"
        in line
        for line in lines
    )

    and

    any(
        "self.stock_providers"
        in line
        for line in lines
    )
)


if flags_already_present:

    print(
        "Provider flags block: ALREADY PRESENT"
    )

else:

    # ==================================================
    # FIND self.pexels = PexelsProvider()
    # ==================================================

    provider_start = None


    for index, line in enumerate(
        lines
    ):

        compact = (
            line
            .replace(" ", "")
            .replace("\t", "")
        )


        if (
            "self.pexels=PexelsProvider()"
            in compact
        ):

            provider_start = index
            break


    if provider_start is None:

        raise RuntimeError(
            "Could not find "
            "self.pexels = PexelsProvider()."
        )


    print(
        "Provider block start:",
        provider_start + 1,
    )


    # ==================================================
    # FIND self.search_manager = StockSearchManager(
    # ==================================================

    search_start = None


    for index in range(
        provider_start,
        len(lines),
    ):

        if (
            "self.search_manager"
            in lines[index]
            and
            "StockSearchManager"
            in lines[index]
        ):

            search_start = index
            break


    if search_start is None:

        raise RuntimeError(
            "Could not find "
            "self.search_manager = StockSearchManager(...)."
        )


    print(
        "SearchManager start:",
        search_start + 1,
    )


    # ==================================================
    # FIND END OF StockSearchManager(...)
    #
    # Uses parenthesis counting instead of comments.
    # ==================================================

    search_end = None

    balance = 0
    started = False


    for index in range(
        search_start,
        len(lines),
    ):

        line = lines[index]


        for char in line:

            if char == "(":

                balance += 1
                started = True

            elif char == ")":

                balance -= 1


        if (
            started
            and balance == 0
        ):

            search_end = index
            break


    if search_end is None:

        raise RuntimeError(
            "Could not locate end of "
            "StockSearchManager(...)."
        )


    print(
        "SearchManager end:",
        search_end + 1,
    )


    # ==================================================
    # GET INDENTATION
    # ==================================================

    original_line = lines[
        provider_start
    ]


    indentation = (
        original_line[
            :
            len(original_line)
            - len(original_line.lstrip())
        ]
    )


    if not indentation:

        indentation = "        "


    # ==================================================
    # NEW PROVIDER BLOCK
    # ==================================================

    new_block = [

        indentation
        + "# ==========================================",

        indentation
        + "# STOCK PROVIDERS",

        indentation
        + "# ==========================================",

        "",

        indentation
        + "self.stock_providers = []",

        "",

        indentation
        + "self.pexels = None",

        indentation
        + "self.pixabay = None",

        "",

        indentation
        + "pexels_enabled = self._env_enabled(",

        indentation
        + '    "STOCK_PROVIDER_PEXELS",',

        indentation
        + "    default=True,",

        indentation
        + ")",

        "",

        indentation
        + "pixabay_enabled = self._env_enabled(",

        indentation
        + '    "STOCK_PROVIDER_PIXABAY",',

        indentation
        + "    default=True,",

        indentation
        + ")",

        "",

        indentation
        + "if pexels_enabled:",

        "",

        indentation
        + "    self.pexels = PexelsProvider()",

        "",

        indentation
        + "    self.stock_providers.append(",

        indentation
        + "        self.pexels",

        indentation
        + "    )",

        "",

        indentation
        + "if pixabay_enabled:",

        "",

        indentation
        + "    self.pixabay = PixabayProvider()",

        "",

        indentation
        + "    self.stock_providers.append(",

        indentation
        + "        self.pixabay",

        indentation
        + "    )",

        "",

        indentation
        + "if not self.stock_providers:",

        "",

        indentation
        + "    raise RuntimeError(",

        indentation
        + '        "No stock providers are enabled."',

        indentation
        + "    )",

        "",

        indentation
        + "print(",

        indentation
        + '    "Stock providers enabled:",',

        indentation
        + "    [",

        indentation
        + "        provider.name",

        indentation
        + "        for provider",

        indentation
        + "        in self.stock_providers",

        indentation
        + "    ],",

        indentation
        + ")",

        "",

        indentation
        + "self.search_manager = StockSearchManager(",

        "",

        indentation
        + "    providers=",

        indentation
        + "        self.stock_providers,",

        "",

        indentation
        + "    per_query=",

        indentation
        + "        per_query,",

        "",

        indentation
        + "    max_candidates=",

        indentation
        + "        max_candidates,",

        indentation
        + ")",

        "",
    ]


    # ==================================================
    # REPLACE ONLY CODE BLOCK
    # ==================================================

    lines[
        provider_start:
        search_end + 1
    ] = new_block


    print(
        "Provider flags block: UPDATED"
    )


# ==================================================
# 5. BUILD FINAL SOURCE
# ==================================================

new_text = (
    "\n".join(lines)
    + "\n"
)


# ==================================================
# 6. SAFETY CHECK
# ==================================================

required = [

    "def _env_enabled(",

    "STOCK_PROVIDER_PEXELS",

    "STOCK_PROVIDER_PIXABAY",

    "self.stock_providers = []",

    "self.stock_providers.append(",

    "self.search_manager = StockSearchManager(",
]


for fragment in required:

    if fragment not in new_text:

        raise RuntimeError(
            "Safety check failed: "
            + fragment
        )


# ==================================================
# 7. WRITE
# ==================================================

TARGET.write_text(
    new_text,
    encoding="utf-8",
)


# ==================================================
# 8. COMPILE
# ==================================================

try:

    py_compile.compile(
        str(TARGET),
        doraise=True,
    )

except Exception as error:

    print()
    print(
        "COMPILE FAILED"
    )

    print(
        "Restoring backup..."
    )


    shutil.copy2(
        BACKUP,
        TARGET,
    )


    raise RuntimeError(
        f"Compile failed: {error}"
    )


# ==================================================
# PASS
# ==================================================

print()
print("=" * 70)
print("STOCK PROVIDER FLAGS V2: PASS")
print("=" * 70)

print(
    "Environment flags:"
)

print(
    "  STOCK_PROVIDER_PEXELS"
)

print(
    "  STOCK_PROVIDER_PIXABAY"
)

print()
print(
    "scene_pipeline.py compile: PASS"
)