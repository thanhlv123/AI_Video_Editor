import inspect
import sys
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parent.parent


sys.path.insert(
    0,
    str(ROOT)
)


print("=" * 80)
print("AI VIDEO EDITOR")
print("FULL PIPELINE API INSPECTOR")
print("=" * 80)


# ==================================================
# MODULE IMPORTS
# ==================================================

from pipeline.voice_pipeline import (
    VoicePipeline
)

from ai.providers.kie_provider import (
    KieAIProvider
)

from ai.scene_ai_analyzer import (
    SceneAIAnalyzer
)

from ai.batch_analyzer import (
    BatchSceneAnalyzer
)

from ai.manifest_builder import (
    AnalysisManifestBuilder
)

from pipeline.batch_pipeline import (
    BatchPipeline
)

from pipeline.timeline_builder import (
    BatchTimelineBuilder
)

from engine.timeline_renderer import (
    TimelineRenderer
)


# ==================================================
# HELPERS
# ==================================================

def show_class(
    cls,
    methods=None,
):

    print()
    print("=" * 80)
    print(cls.__module__ + "." + cls.__name__)
    print("=" * 80)

    print(
        "CLASS SIGNATURE:"
    )

    try:

        print(
            inspect.signature(
                cls
            )
        )

    except Exception as error:

        print(
            "Could not inspect class:",
            error
        )


    if not methods:

        return


    for method_name in methods:

        print()
        print(
            f"METHOD: {method_name}"
        )

        method = getattr(
            cls,
            method_name,
            None,
        )


        if method is None:

            print(
                "NOT FOUND"
            )

            continue


        try:

            print(
                inspect.signature(
                    method
                )
            )

        except Exception as error:

            print(
                "Signature error:",
                error
            )


# ==================================================
# VOICE PIPELINE
# ==================================================

show_class(

    VoicePipeline,

    methods=[
        "run",
    ],
)


# ==================================================
# KIE PROVIDER
# ==================================================

show_class(

    KieAIProvider,

    methods=[
        "analyze",
        "request",
    ],
)


# ==================================================
# SCENE AI ANALYZER
# ==================================================

show_class(

    SceneAIAnalyzer,

    methods=[
        "analyze",
    ],
)


# ==================================================
# BATCH AI ANALYZER
# ==================================================

show_class(

    BatchSceneAnalyzer,

    methods=[
        "analyze",
        "analyze_one",
        "analyze_many",
    ],
)


# ==================================================
# MANIFEST BUILDER
# ==================================================

show_class(

    AnalysisManifestBuilder,

    methods=[
        "build",
        "build_scene",
    ],
)


# ==================================================
# STOCK BATCH
# ==================================================

show_class(

    BatchPipeline,

    methods=[
        "run",
    ],
)


# ==================================================
# TIMELINE
# ==================================================

show_class(

    BatchTimelineBuilder,

    methods=[
        "build",
    ],
)


# ==================================================
# RENDERER
# ==================================================

show_class(

    TimelineRenderer,

    methods=[
        "render",
    ],
)


# ==================================================
# ALSO PRINT SOURCE OF SMALL PUBLIC METHODS
# ==================================================

print()
print("=" * 80)
print("VOICE PIPELINE RUN SOURCE")
print("=" * 80)

try:

    print(
        inspect.getsource(
            VoicePipeline.run
        )
    )

except Exception as error:

    print(
        "Could not read source:",
        error
    )


print()
print("=" * 80)
print("BATCH ANALYZER analyze_one SOURCE")
print("=" * 80)

try:

    print(
        inspect.getsource(
            BatchSceneAnalyzer.analyze_one
        )
    )

except Exception as error:

    print(
        "Could not read source:",
        error
    )


print()
print("=" * 80)
print("MANIFEST BUILDER build SOURCE")
print("=" * 80)

try:

    print(
        inspect.getsource(
            AnalysisManifestBuilder.build
        )
    )

except Exception as error:

    print(
        "Could not read source:",
        error
    )


print()
print("=" * 80)
print("BATCH PIPELINE INIT SOURCE")
print("=" * 80)

try:

    print(
        inspect.getsource(
            BatchPipeline.__init__
        )
    )

except Exception as error:

    print(
        "Could not read source:",
        error
    )


print()
print("=" * 80)
print("INSPECTION COMPLETE")
print("=" * 80)