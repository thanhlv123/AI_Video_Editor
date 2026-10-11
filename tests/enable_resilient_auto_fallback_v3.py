from pathlib import Path
import py_compile
import shutil


ROOT = Path(__file__).resolve().parent.parent

TARGET = ROOT / "pipeline" / "scene_pipeline.py"

BACKUP = (
    ROOT
    / "pipeline"
    / "scene_pipeline_before_resilient_fallback_v3.py"
)


print("=" * 70)
print("ENABLE RESILIENT AUTO FALLBACK V3")
print("=" * 70)


if not TARGET.exists():
    raise FileNotFoundError(TARGET)


# ==================================================
# BACKUP
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


text = TARGET.read_text(
    encoding="utf-8"
)

lines = text.splitlines()


# ==================================================
# HELPERS
# ==================================================

def indent_count(line):

    return (
        len(line)
        - len(line.lstrip())
    )


def method_positions(
    method_name,
):

    result = []

    needle = (
        f"def {method_name}("
    )

    for i, line in enumerate(lines):

        if line.strip().startswith(
            needle
        ):

            result.append(i)

    return result


def method_end(start):

    level = indent_count(
        lines[start]
    )

    for i in range(
        start + 1,
        len(lines),
    ):

        stripped = (
            lines[i].strip()
        )

        if (
            stripped.startswith("def ")
            and
            indent_count(lines[i]) == level
        ):

            return i

    return len(lines)


def assignment_end(start):

    balance = 0
    found_parenthesis = False

    for i in range(
        start,
        len(lines),
    ):

        for char in lines[i]:

            if char == "(":

                balance += 1
                found_parenthesis = True

            elif char == ")":

                balance -= 1


        if (
            found_parenthesis
            and
            balance == 0
        ):

            return i

    return None


changed = False


# ==================================================
# PART 1
# KIE -> LOCAL RANKING FALLBACK
# ==================================================

if any(
    "AI VISUAL FALLBACK ACTIVE"
    in line
    for line in lines
):

    print(
        "AI visual fallback: ALREADY PRESENT"
    )

