from pathlib import Path
import py_compile
import re
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
    / "scene_pipeline_before_resilient_fallback.py"
)


print("=" * 70)
print("ENABLE RESILIENT AUTO FALLBACK")
print("=" * 70)


if not TARGET.exists():

    raise FileNotFoundError(
        TARGET
    )


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


changed = False


# ==================================================
# 1. KIE VISUAL FALLBACK
# ==================================================

if "AI VISUAL FALLBACK ACTIVE" in text:

    print(
        "AI visual fallback: ALREADY PRESENT"
    )

else:

    pattern = re.compile(
        r'''
        (?P<indent>[ \t]+)
        visual_ranked[ \t]*=[ \t]*\(
        \s*
        self\.visual_ranker\.rank\(
        \s*
        scene=scene,
        \s*
        candidates=top_candidates,
        \s*
        top_n=self\.visual_top_n
        \s*
        \)
        \s*
        \)
        ''',
        re.VERBOSE,
    )


    match = pattern.search(
        text
    )


    if not match:

        raise RuntimeError(
            "Could not locate visual_ranker.rank() block."
        )


    indent = match.group(
        "indent"
    )


    replacement = (
        indent
        + "# AI VISUAL FALLBACK ACTIVE\n"
        + indent
        + "try:\n\n"
        + indent
        + "    visual_ranked = (\n"
        + indent
        + "        self.visual_ranker.rank(\n"
        + indent
        + "            scene=scene,\n"
        + indent
        + "            candidates=top_candidates,\n"
        + indent
        + "            top_n=self.visual_top_n\n"
        + indent
        + "        )\n"
        + indent
        + "    )\n\n"
        + indent
        + "except Exception as error:\n\n"
        + indent
        + "    if self.review_mode != \"auto\":\n"
        + indent
        + "        raise\n\n"
        + indent
        + "    print()\n"
        + indent
        + "    print(\"=\" * 70)\n"
        + indent
        + "    print(\"AI VISUAL RANKING FALLBACK\")\n"
        + indent
        + "    print(\"=\" * 70)\n\n"
        + indent
        + "    print(\n"
        + indent
        + "        \"Visual AI unavailable:\",\n"
        + indent
        + "        type(error).__name__,\n"
        + indent
        + "        str(error)\n"
        + indent
        + "    )\n\n"
        + indent
        + "    print(\n"
        + indent
        + "        \"Using local ranking for this scene.\"\n"
        + indent
        + "    )\n\n"
        + indent
        + "    visual_ranked = []\n\n"
        + indent
        + "    for candidate in top_candidates:\n\n"
        + indent
        + "        item = dict(candidate)\n\n"
        + indent
        + "        try:\n"
        + indent
        + "            local_score = float(\n"
        + indent
        + "                item.get(\"score\", 0) or 0\n"
        + indent
        + "            )\n"
        + indent
        + "        except (TypeError, ValueError):\n"
        + indent
        + "            local_score = 0.0\n\n"
        + indent
        + "        item[\"local_score\"] = round(\n"
        + indent
        + "            local_score,\n"
        + indent
        + "            3\n"
        + indent
        + "        )\n\n"
        + indent
        + "        item[\"visual_score\"] = None\n"
        + indent
        + "        item[\"visual_reason\"] = (\n"
        + indent
        + "            \"KIE unavailable - local ranking fallback.\"\n"
        + indent
        + "        )\n\n"
        + indent
        + "        # In fallback mode the local score becomes\n"
        + indent
        + "        # the final score so the normal selector can\n"
        + indent
        + "        # continue operating.\n"
        + indent
        + "        item[\"final_score\"] = round(\n"
        + indent
        + "            local_score,\n"
        + indent
        + "            3\n"
        + indent
        + "        )\n\n"
        + indent
        + "        item[\"ranking_fallback\"] = (\n"
        + indent
        + "            \"local_only\"\n"
        + indent
        + "        )\n\n"
        + indent
        + "        visual_ranked.append(item)\n\n"
        + indent
        + "    visual_ranked.sort(\n"
        + indent
        + "        key=lambda item: item.get(\n"
        + indent
        + "            \"final_score\",\n"
        + indent
        + "            0\n"
        + indent
        + "        ),\n"
        + indent
        + "        reverse=True\n"
        + indent
        + "    )\n"
    )


    text = (
        text[:match.start()]
        + replacement
        + text[match.end():]
    )


    changed = True

    print(
        "AI visual fallback: ADDED"
    )


