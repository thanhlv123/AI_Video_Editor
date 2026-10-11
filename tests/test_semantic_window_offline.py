from pathlib import Path
import json
import sys


# ==================================================
# PROJECT
# ==================================================

ROOT = Path(
    r"D:\YouTubeTools\AI_Video_Editor"
)

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


# ==================================================
# MOROCCO MANIFEST
# ==================================================

MANIFEST = (
    ROOT
    / "projects"
    / "runs"
    / "morocco_88fd372c"
    / "ai_manifest.json"
)


FOCUS_IDS = {
    "scene_004",
    "scene_008",
    "scene_010",
    "scene_011",
}


print("=" * 78)
print("58C-3 SEMANTIC WINDOW OFFLINE TEST")
print("=" * 78)

print()
print("Manifest:")
print(MANIFEST)


if not MANIFEST.exists():
    raise FileNotFoundError(
        MANIFEST
    )


with open(
    MANIFEST,
    "r",
    encoding="utf-8",
) as file:

    manifest = json.load(
        file
    )


# ==================================================
# SPEECH SCENES
# ==================================================

scenes = [

    scene

    for scene in manifest.get(
        "scenes",
        [],
    )

    if scene.get(
        "scene_type",
        "speech",
    ) != "gap"
]


print()
print(
    "Speech scenes:",
    len(scenes),
)


scene_map = {

    scene.get(
        "scene_id"
    ):
        scene

    for scene in scenes
}


# ==================================================
# BUILD SEMANTIC WINDOW
# ==================================================

def build_semantic_window(
    previous_text,
    current_text,
    next_text,
):

    return (
        "SEMANTIC CONTEXT FOR STOCK ANALYSIS\n\n"

        "IMPORTANT RULES:\n"

        "- Analyze CURRENT NARRATION for the visual.\n"

        "- PREVIOUS and NEXT are context only.\n"

        "- Use neighboring text to resolve incomplete "
        "phrases, pronouns, subjects, locations, or "
        "sentences split by timing.\n"

        "- Do NOT blend an unrelated previous or next "
        "topic into the current visual.\n"

        "- If CURRENT continues a thought from PREVIOUS, "
        "inherit the missing subject or location.\n"

        "- If CURRENT ends mid-thought and NEXT completes "
        "that same thought, use NEXT only to understand "
        "the completion.\n\n"

        "PREVIOUS CONTEXT:\n"
        + (
            previous_text
            if previous_text
            else "[NONE]"
        )

        + "\n\n"

        "CURRENT NARRATION:\n"
        + current_text

        + "\n\n"

        "NEXT CONTEXT:\n"
        + (
            next_text
            if next_text
            else "[NONE]"
        )
    )


# ==================================================
# TEST
# ==================================================

passed = 0
failed = 0


for scene_id in [
    "scene_004",
    "scene_008",
    "scene_010",
    "scene_011",
]:

    scene = scene_map.get(
        scene_id
    )


    if scene is None:

        print()
        print(
            scene_id,
            "-> NOT FOUND"
        )

        failed += 1

        continue


    index = scenes.index(
        scene
    )


    current_text = str(
        scene.get(
            "dialogue",
            "",
        )
        or ""
    ).strip()


    previous_text = ""

    next_text = ""


    if index > 0:

        previous_text = str(
            scenes[
                index - 1
            ].get(
                "dialogue",
                "",
            )
            or ""
        ).strip()


    if (
        index + 1
        < len(scenes)
    ):

        next_text = str(
            scenes[
                index + 1
            ].get(
                "dialogue",
                "",
            )
            or ""
        ).strip()


    semantic_text = (
        build_semantic_window(
            previous_text,
            current_text,
            next_text,
        )
    )


    print()
    print("=" * 78)

    print(
        "SCENE:",
        scene_id,
    )

    print("=" * 78)


    print()
    print(
        "ORIGINAL DIALOGUE:"
    )

    print(
        current_text
    )


    print()
    print(
        "PREVIOUS:"
    )

    print(
        previous_text
        or
        "[NONE]"
    )


    print()
    print(
        "CURRENT:"
    )

    print(
        current_text
    )


    print()
    print(
        "NEXT:"
    )

    print(
        next_text
        or
        "[NONE]"
    )


    print()
    print(
        "SEMANTIC WINDOW:"
    )

    print(
        semantic_text
    )


    # ==================================================
    # VALIDATION
    # ==================================================

    checks = {

        "current_present":
            (
                current_text
                in semantic_text
            ),

        "previous_present":
            (
                not previous_text
                or
                previous_text
                in semantic_text
            ),

        "next_present":
            (
                not next_text
                or
                next_text
                in semantic_text
            ),

        "current_label":
            (
                "CURRENT NARRATION:"
                in semantic_text
            ),

        "previous_label":
            (
                "PREVIOUS CONTEXT:"
                in semantic_text
            ),

        "next_label":
            (
                "NEXT CONTEXT:"
                in semantic_text
            ),
    }


    scene_pass = all(
        checks.values()
    )


    print()
    print(
        "CHECKS:"
    )


    for name, value in checks.items():

        print(
            " ",
            name,
            "->",
            "PASS"
            if value
            else "FAIL",
        )


    print()

    print(
        "SCENE RESULT:",
        "PASS"
        if scene_pass
        else "FAIL",
    )


    if scene_pass:

        passed += 1

    else:

        failed += 1


# ==================================================
# SPECIAL SEMANTIC EXPECTATIONS
# ==================================================

print()
print("=" * 78)
print("SEMANTIC CONTINUITY CHECK")
print("=" * 78)


expectations = [

    (
        "scene_004",
        "wine industry",
    ),

    (
        "scene_008",
        "Casablanca",
    ),

    (
        "scene_010",
        "North",
    ),

    (
        "scene_011",
        "Arab armies entered North",
    ),
]


expect_pass = 0


for (
    scene_id,
    expected_text,
) in expectations:

    scene = scene_map[
        scene_id
    ]

    index = scenes.index(
        scene
    )


    previous_text = (
        str(
            scenes[
                index - 1
            ].get(
                "dialogue",
                "",
            )
            or ""
        ).strip()

        if index > 0
        else ""
    )


    current_text = str(
        scene.get(
            "dialogue",
            "",
        )
        or ""
    ).strip()


    next_text = (

        str(
            scenes[
                index + 1
            ].get(
                "dialogue",
                "",
            )
            or ""
        ).strip()

        if (
            index + 1
            < len(scenes)
        )

        else ""
    )


    semantic_text = (
        build_semantic_window(
            previous_text,
            current_text,
            next_text,
        )
    )


    found = (
        expected_text.lower()
        in semantic_text.lower()
    )


    if found:

        expect_pass += 1


    print(
        scene_id,
        "|",
        repr(
            expected_text
        ),
        "->",
        "PASS"
        if found
        else "FAIL",
    )


# ==================================================
# FINAL
# ==================================================

print()
print("=" * 78)
print("SUMMARY")
print("=" * 78)

print(
    "Focus scenes passed:",
    f"{passed}/4",
)

print(
    "Semantic continuity:",
    f"{expect_pass}/4",
)


print()


if (
    passed == 4
    and
    expect_pass == 4
):

    print(
        "SEMANTIC WINDOW OFFLINE TEST: PASS"
    )

else:

    print(
        "SEMANTIC WINDOW OFFLINE TEST: FAIL"
    )


print()
print(
    "Production files were NOT modified."
)