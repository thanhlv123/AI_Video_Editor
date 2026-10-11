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
print("BATCH TIMELINE BUILDER TEST")
print("=" * 70)


# ==================================================
# PATHS
# ==================================================

manifest_path = (
    ROOT
    / "projects"
    / "analysis_manifest.json"
)


project_path = (
    ROOT
    / "projects"
    / "batch_timeline_test.json"
)


# ==================================================
# CHECK MANIFEST
# ==================================================

if not manifest_path.exists():

    raise FileNotFoundError(
        f"Manifest not found: "
        f"{manifest_path}"
    )


# ==================================================
# LOAD MANIFEST
# ==================================================

print()
print(
    "Loading manifest:",
    manifest_path
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
    "Scenes found:",
    len(scenes)
)


if not scenes:

    raise RuntimeError(
        "Manifest contains no scenes."
    )


# ==================================================
# DISPLAY INPUT SCENES
# ==================================================

print()
print("=" * 70)
print("INPUT SCENES")
print("=" * 70)


for index, scene in enumerate(
    scenes,
    start=1
):

    stock = scene.get(
        "stock",
        {}
    )

    print()

    print(
        f"{index}.",
        scene.get(
            "scene_id"
        )
    )

    print(
        "   Start:",
        scene.get(
            "start"
        )
    )

    print(
        "   End:",
        scene.get(
            "end"
        )
    )

    print(
        "   Duration:",
        scene.get(
            "duration"
        )
    )

    print(
        "   Stock status:",
        stock.get(
            "status"
        )
    )

    download = stock.get(
        "download",
        {}
    )

    print(
        "   Media:",
        download.get(
            "filename"
        )
    )


# ==================================================
# CREATE BUILDER
# ==================================================

builder = BatchTimelineBuilder(

    project_name=(
        "AI Video Editor "
        "Batch Timeline Test"
    ),

    video_track_id="video_1",

    video_track_name="Video 1"
)


# ==================================================
# BUILD TIMELINE
# ==================================================

print()
print("=" * 70)
print("BUILDING TIMELINE")
print("=" * 70)


project, result = builder.build(
    manifest
)


# ==================================================
# DISPLAY BUILD RESULT
# ==================================================

print()
print("=" * 70)
print("BUILD RESULT")
print("=" * 70)


print(
    "Total scenes:",
    result[
        "total_scenes"
    ]
)

print(
    "Validated scenes:",
    result[
        "validated_scenes"
    ]
)

print(
    "Skipped scenes:",
    result[
        "skipped_scenes"
    ]
)

print(
    "Imported media:",
    result[
        "imported_media"
    ]
)

print(
    "Created clips:",
    result[
        "created_clips"
    ]
)

print(
    "Timeline duration:",
    result[
        "timeline_duration"
    ]
)

print(
    "Project revision:",
    result[
        "project_revision"
    ]
)


# ==================================================
# DISPLAY PROJECT MEDIA
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
        f"{index}.",
        media.id
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
        len(
            track.clips
        )
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
# VALIDATE TIMELINE
# ==================================================

print()
print("=" * 70)
print("VALIDATING TIMELINE")
print("=" * 70)


video_track = (
    project.timeline.get_track(
        "video_1"
    )
)


if video_track is None:

    raise RuntimeError(
        "video_1 track was not created."
    )


if len(
    video_track.clips
) != result[
    "created_clips"
]:

    raise RuntimeError(
        "Clip count mismatch."
    )


previous_end = None


for clip in video_track.clips:

    if clip.start < 0:

        raise RuntimeError(
            f"{clip.id}: "
            "negative start time."
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
            f"media not found: "
            f"{clip.media_id}"
        )


    if previous_end is not None:

        if clip.start < previous_end:

            raise RuntimeError(

                f"Timeline overlap detected: "
                f"{clip.id} starts at "
                f"{clip.start}, "
                f"previous clip ends at "
                f"{previous_end}."
            )


    previous_end = clip.end


print(
    "Timeline structure: VALID"
)


# ==================================================
# SAVE PROJECT
# ==================================================

project_path.parent.mkdir(
    parents=True,
    exist_ok=True
)


project.save(
    str(
        project_path
    )
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
print("BATCH TIMELINE SUCCESS")
print("=" * 70)


print(
    "Media:",
    len(
        project.media
    )
)

print(
    "Clips:",
    len(
        video_track.clips
    )
)

print(
    "Duration:",
    result[
        "timeline_duration"
    ]
)

print(
    "Project revision:",
    project.revision
)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)