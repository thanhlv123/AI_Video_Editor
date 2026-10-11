from pathlib import Path
import shutil
import py_compile


ROOT = Path(__file__).resolve().parent.parent

TARGET = (
    ROOT
    / "pipeline"
    / "scene_pipeline.py"
)

BACKUP = (
    ROOT
    / "pipeline"
    / "scene_pipeline_before_resilient_fallback_v5.py"
)


print("=" * 70)
print("ENABLE RESILIENT AUTO FALLBACK V5")
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


def find_last_method(name):

    matches = []

    needle = (
        f"def {name}("
    )

    for index, line in enumerate(lines):

        if line.strip().startswith(
            needle
        ):

            matches.append(index)

    if not matches:
        return None

    return matches[-1]


def find_method_end(start):

    method_indent = indent_count(
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
            indent_count(lines[index])
            == method_indent
        ):

            return index

    return len(lines)


def find_expression_end(start):

    round_balance = 0
    square_balance = 0
    curly_balance = 0

    started = False

    for index in range(
        start,
        len(lines),
    ):

        for char in lines[index]:

            if char == "(":
                round_balance += 1
                started = True

            elif char == ")":
                round_balance -= 1

            elif char == "[":
                square_balance += 1
                started = True

            elif char == "]":
                square_balance -= 1

            elif char == "{":
                curly_balance += 1
                started = True

            elif char == "}":
                curly_balance -= 1


        if (
            started
            and
            round_balance == 0
            and
            square_balance == 0
            and
            curly_balance == 0
        ):

            return index

    return None


changed = False


# ==================================================
# PART 1
# KIE TRANSIENT ERROR -> LOCAL RANKING
# ==================================================

if any(
    "AI VISUAL FALLBACK V5"
    in line
    for line in lines
):

    print(
        "KIE fallback: ALREADY PRESENT"
    )