else:

    methods = method_positions(
        "_search_and_select"
    )

    if not methods:

        raise RuntimeError(
            "Could not find _search_and_select()."
        )


    search_start = methods[-1]

    search_end = method_end(
        search_start
    )


    print(
        "_search_and_select():",
        search_start + 1,
        "to",
        search_end,
    )


    # ----------------------------------------------
    # Find AI visual ranking marker
    # ----------------------------------------------

    marker = None

    for i in range(
        search_start,
        search_end,
    ):

        if (
            "AI visual ranking..."
            in lines[i]
        ):

            marker = i
            break


    if marker is None:

        raise RuntimeError(
            "Could not locate "
            "'AI visual ranking...' marker."
        )


    # ----------------------------------------------
    # Find visual_ranked =
    # ----------------------------------------------

    visual_start = None

    for i in range(
        marker + 1,
        search_end,
    ):

        stripped = (
            lines[i].strip()
        )

        if (
            stripped.startswith(
                "visual_ranked"
            )
            and
            "=" in stripped
        ):

            visual_start = i
            break


    if visual_start is None:

        raise RuntimeError(
            "Could not find visual_ranked assignment."
        )


    visual_end = assignment_end(
        visual_start
    )


    if visual_end is None:

        raise RuntimeError(
            "Could not determine end of "
            "visual_ranked assignment."
        )


    print(
        "Visual ranking assignment:",
        visual_start + 1,
        "to",
        visual_end + 1,
    )


    indent = (
        lines[visual_start]
        [
            :
            indent_count(
                lines[visual_start]
            )
        ]
    )


    replacement = [

        indent
        + "# AI VISUAL FALLBACK ACTIVE",

        indent
        + "try:",

        "",

        indent
        + "    visual_ranked = (",

        indent
        + "        self.visual_ranker.rank(",

        indent
        + "            scene=scene,",

        indent
        + "            candidates=top_candidates,",

        indent
        + "            top_n=self.visual_top_n",

        indent
        + "        )",

        indent
        + "    )",

        "",

        indent
        + "    if not visual_ranked:",

        indent
        + "        raise RuntimeError(",

        indent
        + '            "Visual ranking returned no candidates."',

        indent
        + "        )",

        "",

        indent
        + "except Exception as error:",

        "",

        indent
        + '    if self.review_mode != "auto":',

        indent
        + "        raise",

        "",

        indent
        + "    print()",

        indent
        + '    print("=" * 70)',

        indent
        + '    print("AI VISUAL RANKING FALLBACK")',

        indent
        + '    print("=" * 70)',

        "",

        indent
        + "    print(",

        indent
        + '        "Visual AI unavailable:",',

        indent
        + "        type(error).__name__,",

        indent
        + "        str(error)",

        indent
        + "    )",

        "",

        indent
        + "    print(",

        indent
        + '        "Using local ranking for this scene."',

        indent
        + "    )",

        "",

        indent
        + "    visual_ranked = []",

        "",

        indent
        + "    for candidate in top_candidates:",

        "",

        indent
        + "        item = dict(candidate)",

        "",

        indent
        + "        try:",

        indent
        + "            local_score = float(",

        indent
        + '                item.get("score", 0)',

        indent
        + "                or 0",

        indent
        + "            )",

        indent
        + "        except (TypeError, ValueError):",

        indent
        + "            local_score = 0.0",

        "",

        indent
        + '        item["local_score"] = round(',

        indent
        + "            local_score,",

        indent
        + "            3",

        indent
        + "        )",

        "",

        indent
        + '        item["visual_score"] = None',

        "",

        indent
        + '        item["visual_reason"] = (',

        indent
        + '            "KIE unavailable - local ranking fallback."',

        indent
        + "        )",

        "",

        indent
        + '        item["final_score"] = round(',

        indent
        + "            local_score,",

        indent
        + "            3",

        indent
        + "        )",

        "",

        indent
        + '        item["ranking_fallback"] = (',

        indent
        + '            "local_only"',

        indent
        + "        )",

        "",

        indent
        + "        visual_ranked.append(",

        indent
        + "            item",

        indent
        + "        )",

        "",

        indent
        + "    visual_ranked.sort(",

        indent
        + "        key=lambda item: item.get(",

        indent
        + '            "final_score",',

        indent
        + "            0",

        indent
        + "        ),",

        indent
        + "        reverse=True",

        indent
        + "    )",
    ]


    lines[
        visual_start:
        visual_end + 1
    ] = replacement


    changed = True

    print(
        "AI visual fallback: ADDED"
    )


# ==================================================
# PART 2
# SEARCH RETRIES EXHAUSTED -> AUTO FALLBACK
# ==================================================

if any(
    "AUTO SEARCH EXHAUSTED FALLBACK"
    in line
    for line in lines
):

    print(
        "Search exhausted fallback: "
        "ALREADY PRESENT"
    )