# ==================================================
# 2. SEARCH-AGAIN FINAL AUTO FALLBACK
# ==================================================

if "AUTO SEARCH EXHAUSTED FALLBACK" in text:

    print(
        "Search exhausted fallback: ALREADY PRESENT"
    )

else:

    pattern = re.compile(
        r'''
        (?P<indent>[ \t]+)
        decision[ \t]*=[ \t]*self\.selector\.decide\(
        \s*
        visual_ranked
        \s*
        \)
        ''',
        re.VERBOSE,
    )


    matches = list(
        pattern.finditer(
            text
        )
    )


    if not matches:

        raise RuntimeError(
            "Could not locate self.selector.decide() block."
        )


    # Current production ScenePipeline uses the selector
    # inside _search_and_select(). Patch the LAST match
    # to avoid old/unused helper implementations if present.

    match = matches[-1]

    indent = match.group(
        "indent"
    )


    original = match.group(
        0
    )


    addition = (
        original
        + "\n\n"
        + indent
        + "# AUTO SEARCH EXHAUSTED FALLBACK\n"
        + indent
        + "if (\n"
        + indent
        + "    self.review_mode == \"auto\"\n"
        + indent
        + "    and\n"
        + indent
        + "    attempt >= self.max_search_retries\n"
        + indent
        + "    and\n"
        + indent
        + "    decision.get(\"decision\") == \"search_again\"\n"
        + indent
        + "    and\n"
        + indent
        + "    visual_ranked\n"
        + indent
        + "):\n\n"
        + indent
        + "    print()\n"
        + indent
        + "    print(\"=\" * 70)\n"
        + indent
        + "    print(\"AUTO FALLBACK AFTER SEARCH RETRIES\")\n"
        + indent
        + "    print(\"=\" * 70)\n\n"
        + indent
        + "    print(\n"
        + indent
        + "        \"Search quality threshold was not reached.\"\n"
        + indent
        + "    )\n\n"
        + indent
        + "    print(\n"
        + indent
        + "        \"AUTO mode will use the best available candidate.\"\n"
        + indent
        + "    )\n\n"
        + indent
        + "    original_reason = str(\n"
        + indent
        + "        decision.get(\"reason\", \"\")\n"
        + indent
        + "    )\n\n"
        + indent
        + "    decision = dict(decision)\n\n"
        + indent
        + "    decision[\"decision\"] = \"needs_review\"\n\n"
        + indent
        + "    decision[\"reason\"] = (\n"
        + indent
        + "        original_reason\n"
        + indent
        + "        + \" | AUTO fallback after search retries exhausted.\"\n"
        + indent
        + "    )\n\n"
        + indent
        + "    decision[\"auto_fallback\"] = (\n"
        + indent
        + "        \"search_retries_exhausted\"\n"
        + indent
        + "    )\n"
    )


    text = (
        text[:match.start()]
        + addition
        + text[match.end():]
    )


    changed = True

    print(
        "Search exhausted fallback: ADDED"
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

    if fragment not in text:

        raise RuntimeError(
            "Safety check failed: "
            + fragment
        )


# ==================================================
# WRITE
# ==================================================

if changed:

    TARGET.write_text(
        text,
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
        str(error)
    )


print()
print("=" * 70)
print("RESILIENT AUTO FALLBACK: PASS")
print("=" * 70)

print(
    "KIE failure -> local ranking fallback"
)

print(
    "Final search_again -> best candidate in AUTO mode"
)

print(
    "scene_pipeline.py compile: PASS"
)