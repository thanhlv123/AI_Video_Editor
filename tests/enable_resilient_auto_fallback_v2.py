from pathlib import Path
import py_compile
import shutil

ROOT = Path(__file__).resolve().parent.parent

TARGET = (
    ROOT
    / "pipeline"
    / "scene_pipeline.py"
)

BACKUP = (
    ROOT
    / "pipeline"
    / "scene_pipeline_before_resilient_fallback_v2.py"
)


print("=" * 70)
print("ENABLE RESILIENT AUTO FALLBACK V2")
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

def leading_spaces(line):

    return (
        len(line)
        - len(line.lstrip())
    )


def find_method(
    method_name,
):

    matches = []

    for index, line in enumerate(
        lines
    ):

        if line.strip().startswith(
            f"def {method_name}("
        ):

            matches.append(
                index
            )

    if not matches:

        return None

    # Use last occurrence because old helper versions
    # may still exist above production code.

    return matches[-1]


def find_method_end(
    start_index,
):

    base_indent = leading_spaces(
        lines[start_index]
    )

    for index in range(
        start_index + 1,
        len(lines),
    ):

        stripped = lines[index].strip()

        if (
            stripped.startswith(
                "def "
            )
            and
            leading_spaces(
                lines[index]
            )
            == base_indent
        ):

            return index

    return len(lines)


def find_assignment_end(
    start_index,
):

    balance = 0
    started = False

    for index in range(
        start_index,
        len(lines),
    ):

        for char in lines[index]:

            if char == "(":

                balance += 1
                started = True

            elif char == ")":

                balance -= 1


        if (
            started
            and
            balance == 0
        ):

            return index

    return None


changed = False


# ==================================================
# LOCATE PRODUCTION _search_and_select()
# ==================================================

search_start = find_method(
    "_search_and_select"
)

if search_start is None:

    raise RuntimeError(
        "Could not find _search_and_select()."
    )


search_end = find_method_end(
    search_start
)


print(
    "_search_and_select():",
    search_start + 1,
    "to",
    search_end,
)


# ==================================================
# 1. KIE VISUAL FALLBACK
# ==================================================

already_visual_fallback = any(

    "AI VISUAL FALLBACK ACTIVE"
    in line

    for line in lines[
        search_start:
        search_end
    ]
)


if already_visual_fallback:

    print(
        "AI visual fallback: ALREADY PRESENT"
    )

else:

    # ----------------------------------------------
    # FIND "AI visual ranking..."
    # ----------------------------------------------

    visual_marker = None


    for index in range(
        search_start,
        search_end,
    ):

        if (
            "AI visual ranking..."
            in lines[index]
        ):

            visual_marker = index
            break


    if visual_marker is None:

        raise RuntimeError(
            "Could not locate "
            "AI visual ranking marker."
        )


    print(
        "AI visual marker:",
        visual_marker + 1,
    )


    # ----------------------------------------------
    # FIND visual_ranked assignment
    # ----------------------------------------------

    assignment_start = None


    for index in range(
        visual_marker + 1,
        search_end,
    ):

        stripped = (
            lines[index]
            .strip()
        )

        if (
            stripped.startswith(
                "visual_ranked"
            )
            and
            "=" in stripped
        ):

            assignment_start = index
            break


    if assignment_start is None:

        raise RuntimeError(
            "Could not locate "
            "visual_ranked assignment."
        )


    assignment_end = (
        find_assignment_end(
            assignment_start
        )
    )


    if assignment_end is None:

        raise RuntimeError(
            "Could not locate end of "
            "visual_ranked assignment."
        )


    print(
        "visual_ranked block:",
        assignment_start + 1,
        "to",
        assignment_end + 1,
    )


    indent = (
        lines[assignment_start]
        [
            :
            leading_spaces(
                lines[
                    assignment_start
                ]
            )
        ]
    )


    # ----------------------------------------------
    # NEW SAFE BLOCK
    # ----------------------------------------------

    fallback_block = [

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
        + '                item.get("score", 0) or 0',

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
        assignment_start:
        assignment_end + 1
    ] = fallback_block


    changed = True


    print(
        "AI visual fallback: ADDED"
    )


# ==================================================
# LOCATE PRODUCTION run()
# ==================================================

run_start = find_method(
    "run"
)

if run_start is None:

    raise RuntimeError(
        "Could not find run()."
    )


run_end = find_method_end(
    run_start
)


print(
    "Production run():",
    run_start + 1,
    "to",
    run_end,
)


# ==================================================
# 2. FINAL search_again FALLBACK
# ==================================================

already_search_fallback = any(

    "AUTO SEARCH EXHAUSTED FALLBACK"
    in line

    for line in lines[
        run_start:
        run_end
    ]
)


if already_search_fallback:

    print(
        "Search exhausted fallback: "
        "ALREADY PRESENT"
    )

else:

    # ----------------------------------------------
    # FIND COMMENT
    # ----------------------------------------------

    comment_index = None


    for index in range(
        run_start,
        run_end,
    ):

        if (
            "STILL SEARCH AGAIN"
            in lines[index]
        ):

            comment_index = index
            break


    if comment_index is None:

        raise RuntimeError(
            "Could not locate "
            "STILL SEARCH AGAIN block."
        )


    print(
        "STILL SEARCH AGAIN:",
        comment_index + 1,
    )


    # ----------------------------------------------
    # FIND NEXT if (
    # ----------------------------------------------

    if_start = None


    for index in range(
        comment_index + 1,
        run_end,
    ):

        if (
            lines[index].strip()
            == "if ("
        ):

            if_start = index
            break


    if if_start is None:

        raise RuntimeError(
            "Could not locate "
            "search_again if block."
        )


    indent = (
        lines[if_start]
        [
            :
            leading_spaces(
                lines[if_start]
            )
        ]
    )


    # ----------------------------------------------
    # INSERT BEFORE EXISTING search_again CHECK
    # ----------------------------------------------

    auto_fallback = [

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
        + '    decision_name = "needs_review"',

        "",

        indent
        + "    decision = dict(",

        indent
        + "        decision",

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
        + '    stock["selection"]["decision"] = (',

        indent
        + '        "needs_review"',

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
    ] = auto_fallback


    changed = True


    print(
        "Search exhausted fallback: ADDED"
    )


# ==================================================
# BUILD SOURCE
# ==================================================

new_text = (
    "\n".join(lines)
    + "\n"
)


# ==================================================
# SAFETY CHECKS
# ==================================================

required_fragments = [

    "AI VISUAL FALLBACK ACTIVE",

    "AI VISUAL RANKING FALLBACK",

    "ranking_fallback",

    "AUTO SEARCH EXHAUSTED FALLBACK",

    "AUTO FALLBACK AFTER SEARCH RETRIES",

    "search_retries_exhausted",
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

if changed:

    TARGET.write_text(
        new_text,
        encoding="utf-8",
    )


# ==================================================
# COMPILE PRODUCTION FILE
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
        "Restoring V2 backup..."
    )

    shutil.copy2(
        BACKUP,
        TARGET,
    )

    raise RuntimeError(
        str(error)
    )


print()
print("=" * 70)
print("RESILIENT AUTO FALLBACK V2: PASS")
print("=" * 70)

print(
    "KIE failure -> local ranking fallback"
)

print(
    "Final search_again -> AUTO best-candidate fallback"
)

print(
    "scene_pipeline.py compile: PASS"
)