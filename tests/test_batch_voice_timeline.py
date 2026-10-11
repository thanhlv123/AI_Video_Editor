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


print("=" * 70)
print("AI VIDEO EDITOR")
print("BATCH VOICE TIMELINE TEST")
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
    / "batch_voice_timeline_test.json"
)


# ==================================================
# CHECK FILES
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
print(
    "Manifest:",
    manifest_path
)

print(
    "Voice:",
    voice_path
)


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
    "Scenes:",
    len(scenes)
)


if not scenes:

    raise RuntimeError(
        "Manifest contains no scenes."
    )


# ==================================================
# CREATE BUILDER
# ==================================================

builder = BatchTimelineBuilder(

    project_name=(
        "AI Video Editor "
        "Batch Voice Timeline Test"
    ),

    video_track_id="video_1",

    video_track_name="Video 1",

    voice_track_id="voice_1",

    voice_track_name="Voice"
)


# ==================================================
# BUILD VIDEO + VOICE TIMELINE
# ==================================================

print()
print("=" * 70)
print("BUILDING VIDEO + VOICE TIMELINE")
print("=" * 70)


project, result = builder.build(

    manifest=manifest,

    voice_path=voice_path
)


# ==================================================
# BUILD RESULT
# ==================================================

print()
print("=" * 70)
print("BUILD RESULT")
print("=" * 70)


print(
    "Total scenes:",
    result["total_scenes"]
)

print(
    "Validated scenes:",
    result["validated_scenes"]
)

print(
    "Skipped scenes:",
    result["skipped_scenes"]
)

print(
    "Imported media:",
    result["imported_media"]
)

print(
    "Created clips:",
    result["created_clips"]
)

print(
    "Video clips:",
    result["video_clips"]
)

print(
    "Voice clips:",
    result["voice_clips"]
)

print(
    "Video duration:",
    result["timeline_duration"]
)

print(
    "Voice duration:",
    result["voice_duration"]
)

print(
    "Voice added:",
    result["voice_added"]
)

print(
    "Project revision:",
    result["project_revision"]
)


# ==================================================
# PROJECT MEDIA
# ==================================================

print()
print("=" * 70)
print("PROJECT MEDIA")
print("=" * 70)


for index, media in enumerate(
    project.media,
    start=1
):

    print()

    print(
        f"{index}. {media.id}"
    )

    print(
        "   Name:",
        media.name
    )

    print(
        "   Type:",
        media.media_type
    )

    print(
        "   Duration:",
        media.duration
    )

    print(
        "   Resolution:",
        f"{media.width}x"
        f"{media.height}"
    )

    print(
        "   FPS:",
        media.fps
    )

    print(
        "   Has audio:",
        media.has_audio
    )

    print(
        "   Path:",
        media.path
    )


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
        track.id,
        f"({track.name})"
    )

    print(
        "Type:",
        track.track_type
    )

    print(
        "Clips:",
        len(track.clips)
    )


    for clip in track.clips:

        media = project.get_media(
            clip.media_id
        )

        print()

        print(
            "  Clip:",
            clip.id
        )

        print(
            "    Media ID:",
            clip.media_id
        )

        print(
            "    Media:",
            (
                media.name
                if media
                else "NOT FOUND"
            )
        )

        print(
            "    Start:",
            clip.start
        )

        print(
            "    Duration:",
            clip.duration
        )

        print(
            "    End:",
            clip.end
        )

        print(
            "    Source start:",
            clip.source_start
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


# ==================================================
# VALIDATE VIDEO TRACK
# ==================================================

print()
print("=" * 70)
print("VALIDATING VIDEO TRACK")
print("=" * 70)


if len(video_track.clips) != 3:

    raise RuntimeError(

        "Expected 3 video clips, "
        f"found {len(video_track.clips)}."
    )


previous_end = None


for clip in video_track.clips:

    if clip.start < 0:

        raise RuntimeError(
            f"{clip.id}: "
            "negative start."
        )


    if clip.duration <= 0:

        raise RuntimeError(
            f"{clip.id}: "
            "invalid duration."
        )


    media = project.get_media(
        clip.media_id
    )


    if media is None:

        raise RuntimeError(
            f"{clip.id}: "
            "media not found."
        )


    if previous_end is not None:

        if clip.start < previous_end:

            raise RuntimeError(
                f"{clip.id}: "
                "video overlap detected."
            )


    previous_end = clip.end


print(
    "Video track: VALID"
)


# ==================================================
# VALIDATE VOICE TRACK
# ==================================================

print()
print("=" * 70)
print("VALIDATING VOICE TRACK")
print("=" * 70)


if len(voice_track.clips) != 1:

    raise RuntimeError(

        "Expected 1 voice clip, "
        f"found {len(voice_track.clips)}."
    )


voice_clip = voice_track.clips[0]


if voice_clip.id != "clip_voice_main":

    raise RuntimeError(
        "Unexpected voice clip ID."
    )


if voice_clip.media_id != "voice_main":

    raise RuntimeError(
        "Unexpected voice media ID."
    )


if voice_clip.start != 0.0:

    raise RuntimeError(
        "Voice must start at 0."
    )


if voice_clip.duration <= 0:

    raise RuntimeError(
        "Invalid voice duration."
    )


voice_media = project.get_media(
    "voice_main"
)


if voice_media is None:

    raise RuntimeError(
        "voice_main media not found."
    )


if not voice_media.has_audio:

    raise RuntimeError(
        "voice_main contains no audio."
    )


print(
    "Voice track: VALID"
)


# ==================================================
# CHECK TIMELINE SYNCHRONIZATION
# ==================================================

print()
print("=" * 70)
print("CHECKING A/V SYNCHRONIZATION")
print("=" * 70)


video_duration = result[
    "timeline_duration"
]


voice_timeline_duration = (
    voice_clip.end
)


difference = abs(
    video_duration
    - voice_timeline_duration
)


print(
    "Video timeline:",
    video_duration
)

print(
    "Voice timeline:",
    voice_timeline_duration
)

print(
    "Difference:",
    difference
)


if difference > 0.05:

    raise RuntimeError(

        "Video and voice timeline "
        "are not synchronized."
    )


print(
    "A/V synchronization: VALID"
)


# ==================================================
# SAVE PROJECT
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
# SAVE UPDATED MANIFEST
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


print(
    "Manifest updated:",
    manifest_path
)


# ==================================================
# FINAL RESULT
# ==================================================

print()
print("=" * 70)
print("BATCH VOICE TIMELINE SUCCESS")
print("=" * 70)


print(
    "Total media:",
    len(project.media)
)

print(
    "Video clips:",
    len(video_track.clips)
)

print(
    "Voice clips:",
    len(voice_track.clips)
)

print(
    "Video duration:",
    video_duration
)

print(
    "Voice duration:",
    voice_timeline_duration
)

print(
    "Project revision:",
    project.revision
)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)