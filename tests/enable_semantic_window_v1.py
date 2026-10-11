from pathlib import Path
import py_compile
import shutil


# ==================================================
# PATHS
# ==================================================

ROOT = Path(
    r"D:\YouTubeTools\AI_Video_Editor"
)

TARGET = (
    ROOT
    / "pipeline"
    / "full_video_pipeline.py"
)

BACKUP = (
    ROOT
    / "pipeline"
    / "full_video_pipeline_before_semantic_window_v1.py"
)


print("=" * 78)
print("ENABLE SEMANTIC WINDOW V1")
print("=" * 78)


# ==================================================
# VERIFY TARGET
# ==================================================

if not TARGET.exists():

    raise FileNotFoundError(
        TARGET
    )


original = TARGET.read_text(
    encoding="utf-8"
)


# ==================================================
# ALREADY INSTALLED?
# ==================================================

if (
    "SEMANTIC WINDOW 58C V1"
    in original
):

    print()
    print(
        "SEMANTIC WINDOW 58C V1 already installed."
    )

    print(
        "No changes made."
    )

    raise SystemExit(
        0
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


# ==================================================
# FIND PRODUCTION LOOP
# ==================================================

old_block = '''        analyses = []

        for index, scene in enumerate(
            speech_scenes,
            start=1,
        ):

            print()
            print(
                f"AI scene "
                f"{index}/"
                f"{len(speech_scenes)}: "
                f"{scene.id}"
            )

            result = batch.analyze_one(

                scene=scene,

                use_cache=True,
            )

            analyses.append(
                result
            )
'''


if old_block not in original:

    raise RuntimeError(
        "Could not locate the exact "
        "_run_ai_stage analysis loop.\n"
        "Production file was NOT modified."
    )


# ==================================================
# NEW SEMANTIC LOOP
# ==================================================

new_block = '''        analyses = []

        # ==================================================
        # SEMANTIC WINDOW 58C V1
        #
        # Scene timing and original dialogue remain unchanged.
        #
        # AI temporarily receives:
        #
        # PREVIOUS CONTEXT
        # CURRENT NARRATION
        # NEXT CONTEXT
        #
        # This helps resolve fragments caused by time-based
        # SceneBuilder splitting without changing the timeline.
        # ==================================================

        for index, scene in enumerate(
            speech_scenes,
            start=1,
        ):

            print()
            print(
                f"AI scene "
                f"{index}/"
                f"{len(speech_scenes)}: "
                f"{scene.id}"
            )

            # ----------------------------------------------
            # NEIGHBOR TEXT
            # ----------------------------------------------

            previous_text = ""

            next_text = ""


            if index > 1:

                previous_scene = (
                    speech_scenes[
                        index - 2
                    ]
                )

                previous_text = str(
                    previous_scene.text
                    or ""
                ).strip()


            if index < len(
                speech_scenes
            ):

                next_scene = (
                    speech_scenes[
                        index
                    ]
                )

                next_text = str(
                    next_scene.text
                    or ""
                ).strip()


            current_text = str(
                scene.text
                or ""
            ).strip()


            # ----------------------------------------------
            # CREATE TEMPORARY AI SCENE
            #
            # deepcopy keeps:
            # id
            # start/end
            # duration
            # subtitle IDs
            #
            # Only text is temporarily expanded.
            # ----------------------------------------------

            semantic_scene = (
                copy.deepcopy(
                    scene
                )
            )


            semantic_scene.text = (
                "SEMANTIC CONTEXT FOR STOCK ANALYSIS\\n\\n"

                "IMPORTANT RULES:\\n"
                "- Analyze CURRENT NARRATION for the visual.\\n"
                "- PREVIOUS and NEXT are context only.\\n"
                "- Use neighboring text to resolve incomplete "
                "phrases, pronouns, subjects, locations, or "
                "sentences split by timing.\\n"
                "- Do NOT blend an unrelated previous or next "
                "topic into the current visual.\\n"
                "- If CURRENT continues a thought from PREVIOUS, "
                "inherit the missing subject or location.\\n"
                "- If CURRENT ends mid-thought and NEXT completes "
                "that same thought, use NEXT only to understand "
                "the completion.\\n\\n"

                "PREVIOUS CONTEXT:\\n"
                + (
                    previous_text
                    if previous_text
                    else "[NONE]"
                )

                + "\\n\\n"

                "CURRENT NARRATION:\\n"
                + current_text

                + "\\n\\n"

                "NEXT CONTEXT:\\n"
                + (
                    next_text
                    if next_text
                    else "[NONE]"
                )
            )


            print(
                "  Semantic window:",
                (
                    "PREV"
                    if previous_text
                    else "-"
                ),
                "| CURRENT |",
                (
                    "NEXT"
                    if next_text
                    else "-"
                ),
            )


            # ----------------------------------------------
            # ANALYZE TEMPORARY SEMANTIC SCENE
            #
            # Its expanded text also naturally changes the
            # BatchSceneAnalyzer cache key, preventing old
            # single-scene analysis cache from being reused.
            # ----------------------------------------------

            result = batch.analyze_one(

                scene=semantic_scene,

                use_cache=True,
            )


            # ----------------------------------------------
            # RESTORE ORIGINAL SCENE IDENTITY
            #
            # KIE saw the semantic window, but the manifest
            # must contain ONLY the real current narration.
            # ----------------------------------------------

            analysis_object = (
                result.get(
                    "analysis"
                )
            )


            if analysis_object is None:

                raise FullVideoPipelineError(
                    f"Missing semantic AI analysis "
                    f"for {scene.id}"
                )


            analysis_object.scene_id = (
                scene.id
            )

            analysis_object.start = (
                scene.start
            )

            analysis_object.end = (
                scene.end
            )

            analysis_object.duration = (
                scene.duration
            )

            analysis_object.dialogue = (
                current_text
            )


            analyses.append(
                result
            )
'''


modified = original.replace(
    old_block,
    new_block,
    1,
)


# ==================================================
# SAFETY CHECKS
# ==================================================

required_markers = [

    "SEMANTIC WINDOW 58C V1",

    "semantic_scene = (",

    "PREVIOUS CONTEXT:",

    "CURRENT NARRATION:",

    "NEXT CONTEXT:",

    "analysis_object.dialogue = (",
]


for marker in required_markers:

    if marker not in modified:

        raise RuntimeError(
            "Missing marker after patch: "
            + marker
        )


# ==================================================
# ENSURE copy MODULE EXISTS
# ==================================================

if (
    "import copy"
    not in modified
):

    # Current production already uses copy.deepcopy()
    # in _run_ai_stage in known builds, but add import
    # only if it is missing.

    lines = modified.splitlines()

    insertion_index = 0


    for index, line in enumerate(
        lines
    ):

        if line.startswith(
            "import "
        ):

            insertion_index = (
                index + 1
            )


    lines.insert(
        insertion_index,
        "import copy",
    )


    modified = (
        "\\n".join(
            lines
        )
        + "\\n"
    )


# ==================================================
# IN-MEMORY COMPILE BEFORE WRITING
# ==================================================

compile(
    modified,
    str(TARGET),
    "exec",
)

print(
    "In-memory compile: PASS"
)


# ==================================================
# WRITE
# ==================================================

try:

    TARGET.write_text(
        modified,
        encoding="utf-8",
    )


    py_compile.compile(
        str(TARGET),
        doraise=True,
    )


except Exception:

    print()
    print(
        "PATCH FAILED - RESTORING BACKUP"
    )

    shutil.copy2(
        BACKUP,
        TARGET,
    )

    raise


# ==================================================
# SUCCESS
# ==================================================

print()
print("=" * 78)
print("SEMANTIC WINDOW 58C V1: PASS")
print("=" * 78)

print(
    "SceneBuilder timing: UNCHANGED"
)

print(
    "Original dialogue: PRESERVED"
)

print(
    "Previous context: ENABLED"
)

print(
    "Next context: ENABLED"
)

print(
    "AI cache isolation: ENABLED"
)

print(
    "Geography Guard: UNCHANGED"
)

print(
    "V5 fallback: UNCHANGED"
)

print(
    "Timeline/render: UNCHANGED"
)