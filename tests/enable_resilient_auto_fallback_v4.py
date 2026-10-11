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
    / "scene_pipeline_before_resilient_fallback_v4.py"
)


print("=" * 70)
print("ENABLE RESILIENT AUTO FALLBACK V4")
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
    name,
):

    result = []

    needle = f"def {name}("

    for index, line in enumerate(lines):

        if line.strip().startswith(
            needle
        ):

            result.append(
                index
            )

    return result


def method_end(
    start,
):

    level = indent_count(
        lines[start]
    )

    for index in range(
        start + 1,
        len(lines),
    ):

        stripped = (
            lines[index].strip()
        )

        if (
            stripped.startswith("def ")
            and
            indent_count(
                lines[index]
            )
            == level
        ):

            return index

    return len(lines)


def expression_end(
    start,
):

    """
    Find end of a multi-line assignment/expression by
    balancing (), [] and {}.
    """

    round_balance = 0
    square_balance = 0
    curly_balance = 0

    saw_bracket = False


    for index in range(
        start,
        len(lines),
    ):

        line = lines[index]


        for char in line:

            if char == "(":

                round_balance += 1
                saw_bracket = True

            elif char == ")":

                round_balance -= 1

            elif char == "[":

                square_balance += 1
                saw_bracket = True

            elif char == "]":

                square_balance -= 1

            elif char == "{":

                curly_balance += 1
                saw_bracket = True

            elif char == "}":

                curly_balance -= 1


        if saw_bracket:

            if (
                round_balance == 0
                and
                square_balance == 0
                and
                curly_balance == 0
            ):

                return index

        else:

            if "=" in line:

                return index


    return None


changed = False


# ==================================================
# PART 1
# KIE ERROR -> LOCAL RANKING
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

    search_methods = (
        method_positions(
            "_search_and_select"
        )
    )


    if not search_methods:

        raise RuntimeError(
            "Could not find "
            "_search_and_select()."
        )


    search_start = (
        search_methods[-1]
    )

    search_end = (
        method_end(
            search_start
        )
    )


    print(
        "_search_and_select():",
        search_start + 1,
        "to",
        search_end,
    )


    # ----------------------------------------------
    # AI visual ranking marker
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


    # ----------------------------------------------
    # visual_ranked assignment
    # ----------------------------------------------

    visual_start = None


    for index in range(
        visual_marker + 1,
        search_end,
    ):

        stripped = (
            lines[index].strip()
        )

        if (
            stripped.startswith(
                "visual_ranked"
            )
            and
            "=" in stripped
        ):

            visual_start = index
            break


    if visual_start is None:

        raise RuntimeError(
            "Could not locate "
            "visual_ranked assignment."
        )


    visual_end = (
        expression_end(
            visual_start
        )
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


    visual_fallback = [

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
    ] = visual_fallback


    changed = True


    print(
        "AI visual fallback: ADDED"
    )


# ==================================================
# PART 2
# FINAL search_again -> AUTO FALLBACK
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

    # Need recalculate method positions because
    # Part 1 may have changed line numbers.

    run_methods = (
        method_positions(
            "run"
        )
    )


    if not run_methods:

        raise RuntimeError(
            "Could not find run()."
        )


    run_start = (
        run_methods[-1]
    )

    run_end = (
        method_end(
            run_start
        )
    )


    print(
        "Production run():",
        run_start + 1,
        "to",
        run_end,
    )


    # ----------------------------------------------
    # Locate:
    #
    # decision = final_result[
    #     "decision"
    # ]
    # ----------------------------------------------

    final_decision_start = None


    for index in range(
        run_start,
        run_end,
    ):

        stripped = (
            lines[index]
            .strip()
            .replace(" ", "")
        )

        if (
            stripped.startswith(
                "decision=final_result["
            )
        ):

            final_decision_start = index
            break


    if final_decision_start is None:

        raise RuntimeError(
            "Could not locate "
            "decision = final_result[...] "
            "inside production run()."
        )


    final_decision_end = (
        expression_end(
            final_decision_start
        )
    )


    print(
        "Final decision assignment:",
        final_decision_start + 1,
        "to",
        final_decision_end + 1,
    )


    # ----------------------------------------------
    # Locate NEXT decision_name assignment.
    # ----------------------------------------------

    decision_name_start = None


    for index in range(
        final_decision_end + 1,
        min(
            final_decision_end + 30,
            run_end,
        ),
    ):

        stripped = (
            lines[index]
            .strip()
            .replace(" ", "")
        )

        if stripped.startswith(
            "decision_name=decision["
        ):

            decision_name_start = index
            break


    if decision_name_start is None:

        raise RuntimeError(
            "Could not locate final "
            "decision_name = decision[...] assignment."
        )


    decision_name_end = (
        expression_end(
            decision_name_start
        )
    )


    if decision_name_end is None:

        raise RuntimeError(
            "Could not determine end of "
            "decision_name assignment."
        )


    print(
        "Final decision_name assignment:",
        decision_name_start + 1,
        "to",
        decision_name_end + 1,
    )


    indent = (
        lines[decision_name_start]
        [
            :
            indent_count(
                lines[
                    decision_name_start
                ]
            )
        ]
    )


    # ==================================================
    # IMPORTANT:
    #
    # This code is AFTER the retry loop.
    # Therefore if decision is still search_again,
    # all configured search attempts are exhausted.
    # ==================================================

    auto_search_fallback = [

        "",

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
        + '    decision["reason"] = (',

        indent
        + '        str(decision.get("reason", ""))',

        indent
        + '        + " | AUTO fallback after search retries exhausted."',

        indent
        + "    )",

        "",

        indent
        + '    decision_name = "needs_review"',

        "",

        indent
        + '    final_result["decision"] = (',

        indent
        + "        decision",

        indent
        + "    )",
    ]


    insert_at = (
        decision_name_end
        + 1
    )


    lines[
        insert_at:
        insert_at
    ] = auto_search_fallback


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
# SAFETY CHECK
# ==================================================

required = [

    "AI VISUAL FALLBACK ACTIVE",

    "AI VISUAL RANKING FALLBACK",

    "Using local ranking for this scene.",

    "ranking_fallback",

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
        "Restoring V4 backup..."
    )

    shutil.copy2(
        BACKUP,
        TARGET,
    )

    raise RuntimeError(
        str(error)
    )


# ==================================================
# FINAL VERIFY FROM WRITTEN FILE
# ==================================================

written = TARGET.read_text(
    encoding="utf-8"
)


if (
    "AI VISUAL FALLBACK ACTIVE"
    not in written
):

    raise RuntimeError(
        "Written file is missing "
        "AI visual fallback."
    )


if (
    "AUTO SEARCH EXHAUSTED FALLBACK"
    not in written
):

    raise RuntimeError(
        "Written file is missing "
        "search exhausted fallback."
    )


print()
print("=" * 70)
print("RESILIENT AUTO FALLBACK V4: PASS")
print("=" * 70)

print(
    "1. KIE failure -> local ranking"
)

print(
    "2. search_again after all retries "
    "-> AUTO best candidate"
)

print(
    "3. scene_pipeline.py compile -> PASS"
)