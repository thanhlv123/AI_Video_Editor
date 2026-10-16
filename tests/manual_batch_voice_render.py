from pathlib import Path
import sys
import json


ROOT = Path(
    __file__
).resolve().parent.parent


sys.path.insert(
    0,
    str(ROOT)
)


from pipeline.timeline_builder import (
    BatchTimelineBuilder
)

from engine.timeline_renderer import (
    TimelineRenderer
)

from engine.ffmpeg import (
    FFprobe
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("BATCH VIDEO + VOICE RENDER TEST")
print("=" * 70)


# ==================================================
# PATHS
# ==================================================

manifest_path = (
    ROOT
    / "projects"
    / "analysis_manifest.json"
)


voice_path = (
    ROOT
    / "media"
    / "test_voice_15s.mp3"
)


project_path = (
    ROOT
    / "projects"
    / "batch_voice_render_project.json"
)


output_path = (
    ROOT
    / "exports"
    / "batch_voice_render.mp4"
)


# ==================================================
# CHECK INPUT FILES
# ==================================================

if not manifest_path.exists():

    raise FileNotFoundError(
        f"Manifest not found: "
        f"{manifest_path}"
    )


if not voice_path.exists():

    raise FileNotFoundError(
        f"Voice not found: "
        f"{voice_path}"
    )


# ==================================================
# LOAD MANIFEST
# ==================================================

print()
print("=" * 70)
print("LOADING MANIFEST")
print("=" * 70)


with open(
    manifest_path,
    "r",
    encoding="utf-8"
) as file:

    manifest = json.load(
        file
    )


scenes = manifest.get(
    "scenes",
    []
)


print(
    "Manifest:",
    manifest_path
)

print(
    "Scenes:",
    len(scenes)
)

print(
    "Voice:",
    voice_path
)


if not scenes:

    raise RuntimeError(
        "Manifest contains no scenes."
    )


# ==================================================
# BUILD TIMELINE
# ==================================================

print()
print("=" * 70)
print("BUILDING TIMELINE")
print("=" * 70)


builder = BatchTimelineBuilder(

    project_name=(
        "AI Video Editor "
        "Batch Voice Render"
    ),

    video_track_id="video_1",

    video_track_name="Video 1",

    voice_track_id="voice_1",

    voice_track_name="Voice"
)


project, build_result = builder.build(

    manifest=manifest,

    voice_path=voice_path
)


# ==================================================
# DISPLAY BUILD RESULT
# ==================================================

print()
print("=" * 70)
print("TIMELINE BUILD RESULT")
print("=" * 70)


print(
    "Validated scenes:",
    build_result[
        "validated_scenes"
    ]
)

print(
    "Imported media:",
    build_result[
        "imported_media"
    ]
)

print(
    "Video clips:",
    build_result[
        "video_clips"
    ]
)

print(
    "Voice clips:",
    build_result[
        "voice_clips"
    ]
)

print(
    "Video duration:",
    build_result[
        "timeline_duration"
    ]
)

print(
    "Voice duration:",
    build_result[
        "voice_duration"
    ]
)

print(
    "Project revision:",
    build_result[
        "project_revision"
    ]
)


# ==================================================
# GET TRACKS
# ==================================================

video_track = (
    project.timeline.get_track(
        "video_1"
    )
)


voice_track = (
    project.timeline.get_track(
        "voice_1"
    )
)


if video_track is None:

    raise RuntimeError(
        "video_1 track not found."
    )


if voice_track is None:

    raise RuntimeError(
        "voice_1 track not found."
    )


if not video_track.clips:

    raise RuntimeError(
        "No video clips found."
    )


if not voice_track.clips:

    raise RuntimeError(
        "No voice clips found."
    )


# ==================================================
# DISPLAY TIMELINE
# ==================================================

print()
print("=" * 70)
print("TIMELINE")
print("=" * 70)


print()
print(
    "VIDEO TRACK:"
)


for clip in video_track.clips:

    media = project.get_media(
        clip.media_id
    )

    print(
        f"  {clip.id}"
        f" | {clip.start:.3f}"
        f" -> {clip.end:.3f}"
        f" | {media.name}"
    )


print()
print(
    "VOICE TRACK:"
)


for clip in voice_track.clips:

    media = project.get_media(
        clip.media_id
    )

    print(
        f"  {clip.id}"
        f" | {clip.start:.3f}"
        f" -> {clip.end:.3f}"
        f" | {media.name}"
    )


# ==================================================
# SAVE PROJECT BEFORE RENDER
# ==================================================

project_path.parent.mkdir(
    parents=True,
    exist_ok=True
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
# CREATE EXPORT DIRECTORY
# ==================================================

output_path.parent.mkdir(
    parents=True,
    exist_ok=True
)


# ==================================================
# REMOVE OLD OUTPUT
# ==================================================

if output_path.exists():

    print()
    print(
        "Removing old output:",
        output_path
    )

    output_path.unlink()


# ==================================================
# RENDER
# ==================================================

print()
print("=" * 70)
print("RENDERING")
print("=" * 70)

print()
print(
    "Output:",
    output_path
)

print(
    "Please wait..."
)


renderer = TimelineRenderer()


render_result = renderer.render(

    project=project,

    output_path=output_path,

    video_track_id="video_1",

    audio_track_id="voice_1"
)


# ==================================================
# DISPLAY RENDER RESULT
# ==================================================

print()
print("=" * 70)
print("RENDER RESULT")
print("=" * 70)


if isinstance(
    render_result,
    dict
):

    for key, value in (
        render_result.items()
    ):

        print(
            f"{key}: {value}"
        )

else:

    print(
        render_result
    )


# ==================================================
# CHECK OUTPUT EXISTS
# ==================================================

if not output_path.exists():

    raise RuntimeError(
        "Renderer finished but "
        "output file was not created."
    )


file_size = (
    output_path.stat().st_size
)


if file_size <= 0:

    raise RuntimeError(
        "Rendered output file is empty."
    )


print()
print(
    "Output size:",
    file_size,
    "bytes"
)


# ==================================================
# FFPROBE OUTPUT
# ==================================================

print()
print("=" * 70)
print("VERIFYING OUTPUT WITH FFPROBE")
print("=" * 70)


probe = FFprobe()


information = probe.analyze(
    output_path
)


for key, value in (
    information.items()
):

    print(
        f"{key}: {value}"
    )


# ==================================================
# VALIDATE OUTPUT
# ==================================================

print()
print("=" * 70)
print("VALIDATING RENDERED VIDEO")
print("=" * 70)


if not information.get(
    "has_video"
):

    raise RuntimeError(
        "Rendered file contains no video."
    )


if not information.get(
    "has_audio"
):

    raise RuntimeError(
        "Rendered file contains no audio."
    )


width = information.get(
    "width"
)


height = information.get(
    "height"
)


if (
    width != 1920
    or height != 1080
):

    raise RuntimeError(

        "Unexpected output resolution: "
        f"{width}x{height}"
    )


duration = float(
    information.get(
        "duration",
        0.0
    )
)


expected_duration = float(
    build_result[
        "timeline_duration"
    ]
)


duration_difference = abs(
    duration
    - expected_duration
)


print(
    "Expected duration:",
    expected_duration
)

print(
    "Actual duration:",
    duration
)

print(
    "Difference:",
    duration_difference
)


# FFmpeg containers can differ by a tiny amount.
# Allow 0.15 second tolerance.

if duration_difference > 0.15:

    raise RuntimeError(

        "Rendered duration differs "
        "too much from timeline."
    )


print(
    "Video stream: VALID"
)

print(
    "Audio stream: VALID"
)

print(
    "Resolution: VALID"
)

print(
    "Duration: VALID"
)


# ==================================================
# SAVE MANIFEST
# ==================================================

with open(
    manifest_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        manifest,
        file,
        indent=4,
        ensure_ascii=False
    )


# ==================================================
# FINAL SUCCESS
# ==================================================

print()
print("=" * 70)
print("BATCH VIDEO + VOICE RENDER SUCCESS")
print("=" * 70)


print(
    "Output:",
    output_path
)

print(
    "Size:",
    file_size,
    "bytes"
)

print(
    "Duration:",
    duration
)

print(
    "Resolution:",
    f"{width}x{height}"
)

print(
    "FPS:",
    information.get(
        "fps"
    )
)

print(
    "Video codec:",
    information.get(
        "video_codec"
    )
)

print(
    "Audio codec:",
    information.get(
        "audio_codec"
    )
)

print(
    "Sample rate:",
    information.get(
        "sample_rate"
    )
)

print(
    "Channels:",
    information.get(
        "channels"
    )
)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)