from pathlib import Path
import sys
import json


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


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
print("STOCK SCENE RENDER TEST")
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
    / "scene_001_render_project.json"
)

output_path = (
    ROOT
    / "exports"
    / "scene_001_render.mp4"
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


if stock.get("status") != "timeline_ready":

    raise RuntimeError(
        "Scene is not timeline_ready. "
        f"Current status: {stock.get('status')}"
    )


# ==================================================
# TIMELINE DATA
# ==================================================

media_id = timeline_data.get(
    "media_id"
)

clip_id = timeline_data.get(
    "clip_id"
)

track_id = timeline_data.get(
    "track_id",
    "video_1"
)

start = float(
    timeline_data.get(
        "start",
        0.0
    )
)

duration = float(
    timeline_data.get(
        "duration",
        0.0
    )
)

source_start = float(
    timeline_data.get(
        "source_start",
        0.0
    )
)


if not media_id:
    raise RuntimeError(
        "timeline.media_id is missing."
    )


if not clip_id:
    raise RuntimeError(
        "timeline.clip_id is missing."
    )


if duration <= 0:
    raise RuntimeError(
        "Timeline duration is invalid."
    )


# ==================================================
# STOCK FILE
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


if not Path(file_path).exists():

    raise RuntimeError(
        f"Stock file does not exist: "
        f"{file_path}"
    )


print()

print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Media ID:",
    media_id
)

print(
    "Clip ID:",
    clip_id
)

print(
    "Source:",
    file_path
)

print(
    "Timeline:",
    f"{start:.3f}s -> "
    f"{start + duration:.3f}s"
)


# ==================================================
# CREATE PROJECT
# ==================================================

project = Project(
    name="Scene 001 Stock Render"
)


# ==================================================
# VIDEO TRACK
# ==================================================

video_track = Track(
    id=track_id,
    name="Video 1",
    track_type="video"
)


project.timeline.add_track(
    video_track
)


# ==================================================
# OPERATIONS
# ==================================================

operations = OperationManager(
    project
)

executor = CommandExecutor(
    operations
)


# ==================================================
# IMPORT STOCK
# ==================================================

executor.execute({

    "command": "media.import",

    "parameters": {

        "path": file_path,

        "media_id": media_id
    }
})


# ==================================================
# ADD TIMELINE CLIP
# ==================================================

executor.execute({

    "command": "timeline.add_clip",

    "parameters": {

        "clip_id": clip_id,

        "media_id": media_id,

        "track_id": track_id,

        "start": start,

        "duration": duration,

        "source_start": source_start,

        "author": "ai"
    }
})


# ==================================================
# SAVE PROJECT BEFORE RENDER
# ==================================================

project.save(
    str(project_path)
)


print()
print(
    "Project saved:",
    project_path
)


# ==================================================
# RENDER
# ==================================================

print()
print("=" * 70)
print("RENDERING SCENE")
print("=" * 70)


renderer = TimelineRenderer()


result = renderer.render(

    project=project,

    output_path=output_path,

    video_track_id=track_id,

    # No voice track exists yet.
    # Renderer handles this as video-only.
    audio_track_id="voice_1"
)


# ==================================================
# DISPLAY RENDER RESULT
# ==================================================

print()
print("=" * 70)
print("RENDER RESULT")
print("=" * 70)


for key, value in result.items():

    print(
        f"{key}: {value}"
    )


# ==================================================
# FFPROBE OUTPUT
# ==================================================

probe = FFprobe()


information = probe.analyze(
    output_path
)


print()
print("=" * 70)
print("OUTPUT FFPROBE")
print("=" * 70)


for key, value in information.items():

    print(
        f"{key}: {value}"
    )


# ==================================================
# VERIFY OUTPUT
# ==================================================

if not information.get(
    "has_video"
):

    raise RuntimeError(
        "Rendered output has no video."
    )


output_duration = float(
    information.get(
        "duration",
        0
    )
    or 0
)


if abs(
    output_duration
    - duration
) > 0.15:

    raise RuntimeError(
        "Rendered duration mismatch. "
        f"Expected={duration:.3f}s, "
        f"Actual={output_duration:.3f}s"
    )


if information.get(
    "width"
) != project.settings.width:

    raise RuntimeError(
        "Rendered width mismatch."
    )


if information.get(
    "height"
) != project.settings.height:

    raise RuntimeError(
        "Rendered height mismatch."
    )


# We intentionally expect no audio yet.
if information.get(
    "has_audio"
):

    raise RuntimeError(
        "Unexpected audio found in "
        "video-only scene render."
    )


# ==================================================
# UPDATE MANIFEST
# ==================================================

stock[
    "render"
] = {

    "status": "rendered",

    "output": str(
        output_path.resolve()
    ),

    "duration": output_duration,

    "width": information.get(
        "width"
    ),

    "height": information.get(
        "height"
    ),

    "fps": information.get(
        "fps"
    ),

    "video_codec": information.get(
        "video_codec"
    ),

    "has_audio": information.get(
        "has_audio"
    )
}


stock[
    "status"
] = "rendered"


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
# SUCCESS
# ==================================================

print()
print("=" * 70)
print("STOCK SCENE RENDER SUCCESS")
print("=" * 70)

print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Output:",
    output_path
)

print(
    "Duration:",
    output_duration
)

print(
    "Resolution:",
    f"{information.get('width')}x"
    f"{information.get('height')}"
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
    "Has audio:",
    information.get(
        "has_audio"
    )
)

print(
    "Manifest status:",
    stock["status"]
)