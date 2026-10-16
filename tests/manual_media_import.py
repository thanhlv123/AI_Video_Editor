from pathlib import Path
import sys
import json


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)


from core.project import Project
from core.operations import OperationManager

from automation.executor import CommandExecutor


# ==================================================
# PROJECT
# ==================================================

project = Project(
    name="Media Import Test"
)


operations = OperationManager(
    project
)

executor = CommandExecutor(
    operations
)


# ==================================================
# COMMANDS
# ==================================================

commands = [

    {
        "command": "media.import",

        "parameters": {
            "path": str(
                ROOT
                / "media"
                / "test_image.jpg"
            ),

            "media_id": "image_001"
        }
    },


    {
        "command": "media.import",

        "parameters": {
            "path": str(
                ROOT
                / "media"
                / "test_video.mp4"
            ),

            "media_id": "video_001"
        }
    },


    {
        "command": "media.import",

        "parameters": {
            "path": str(
                ROOT
                / "media"
                / "test_voice.mp3"
            ),

            "media_id": "voice_001"
        }
    }
]


print("=" * 70)
print("AI VIDEO EDITOR")
print("MEDIA IMPORT COMMAND TEST")
print("=" * 70)


# ==================================================
# EXECUTE
# ==================================================

for command in commands:

    print()
    print("COMMAND")
    print("-" * 70)

    print(
        json.dumps(
            command,
            indent=4,
            ensure_ascii=False
        )
    )


    result = executor.execute(
        command
    )


    print()
    print("RESULT")
    print("-" * 70)

    print(
        json.dumps(
            result,
            indent=4,
            ensure_ascii=False
        )
    )


# ==================================================
# MEDIA LIBRARY
# ==================================================

print()
print("=" * 70)
print("MEDIA LIBRARY")
print("=" * 70)


for media in project.media:

    print()

    print(
        "ID:",
        media.id
    )

    print(
        "Name:",
        media.name
    )

    print(
        "Type:",
        media.media_type
    )

    print(
        "Duration:",
        media.duration
    )

    print(
        "Resolution:",
        media.width,
        "x",
        media.height
    )

    print(
        "FPS:",
        media.fps
    )

    print(
        "Has Audio:",
        media.has_audio
    )


# ==================================================
# SAVE PROJECT
# ==================================================

project.save(
    str(
        ROOT
        / "projects"
        / "media_import_test.json"
    )
)


print()
print("=" * 70)
print("PROJECT SAVED")
print("=" * 70)

print(
    ROOT
    / "projects"
    / "media_import_test.json"
)