else:

    search_start = find_last_method(
        "_search_and_select"
    )

    if search_start is None:

        raise RuntimeError(
            "Could not find "
            "_search_and_select()."
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


    visual_start = None


    for index in range(
        search_start,
        search_end,
    ):

        stripped = (
            lines[index].strip()
        )

        if stripped.startswith(
            "visual_ranked = ("
        ):

            visual_start = index
            break


    if visual_start is None:

        raise RuntimeError(
            "Could not find "
            "visual_ranked assignment."
        )


    visual_end = find_expression_end(
        visual_start
    )


    if visual_end is None:

        raise RuntimeError(
            "Could not determine "
            "visual_ranked assignment end."
        )


    print(
        "Visual block:",
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


    visual_patch = [

        indent
        + "# AI VISUAL FALLBACK V5",

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
        + "            top_n=self.visual_top_n,",

        indent
        + "        )",

        indent
        + "    )",

        "",

        indent
        + "except Exception as error:",

        "",

        indent
        + "    error_text = str(",

        indent
        + "        error",

        indent
        + "    ).lower()",

        "",

        indent
        + "    transient_error = any(",

        indent
        + "        token in error_text",

        indent
        + "        for token in (",

        indent
        + '            "http 429",',

        indent
        + '            "http 500",',

        indent
        + '            "http 502",',

        indent
        + '            "http 503",',

        indent
        + '            "http 504",',

        indent
        + '            "server_error",',

        indent
        + '            "server exception",',

        indent
        + '            "timeout",',

        indent
        + '            "timed out",',

        indent
        + '            "connection",',

        indent
        + "        )",

        indent
        + "    )",

        "",

        indent
        + "    if (",

        indent
        + '        self.review_mode != "auto"',

        indent
        + "        or not transient_error",

        indent
        + "    ):",

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
        + '        "KIE unavailable after retries:",',

        indent
        + "        str(error),",

        indent
        + "    )",

        "",

        indent
        + "    print(",

        indent
        + '        "Using LOCAL ranking for this scene."',

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
        + "        item = dict(",

        indent
        + "            candidate",

        indent
        + "        )",

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
        + "        except (",

        indent
        + "            TypeError,",

        indent
        + "            ValueError,",

        indent
        + "        ):",

        indent
        + "            local_score = 0.0",

        "",

        indent
        + '        item["local_score"] = (',

        indent
        + "            round(",

        indent
        + "                local_score,",

        indent
        + "                3,",

        indent
        + "            )",

        indent
        + "        )",

        "",

        indent
        + '        item["visual_score"] = None',

        "",

        indent
        + '        item["visual_reason"] = (',

        indent
        + '            "KIE transient failure; "',

        indent
        + '            "local-ranking fallback used."',

        indent
        + "        )",

        "",

        indent
        + '        item["final_score"] = (',

        indent
        + "            round(",

        indent
        + "                local_score,",

        indent
        + "                3,",

        indent
        + "            )",

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
        + "        key=lambda item: (",

        indent
        + "            item.get(",

        indent
        + '                "final_score",',

        indent
        + "                0,",

        indent
        + "            )",

        indent
        + "        ),",

        indent
        + "        reverse=True,",

        indent
        + "    )",
    ]


    lines[
        visual_start:
        visual_end + 1
    ] = visual_patch


    changed = True


    print(
        "KIE fallback: ADDED"
    )


# ==================================================
# PART 2
# FINAL SEARCH_AGAIN -> AUTO NEEDS_REVIEW
# ==================================================

if any(
    "AUTO SEARCH FALLBACK V5"
    in line
    for line in lines
):

    print(
        "Search fallback: ALREADY PRESENT"
    )

else:

    # Recalculate because part 1 changed line counts.

    run_start = find_last_method(
        "run"
    )

    if run_start is None:

        raise RuntimeError(
            "Could not find production run()."
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


    # ----------------------------------------------
    # Find SEARCH AGAIN comment
    # ----------------------------------------------

    search_marker = None


    for index in range(
        run_start,
        run_end,
    ):

        if (
            lines[index].strip()
            == "# SEARCH AGAIN"
        ):

            search_marker = index
            break


    if search_marker is None:

        raise RuntimeError(
            "Could not find # SEARCH AGAIN."
        )


    # ----------------------------------------------
    # Find corresponding if (
    # ----------------------------------------------

    search_if = None


    for index in range(
        search_marker + 1,
        min(
            search_marker + 20,
            run_end,
        ),
    ):

        if (
            lines[index].strip()
            == "if ("
        ):

            nearby = "\n".join(
                lines[
                    index:
                    index + 10
                ]
            )

            if (
                "decision_name"
                in nearby
                and
                "search_again"
                in nearby
            ):

                search_if = index
                break


    if search_if is None:

        raise RuntimeError(
            "Could not find "
            "decision_name == search_again block."
        )


    # ----------------------------------------------
    # Find SAFE MODE REVIEW marker
    # ----------------------------------------------

    safe_marker = None


    for index in range(
        search_if + 1,
        run_end,
    ):

        if (
            lines[index].strip()
            == "# SAFE MODE REVIEW"
        ):

            safe_marker = index
            break


    if safe_marker is None:

        raise RuntimeError(
            "Could not find # SAFE MODE REVIEW."
        )


    # Keep separator immediately before SAFE MODE REVIEW.

    block_end = safe_marker


    while (
        block_end > search_if
        and
        (
            lines[
                block_end - 1
            ].strip() == ""
            or
            lines[
                block_end - 1
            ].strip().startswith(
                "# ==="
            )
        )
    ):

        block_end -= 1


    print(
        "Search-again block:",
        search_if + 1,
        "to",
        block_end,
    )


    indent = (
        lines[search_if]
        [
            :
            indent_count(
                lines[search_if]
            )
        ]
    )


    search_patch = [

        indent
        + "if (",

        indent
        + "    decision_name",

        indent
        + '    == "search_again"',

        indent
        + "):",

        "",

        indent
        + "    history_entry[",

        indent
        + '        "status"',

        indent
        + '    ] = "search_again"',

        "",

        indent
        + "    search_history.append(",

        indent
        + "        history_entry",

        indent
        + "    )",

        "",

        indent
        + "    retry_scene = (",

        indent
        + "        self._prepare_retry(",

        indent
        + "            scene=scene,",

        indent
        + "            attempt=attempt,",

        indent
        + "        )",

        indent
        + "    )",

        "",

        indent
        + "    if retry_scene is not None:",

        "",

        indent
        + "        current_scene = (",

        indent
        + "            retry_scene",

        indent
        + "        )",

        "",

        indent
        + "        attempt += 1",

        "",

        indent
        + "        continue",

        "",

        indent
        + "    # AUTO SEARCH FALLBACK V5",

        indent
        + "    if (",

        indent
        + '        self.review_mode == "auto"',

        indent
        + "        and",

        indent
        + "        result.get(",

        indent
        + '            "visual_ranking"',

        indent
        + "        )",

        indent
        + "    ):",

        "",

        indent
        + "        print()",

        indent
        + '        print("=" * 70)',

        indent
        + '        print("AUTO FALLBACK AFTER SEARCH RETRIES")',

        indent
        + '        print("=" * 70)',

        "",

        indent
        + "        print(",

        indent
        + '            "Search threshold was not reached."',

        indent
        + "        )",

        "",

        indent
        + "        print(",

        indent
        + '            "Using best available candidate in AUTO mode."',

        indent
        + "        )",

        "",

        indent
        + "        decision = dict(",

        indent
        + "            decision",

        indent
        + "        )",

        "",

        indent
        + '        decision["original_decision"] = (',

        indent
        + '            "search_again"',

        indent
        + "        )",

        "",

        indent
        + '        decision["decision"] = (',

        indent
        + '            "needs_review"',

        indent
        + "        )",

        "",

        indent
        + '        decision["auto_fallback"] = (',

        indent
        + '            "search_retries_exhausted"',

        indent
        + "        )",

        "",

        indent
        + '        decision["reason"] = (',

        indent
        + "            str(",

        indent
        + "                decision.get(",

        indent
        + '                    "reason",',

        indent
        + '                    "",',

        indent
        + "                )",

        indent
        + "            )",

        indent
        + '            + " | AUTO fallback after "',

        indent
        + '            + "search retries exhausted."',

        indent
        + "        )",

        "",

        indent
        + '        decision_name = "needs_review"',

        "",

        indent
        + '        result["decision"] = decision',

        "",

        indent
        + "        history_entry[",

        indent
        + '            "status"',

        indent
        + '        ] = "auto_fallback"',

        "",

        indent
        + "        history_entry[",

        indent
        + '            "auto_fallback"',

        indent
        + "        ] = (",

        indent
        + '            "search_retries_exhausted"',

        indent
        + "        )",

        "",

        indent
        + "        search_history[-1] = (",

        indent
        + "            history_entry",

        indent
        + "        )",

        "",

        indent
        + "    else:",

        "",

        indent
        + "        stock[",

        indent
        + '            "candidates"',

        indent
        + "        ] = result[",

        indent
        + '            "candidates"',

        indent
        + "        ]",

        "",

        indent
        + "        stock[",

        indent
        + '            "visual_ranking"',

        indent
        + "        ] = result[",

        indent
        + '            "visual_ranking"',

        indent
        + "        ]",

        "",

        indent
        + "        stock[",

        indent
        + '            "search_history"',

        indent
        + "        ] = search_history",

        "",

        indent
        + "        stock[",

        indent
        + '            "selected_media"',

        indent
        + "        ] = None",

        "",

        indent
        + "        stock[",

        indent
        + '            "status"',

        indent
        + '        ] = "search_again"',

        "",

        indent
        + "        return {",

        "",

        indent
        + '            "success":',

        indent
        + "                False,",

        "",

        indent
        + '            "scene_id":',

        indent
        + "                scene_id,",

        "",

        indent
        + '            "status":',

        indent
        + '                "search_again",',

        "",

        indent
        + '            "decision":',

        indent
        + "                decision,",

        indent
        + "        }",
    ]


    lines[
        search_if:
        block_end
    ] = search_patch


    changed = True


    print(
        "Search fallback: ADDED"
    )


# ==================================================
# VALIDATE BEFORE WRITING
# ==================================================

new_text = (
    "\n".join(lines)
    + "\n"
)


required = [

    "AI VISUAL FALLBACK V5",

    "AI VISUAL RANKING FALLBACK",

    "AUTO SEARCH FALLBACK V5",

    "AUTO FALLBACK AFTER SEARCH RETRIES",

    "search_retries_exhausted",
]


for marker in required:

    if marker not in new_text:

        raise RuntimeError(
            "Missing patch marker: "
            + marker
        )


# Compile entirely in memory BEFORE touching production.

try:

    compile(
        new_text,
        str(TARGET),
        "exec",
    )

except Exception as error:

    raise RuntimeError(
        "Patched source failed "
        "in-memory compile: "
        + str(error)
    )


print(
    "In-memory compile: PASS"
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
# FINAL COMPILE
# ==================================================

try:

    py_compile.compile(
        str(TARGET),
        doraise=True,
    )

except Exception as error:

    print(
        "Production compile failed."
    )

    print(
        "Restoring backup..."
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
print("RESILIENT AUTO FALLBACK V5: PASS")
print("=" * 70)

print(
    "KIE transient failure -> LOCAL ranking"
)

print(
    "Final search_again -> AUTO best candidate"
)

print(
    "scene_pipeline.py compile -> PASS"
)