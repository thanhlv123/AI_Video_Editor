import json

from core.project import Project
from core.media import Media
from core.timeline import Track
from core.operations import OperationManager

from automation.executor import CommandExecutor
from automation.command_registry import list_commands


print("=" * 70)
print("AI VIDEO EDITOR")
print("JSON COMMAND SYSTEM")
print("=" * 70)


# ==================================================
# PROJECT
# ==================================================

project = Project(
    name="JSON Command Test"
)


# ==================================================
# MEDIA LIBRARY
# ==================================================

project.add_media(

    Media(
        id="image_001",
        path="media/vietnam_village.jpg",
        media_type="image",
        name="Vietnam Village"
    )

)


project.add_media(

    Media(
        id="video_001",
        path="media/rural_life.mp4",
        media_type="video",
        name="Rural Life",
        duration=20
    )

)


# ==================================================
# TRACK
# ==================================================

project.timeline.add_track(

    Track(
        id="video_1",
        name="Video 1",
        track_type="video"
    )

)


# ==================================================
# AUTOMATION ENGINE
# ==================================================

operations = OperationManager(
    project
)

executor = CommandExecutor(
    operations
)


# ==================================================
# SHOW AVAILABLE COMMANDS
# ==================================================

print()
print("AVAILABLE COMMANDS")
print("-" * 70)

for name, specification in list_commands().items():

    print(
        name,
        "-",
        specification["description"]
    )


# ==================================================
# COMMAND 1
# ==================================================

command_1 = {

    "command": "timeline.add_clip",

    "parameters": {

        "clip_id": "clip_001",

        "media_id": "image_001",

        "track_id": "video_1",

        "start": 0,

        "duration": 5,

        "author": "ai"
    }
}


print()
print("=" * 70)
print("COMMAND 1")
print("=" * 70)

print(
    json.dumps(
        command_1,
        indent=4
    )
)


result = executor.execute(
    command_1
)


print()
print("RESULT")

print(
    json.dumps(
        result,
        indent=4
    )
)


# ==================================================
# COMMAND 2
# ==================================================

command_2 = {

    "command": "timeline.move_clip",

    "parameters": {

        "clip_id": "clip_001",

        "new_start": 4,

        "author": "ai"
    }
}


print()
print("=" * 70)
print("COMMAND 2")
print("=" * 70)

result = executor.execute(
    command_2
)

print(
    json.dumps(
        result,
        indent=4
    )
)


# ==================================================
# COMMAND 3
# ==================================================

command_3 = {

    "command": "timeline.trim_clip",

    "parameters": {

        "clip_id": "clip_001",

        "new_duration": 7,

        "author": "ai"
    }
}


print()
print("=" * 70)
print("COMMAND 3")
print("=" * 70)

result = executor.execute(
    command_3
)

print(
    json.dumps(
        result,
        indent=4
    )
)


# ==================================================
# CURRENT TIMELINE
# ==================================================

print()
print("=" * 70)
print("CURRENT TIMELINE")
print("=" * 70)


for track in project.timeline.tracks:

    print(
        f"\nTRACK: {track.name}"
    )

    for clip in track.clips:

        print(
            f"{clip.id}"
            f" | start={clip.start}"
            f" | duration={clip.duration}"
            f" | end={clip.end}"
        )


# ==================================================
# HISTORY
# ==================================================

print()
print("=" * 70)
print("COMMAND HISTORY")
print("=" * 70)


for entry in operations.history.entries:

    print(
        f"Revision {entry.revision}"
        f" | {entry.author}"
        f" | {entry.operation}"
    )


# ==================================================
# SAVE PROJECT
# ==================================================

project.save(
    "projects/json_command_test.json"
)


print()
print("=" * 70)
print("PROJECT SAVED")
print("=" * 70)