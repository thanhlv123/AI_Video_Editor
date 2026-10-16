from pathlib import Path
import sys


ROOT = Path(
    __file__
).resolve().parent.parent


sys.path.insert(
    0,
    str(ROOT)
)


from core.project import Project
from core.timeline import Track
from core.operations import OperationManager

from automation.executor import CommandExecutor

from engine.timeline_renderer import (
    TimelineRenderer
)

from engine.ffmpeg import FFprobe


print("=" * 70)
print("AI VIDEO EDITOR")
print("PROJECT -> TIMELINE -> FFMPEG TEST")
print("=" * 70)


# ==================================================
# CREATE PROJECT
# ==================================================

project = Project(
    name="First Timeline Render"
)


# ==================================================
# TRACKS
# ==================================================

video_track = Track(
    id="video_1",
    name="Video 1",
    track_type="video"
)


voice_track = Track(
    id="voice_1",
    name="Voice",
    track_type="audio"
)


project.timeline.add_track(
    video_track
)

project.timeline.add_track(
    voice_track
)


# ==================================================
# AUTOMATION
# ==================================================

operations = OperationManager(
    project
)

executor = CommandExecutor(
    operations
)


# ==================================================
# IMPORT REAL MEDIA
# ==================================================

executor.execute({

    "command": "media.import",

    "parameters": {

        "path": str(
            ROOT
            / "media"
            / "test_image.jpg"
        ),

        "media_id": "image_001"
    }
})


executor.execute({

    "command": "media.import",

    "parameters": {

        "path": str(
            ROOT
            / "media"
            / "test_video.mp4"
        ),

        "media_id": "video_001"
    }
})


executor.execute({

    "command": "media.import",

    "parameters": {

        "path": str(
            ROOT
            / "media"
            / "test_voice.mp3"
        ),

        "media_id": "voice_001"
    }
})


# ==================================================
# BUILD TIMELINE USING COMMANDS
# ==================================================

executor.execute({

    "command": "timeline.add_clip",

    "parameters": {

        "clip_id": "clip_image_001",

        "media_id": "image_001",

        "track_id": "video_1",

        "start": 0,

        "duration": 5,

        "author": "ai"
    }
})


executor.execute({

    "command": "timeline.add_clip",

    "parameters": {

        "clip_id": "clip_video_001",

        "media_id": "video_001",

        "track_id": "video_1",

        "start": 5,

        "duration": 10,

        "source_start": 0,

        "author": "ai"
    }
})


executor.execute({

    "command": "timeline.add_clip",

    "parameters": {

        "clip_id": "clip_voice_001",

        "media_id": "voice_001",

        "track_id": "voice_1",

        "start": 0,

        "duration": 15,

        "source_start": 0,

        "author": "ai"
    }
})


# ==================================================
# DISPLAY TIMELINE
# ==================================================

print()
print("=" * 70)
print("PROJECT TIMELINE")
print("=" * 70)


for track in project.timeline.tracks:

    print()

    print(
        "TRACK:",
        track.name
    )


    for clip in track.clips:

        media = project.get_media(
            clip.media_id
        )

        print(
            f"  {clip.id}"
            f" | {media.name}"
            f" | {clip.start:.2f}"
            f" -> {clip.end:.2f}"
        )


# ==================================================
# SAVE PROJECT BEFORE RENDER
# ==================================================

project_path = (
    ROOT
    / "projects"
    / "timeline_render_test.json"
)


project.save(
    str(project_path)
)


print()
print(
    "Project saved:",
    project_path
)


# ==================================================
# RENDER FROM TIMELINE
# ==================================================

output_path = (
    ROOT
    / "exports"
    / "timeline_render.mp4"
)


renderer = TimelineRenderer()


result = renderer.render(

    project=project,

    output_path=output_path,

    video_track_id="video_1",

    audio_track_id="voice_1"
)


# ==================================================
# RESULT
# ==================================================

print()
print("=" * 70)
print("RENDER SUCCESS")
print("=" * 70)


for key, value in result.items():

    print(
        f"{key}: {value}"
    )


# ==================================================
# VERIFY
# ==================================================

print()
print("=" * 70)
print("VERIFY OUTPUT")
print("=" * 70)


probe = FFprobe()


information = probe.analyze(
    output_path
)


for key, value in information.items():

    print(
        f"{key}: {value}"
    )


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)