else:

    # ----------------------------------------------
    # Find actual stable marker
    # ----------------------------------------------

    exhausted_matches = []

    for i, line in enumerate(lines):

        if (
            "Search retries exhausted."
            in line
        ):

            exhausted_matches.append(i)


    if not exhausted_matches:

        raise RuntimeError(
            "Could not locate "
            "'Search retries exhausted.'"
        )


    # Use last occurrence = current production code.

    exhausted_line = (
        exhausted_matches[-1]
    )


    print(
        "Search retries exhausted marker:",
        exhausted_line + 1,
    )


    # ----------------------------------------------
    # Walk upward to nearest:
    #
    # if (
    #     decision_name
    #     == "search_again"
    # ):
    # ----------------------------------------------

    if_start = None


    search_floor = max(
        0,
        exhausted_line - 100,
    )


    for i in range(
        exhausted_line,
        search_floor - 1,
        -1,
    ):

        if (
            lines[i].strip()
            == "if ("
        ):

            nearby = "\n".join(
                lines[
                    i:
                    min(
                        i + 15,
                        len(lines),
                    )
                ]
            )


            if (
                "decision_name"
                in nearby
                and
                "search_again"
                in nearby
            ):

                if_start = i
                break


    if if_start is None:

        raise RuntimeError(
            "Found Search retries exhausted, "
            "but could not find its "
            "decision_name == search_again block."
        )


    print(
        "search_again block starts:",
        if_start + 1,
    )


    indent = (
        lines[if_start]
        [
            :
            indent_count(
                lines[if_start]
            )
        ]
    )


    # ----------------------------------------------
    # Insert before original search_again failure.
    #
    # Convert search_again -> needs_review
    # only when review_mode=auto.
    #
    # Existing needs_review AUTO code below will
    # select visual_ranking[0] and proceed.
    # ----------------------------------------------

    block = [

        indent
        + "# AUTO SEARCH EXHAUSTED FALLBACK",

        indent
        + "if (",

        indent
        + '    decision_name == "search_again"',

        indent
        + "    and",

        indent
        + '    self.review_mode == "auto"',

        indent
        + "    and",

        indent
        + "    final_result.get(",

        indent
        + '        "visual_ranking"',

        indent
        + "    )",

        indent
        + "):",

        "",

        indent
        + "    print()",

        indent
        + '    print("=" * 70)',

        indent
        + '    print("AUTO FALLBACK AFTER SEARCH RETRIES")',

        indent
        + '    print("=" * 70)',

        "",

        indent
        + "    print(",

        indent
        + '        "Search quality threshold was not reached."',

        indent
        + "    )",

        "",

        indent
        + "    print(",

        indent
        + '        "AUTO mode will use the best available candidate."',

        indent
        + "    )",

        "",

        indent
        + "    decision = dict(",

        indent
        + "        decision",

        indent
        + "    )",

        "",

        indent
        + '    decision["original_decision"] = (',

        indent
        + '        "search_again"',

        indent
        + "    )",

        "",

        indent
        + '    decision["decision"] = (',

        indent
        + '        "needs_review"',

        indent
        + "    )",

        "",

        indent
        + '    decision["auto_fallback"] = (',

        indent
        + '        "search_retries_exhausted"',

        indent
        + "    )",

        "",

        indent
        + '    decision_name = "needs_review"',

        "",

        indent
        + '    stock["selection"]["decision"] = (',

        indent
        + '        "needs_review"',

        indent
        + "    )",

        "",

        indent
        + '    stock["selection"]["original_decision"] = (',

        indent
        + '        "search_again"',

        indent
        + "    )",

        "",

        indent
        + '    stock["selection"]["auto_fallback"] = (',

        indent
        + '        "search_retries_exhausted"',

        indent
        + "    )",

        "",
    ]


    lines[
        if_start:
        if_start
    ] = block


    changed = True

    print(
        "Search exhausted fallback: ADDED"
    )


# ==================================================
# BUILD FINAL SOURCE
# ==================================================

new_text = (
    "\n".join(lines)
    + "\n"
)


# ==================================================
# SAFETY CHECK
# ==================================================

required = [

    "AI VISUAL FALLBACK ACTIVE",

    "AI VISUAL RANKING FALLBACK",

    "Using local ranking for this scene.",

    "AUTO SEARCH EXHAUSTED FALLBACK",

    "AUTO FALLBACK AFTER SEARCH RETRIES",

    "search_retries_exhausted",
]


for fragment in required:

    if fragment not in new_text:

        raise RuntimeError(
            "Safety check failed: "
            + fragment
        )


# ==================================================
# WRITE
# ==================================================

if changed:

    TARGET.write_text(
        new_text,
        encoding="utf-8",
    )


# ==================================================
# COMPILE
# ==================================================

try:

    py_compile.compile(
        str(TARGET),
        doraise=True,
    )

except Exception as error:

    print()
    print("=" * 70)
    print("COMPILE FAILED")
    print("=" * 70)

    print(
        "Restoring V3 backup..."
    )


    shutil.copy2(
        BACKUP,
        TARGET,
    )


    raise RuntimeError(
        str(error)
    )


# ==================================================
# SUCCESS
# ==================================================

print()
print("=" * 70)
print("RESILIENT AUTO FALLBACK V3: PASS")
print("=" * 70)

print(
    "KIE failure -> local ranking fallback"
)

print(
    "Search retries exhausted -> "
    "AUTO best-candidate fallback"
)

print(
    "scene_pipeline.py compile: PASS"
)