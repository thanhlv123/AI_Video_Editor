from pathlib import Path
import sys
import json


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


from core.project import Project
from core.timeline import Track
from core.operations import OperationManager
from automation.executor import CommandExecutor


print("=" * 70)
print("AI VIDEO EDITOR")
print("STOCK TIMELINE INTEGRATION TEST")
print("=" * 70)


# ==================================================
# PATHS
# ==================================================

manifest_path = (
    ROOT
    / "projects"
    / "analysis_manifest.json"
)

output_project_path = (
    ROOT
    / "projects"
    / "stock_timeline_test.json"
)


# ==================================================
# LOAD MANIFEST
# ==================================================

with open(
    manifest_path,
    "r",
    encoding="utf-8"
) as file:

    manifest = json.load(file)


scene = manifest["scenes"][0]
stock = scene["stock"]
timeline_data = scene["timeline"]


# ==================================================
# CHECK IMPORT STATUS
# ==================================================

if stock.get("status") != "imported":
    raise RuntimeError(
        "Stock must be imported before "
        "adding it to timeline. "
        f"Current status: {stock.get('status')}"
    )


media_id = timeline_data.get(
    "media_id"
)

if not media_id:
    raise RuntimeError(
        "Scene timeline.media_id is missing."
    )


# ==================================================
# SCENE TIMING
# ==================================================

start = float(
    scene.get(
        "start",
        0.0
    )
)


# Try duration first.
scene_duration = scene.get(
    "duration"
)


# Otherwise calculate from end - start.
if scene_duration is None:

    end = scene.get(
        "end"
    )

    if end is None:
        raise RuntimeError(
            "Scene has neither duration nor end."
        )

    scene_duration = (
        float(end)
        - start
    )


scene_duration = float(
    scene_duration
)


if scene_duration <= 0:
    raise RuntimeError(
        f"Invalid scene duration: "
        f"{scene_duration}"
    )


# ==================================================
# CHECK STOCK DURATION
# ==================================================

import_data = stock.get(
    "import",
    {}
)


stock_duration = float(
    import_data.get(
        "duration",
        0
    )
    or 0
)


if stock_duration <= 0:
    raise RuntimeError(
        "Imported stock duration is invalid."
    )


if scene_duration > stock_duration:

    raise RuntimeError(
        "Stock video is shorter than scene. "
        f"Scene={scene_duration:.3f}s, "
        f"Stock={stock_duration:.3f}s"
    )


# ==================================================
# CREATE PROJECT
# ==================================================

project = Project(
    name="AI Stock Timeline Test"
)


# ==================================================
# CREATE VIDEO TRACK
# ==================================================

track_id = timeline_data.get(
    "track_id",
    "video_1"
)


video_track = Track(
    id=track_id,
    name="Video 1",
    track_type="video"
)


project.timeline.add_track(
    video_track
)


# ==================================================
# OPERATION SYSTEM
# ==================================================

operations = OperationManager(
    project
)

executor = CommandExecutor(
    operations
)


# ==================================================
# RE-IMPORT VALIDATED MEDIA INTO THIS PROJECT
# ==================================================

download = stock.get(
    "download",
    {}
)


file_path = download.get(
    "path"
)


if not file_path:
    raise RuntimeError(
        "Downloaded stock path is missing."
    )


import_command = {

    "command": "media.import",

    "parameters": {

        "path": file_path,

        "media_id": media_id
    }
}


import_result = executor.execute(
    import_command
)


print()
print("=" * 70)
print("MEDIA READY")
print("=" * 70)

print(
    "Media ID:",
    import_result["media"]["id"]
)

print(
    "Duration:",
    import_result["media"]["duration"]
)


# ==================================================
# CREATE CLIP
# ==================================================

clip_id = (
    f"clip_{scene['scene_id']}"
)


clip_command = {

    "command": "timeline.add_clip",

    "parameters": {

        "clip_id": clip_id,

        "media_id": media_id,

        "track_id": track_id,

        "start": start,

        "duration": scene_duration,

        "source_start": 0.0,

        "author": "ai"
    }
}


print()
print("=" * 70)
print("TIMELINE COMMAND")
print("=" * 70)

print(
    json.dumps(
        clip_command,
        indent=4,
        ensure_ascii=False
    )
)


# ==================================================
# EXECUTE
# ==================================================

result = executor.execute(
    clip_command
)


clip = result[
    "clip"
]


# ==================================================
# VERIFY
# ==================================================

if clip["media_id"] != media_id:
    raise RuntimeError(
        "Clip media_id mismatch."
    )


if clip["track_id"] != track_id:
    raise RuntimeError(
        "Clip track_id mismatch."
    )


if abs(
    float(clip["start"])
    - start
) > 0.001:

    raise RuntimeError(
        "Clip start mismatch."
    )


if abs(
    float(clip["duration"])
    - scene_duration
) > 0.001:

    raise RuntimeError(
        "Clip duration mismatch."
    )


timeline_clip = (
    project.timeline.get_clip(
        clip_id
    )
)


if timeline_clip is None:
    raise RuntimeError(
        "Clip was not added to timeline."
    )


# ==================================================
# UPDATE MANIFEST
# ==================================================

timeline_data[
    "clip_id"
] = clip_id


timeline_data[
    "media_id"
] = media_id


timeline_data[
    "track_id"
] = track_id


timeline_data[
    "start"
] = start


timeline_data[
    "duration"
] = scene_duration


timeline_data[
    "source_start"
] = 0.0


stock[
    "status"
] = "timeline_ready"


# ==================================================
# SAVE PROJECT
# ==================================================

project.save(
    str(output_project_path)
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
# RESULT
# ==================================================

print()
print("=" * 70)
print("TIMELINE RESULT")
print("=" * 70)

print(
    "Clip ID:",
    clip["id"]
)

print(
    "Media ID:",
    clip["media_id"]
)

print(
    "Track:",
    clip["track_id"]
)

print(
    "Start:",
    clip["start"]
)

print(
    "Duration:",
    clip["duration"]
)

print(
    "End:",
    (
        float(clip["start"])
        + float(clip["duration"])
    )
)

print(
    "Source start:",
    clip["source_start"]
)

print(
    "Project revision:",
    project.revision
)

print(
    "Track clips:",
    len(video_track.clips)
)


print()
print("=" * 70)
print("STOCK TIMELINE SUCCESS")
print("=" * 70)

print(
    "Manifest status:",
    stock["status"]
)

print(
    "Timeline clip_id:",
    timeline_data["clip_id"]
)

print(
    "Timeline media_id:",
    timeline_data["media_id"]
)

print(
    "Project saved:",
    output_project_path
)