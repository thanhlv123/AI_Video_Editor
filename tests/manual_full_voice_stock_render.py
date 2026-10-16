from pathlib import Path
import json
import subprocess
import sys


# ==================================================
# PROJECT ROOT
# ==================================================

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


# ==================================================
# PATHS
# ==================================================

MANIFEST_PATH = (
    ROOT
    / "projects"
    / "voice_stock_full_manifest.json"
)


VOICE_PATH = (
    ROOT
    / "media"
    / "test_voice.mp3"
)


OUTPUT_PATH = (
    ROOT
    / "exports"
    / "full_voice_stock_render.mp4"
)


EXPECTED_SCENES = 30

EXPECTED_DURATION = 168.098

TIMELINE_TOLERANCE = 0.002

RENDER_DURATION_TOLERANCE = 0.50


# ==================================================
# HELPERS
# ==================================================

def load_json(
    path,
):

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def almost_equal(
    a,
    b,
    tolerance,
):

    return abs(
        float(a)
        - float(b)
    ) <= tolerance


def ffprobe_file(
    path,
):

    command = [

        "ffprobe",

        "-v",
        "error",

        "-show_streams",

        "-show_format",

        "-of",
        "json",

        str(path),
    ]


    process = subprocess.run(

        command,

        capture_output=True,

        text=True,
    )


    if process.returncode != 0:

        raise RuntimeError(
            "FFprobe failed:\n"
            + process.stderr
        )


    return json.loads(
        process.stdout
    )


# ==================================================
# HEADER
# ==================================================

print("=" * 70)

print(
    "AI VIDEO EDITOR"
)

print(
    "FULL VOICE STOCK RENDER TEST"
)

print("=" * 70)


print()

print(
    "Manifest:",
    MANIFEST_PATH,
)

print(
    "Voice:",
    VOICE_PATH,
)

print(
    "Output:",
    OUTPUT_PATH,
)


# ==================================================
# CHECK FILES
# ==================================================

if not MANIFEST_PATH.exists():

    raise FileNotFoundError(
        f"Manifest not found: "
        f"{MANIFEST_PATH}"
    )


if not VOICE_PATH.exists():

    raise FileNotFoundError(
        f"Voice not found: "
        f"{VOICE_PATH}"
    )


# ==================================================
# 1. LOAD MANIFEST
# ==================================================

print()

print("=" * 70)

print(
    "[1/7] LOAD STOCK MANIFEST"
)

print("=" * 70)


manifest = load_json(
    MANIFEST_PATH
)


scenes = manifest.get(
    "scenes",
    [],
)


print(
    "Scenes:",
    len(
        scenes
    ),
)


if len(
    scenes
) != EXPECTED_SCENES:

    raise RuntimeError(
        f"Expected {EXPECTED_SCENES} scenes, "
        f"found {len(scenes)}."
    )


# ==================================================
# CHECK STOCK VALIDATION
# ==================================================

invalid_stock = []


for scene in scenes:

    scene_id = scene.get(
        "scene_id"
    )


    stock = scene.get(
        "stock",
        {},
    )


    validation = stock.get(
        "validation",
        {},
    )


    if (
        stock.get(
            "status"
        )
        != "validated"
        or validation.get(
            "valid"
        )
        is not True
    ):

        invalid_stock.append(
            scene_id
        )


if invalid_stock:

    raise RuntimeError(
        "Unvalidated stock scenes: "
        + ", ".join(
            invalid_stock
        )
    )


print(
    "30 stock scenes validated: PASS"
)


# ==================================================
# 2. BUILD PROJECT + TIMELINE
# ==================================================

print()

print("=" * 70)

print(
    "[2/7] BUILD TIMELINE"
)

print("=" * 70)


builder = BatchTimelineBuilder(

    project_name=(
        "Full Voice Stock Render"
    ),

    video_track_id="video_1",

    video_track_name="Video 1",

    voice_track_id="voice_1",

    voice_track_name="Voice",
)


project, build_result = (
    builder.build(

        manifest=manifest,

        voice_path=VOICE_PATH,
    )
)


print()

print(
    "Total scenes:",
    build_result[
        "total_scenes"
    ],
)

print(
    "Validated scenes:",
    build_result[
        "validated_scenes"
    ],
)

print(
    "Skipped scenes:",
    build_result[
        "skipped_scenes"
    ],
)

print(
    "Imported media:",
    build_result[
        "imported_media"
    ],
)

print(
    "Video clips:",
    build_result[
        "video_clips"
    ],
)

print(
    "Voice clips:",
    build_result[
        "voice_clips"
    ],
)

print(
    "Timeline duration:",
    build_result[
        "timeline_duration"
    ],
)

print(
    "Voice duration:",
    build_result[
        "voice_duration"
    ],
)


# ==================================================
# 3. VALIDATE VIDEO TIMELINE
# ==================================================

print()

print("=" * 70)

print(
    "[3/7] VALIDATE VIDEO TIMELINE"
)

print("=" * 70)


video_track = (
    project.timeline.get_track(
        "video_1"
    )
)


if video_track is None:

    raise RuntimeError(
        "video_1 track not found."
    )


video_clips = sorted(

    video_track.clips,

    key=lambda clip: clip.start,
)


print(
    "Video clips:",
    len(
        video_clips
    ),
)


if len(
    video_clips
) != EXPECTED_SCENES:

    raise RuntimeError(
        f"Expected {EXPECTED_SCENES} "
        f"video clips, found "
        f"{len(video_clips)}."
    )


# ==================================================
# FIRST CLIP START
# ==================================================

first_clip = video_clips[
    0
]


if not almost_equal(
    first_clip.start,
    0.0,
    TIMELINE_TOLERANCE,
):

    raise RuntimeError(
        "Timeline does not start at 0.0. "
        f"Actual: {first_clip.start}"
    )


print(
    "Timeline starts at 0.000: PASS"
)


# ==================================================
# GAPS + OVERLAPS
# ==================================================

expected_start = 0.0


for index, clip in enumerate(
    video_clips,
    start=1,
):

    if clip.duration <= 0:

        raise RuntimeError(
            f"{clip.id}: invalid duration "
            f"{clip.duration}"
        )


    if not almost_equal(
        clip.start,
        expected_start,
        TIMELINE_TOLERANCE,
    ):

        difference = (
            clip.start
            - expected_start
        )


        if difference > 0:

            problem = "GAP"

        else:

            problem = "OVERLAP"


        raise RuntimeError(

            f"{problem} at clip "
            f"{index}: {clip.id}. "

            f"Expected start "
            f"{expected_start:.6f}, "

            f"actual "
            f"{clip.start:.6f}."
        )


    expected_start = (
        clip.start
        + clip.duration
    )


print(
    "No timeline gaps: PASS"
)

print(
    "No timeline overlaps: PASS"
)


# ==================================================
# LAST CLIP END
# ==================================================

timeline_end = (
    video_clips[
        -1
    ].end
)


print(
    "Timeline end:",
    timeline_end,
)


if not almost_equal(
    timeline_end,
    EXPECTED_DURATION,
    TIMELINE_TOLERANCE,
):

    raise RuntimeError(

        "Timeline duration mismatch. "

        f"Expected "
        f"{EXPECTED_DURATION:.3f}, "

        f"actual "
        f"{timeline_end:.6f}."
    )


print(
    "Timeline ends at 168.098: PASS"
)


# ==================================================
# 4. VALIDATE VOICE TRACK
# ==================================================

print()

print("=" * 70)

print(
    "[4/7] VALIDATE VOICE TRACK"
)

print("=" * 70)


voice_track = (
    project.timeline.get_track(
        "voice_1"
    )
)


if voice_track is None:

    raise RuntimeError(
        "voice_1 track not found."
    )


voice_clips = sorted(

    voice_track.clips,

    key=lambda clip: clip.start,
)


if len(
    voice_clips
) != 1:

    raise RuntimeError(
        "Expected exactly one voice clip, "
        f"found {len(voice_clips)}."
    )


voice_clip = voice_clips[
    0
]


if not almost_equal(
    voice_clip.start,
    0.0,
    TIMELINE_TOLERANCE,
):

    raise RuntimeError(
        "Voice clip does not start at 0."
    )


print(
    "Voice track exists: PASS"
)

print(
    "Voice clips: 1"
)

print(
    "Voice starts at 0.000: PASS"
)

print(
    "Voice clip duration:",
    voice_clip.duration,
)


# ==================================================
# CHECK MEDIA SOURCES WITH AUDIO
# ==================================================

stock_media_with_audio = []


for media in project.media:

    if (
        media.id
        == "voice_main"
    ):

        continue


    if getattr(
        media,
        "has_audio",
        False,
    ):

        stock_media_with_audio.append(
            media.id
        )


print()

print(
    "Stock source files containing audio:",
    len(
        stock_media_with_audio
    ),
)


for media_id in stock_media_with_audio:

    print(
        "  -",
        media_id,
    )


print()

print(
    "Stock audio will NOT be mapped "
    "by TimelineRenderer."
)


# ==================================================
# 5. RENDER
# ==================================================

print()

print("=" * 70)

print(
    "[5/7] RENDER FULL VIDEO"
)

print("=" * 70)


OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)


renderer = TimelineRenderer()


render_result = renderer.render(

    project=project,

    output_path=OUTPUT_PATH,

    video_track_id="video_1",

    audio_track_id="voice_1",
)


if not render_result.get(
    "success"
):

    raise RuntimeError(
        "Timeline renderer did not "
        "report success."
    )


if not OUTPUT_PATH.exists():

    raise RuntimeError(
        "Output file was not created."
    )


print()

print(
    "Render file:",
    OUTPUT_PATH,
)

print(
    "Render size:",
    OUTPUT_PATH.stat().st_size,
    "bytes",
)


# ==================================================
# 6. FFPROBE FINAL OUTPUT
# ==================================================

print()

print("=" * 70)

print(
    "[6/7] FFPROBE FINAL OUTPUT"
)

print("=" * 70)


probe = ffprobe_file(
    OUTPUT_PATH
)


streams = probe.get(
    "streams",
    [],
)


video_streams = [

    stream

    for stream
    in streams

    if stream.get(
        "codec_type"
    )
    == "video"
]


audio_streams = [

    stream

    for stream
    in streams

    if stream.get(
        "codec_type"
    )
    == "audio"
]


print(
    "Video streams:",
    len(
        video_streams
    ),
)

print(
    "Audio streams:",
    len(
        audio_streams
    ),
)


if len(
    video_streams
) != 1:

    raise RuntimeError(
        "Expected exactly one "
        "output video stream."
    )


if len(
    audio_streams
) != 1:

    raise RuntimeError(

        "Expected exactly one "

        "output audio stream. "

        "Stock audio may have leaked "
        "into the output."
    )


print(
    "Single video stream: PASS"
)

print(
    "Single voice audio stream: PASS"
)

print(
    "Stock audio isolation: PASS"
)


# ==================================================
# RESOLUTION
# ==================================================

video_stream = video_streams[
    0
]


width = int(
    video_stream.get(
        "width",
        0,
    )
)


height = int(
    video_stream.get(
        "height",
        0,
    )
)


print(
    "Resolution:",
    f"{width}x{height}",
)


if (
    width != 1920
    or height != 1080
):

    raise RuntimeError(
        "Unexpected output resolution: "
        f"{width}x{height}"
    )


print(
    "1920x1080 output: PASS"
)


# ==================================================
# FINAL DURATION
# ==================================================

format_info = probe.get(
    "format",
    {},
)


render_duration = float(
    format_info.get(
        "duration",
        0.0,
    )
    or 0.0
)


print(
    "Rendered duration:",
    render_duration,
)


if not almost_equal(
    render_duration,
    EXPECTED_DURATION,
    RENDER_DURATION_TOLERANCE,
):

    raise RuntimeError(

        "Rendered duration mismatch. "

        f"Expected approximately "
        f"{EXPECTED_DURATION:.3f}s, "

        f"actual "
        f"{render_duration:.3f}s."
    )


print(
    "Rendered duration: PASS"
)


# ==================================================
# 7. FINAL RESULT
# ==================================================

print()

print("=" * 70)

print(
    "[7/7] FINAL RESULT"
)

print("=" * 70)


print(
    "30 scene timeline: PASS"
)

print(
    "Timeline starts at 0.000: PASS"
)

print(
    "Timeline ends at 168.098: PASS"
)

print(
    "No gaps: PASS"
)

print(
    "No overlaps: PASS"
)

print(
    "Voice track: PASS"
)

print(
    "Stock audio muted: PASS"
)

print(
    "FFprobe output: PASS"
)

print(
    "Render: PASS"
)


print()

print("=" * 70)

print(
    "FULL VOICE STOCK RENDER SUCCESS"
)

print("=" * 70)


print(
    "Output:",
    OUTPUT_PATH
)

print(
    "Duration:",
    render_duration
)

print(
    "Resolution:",
    f"{width}x{height}"
)

print(
    "Video streams:",
    len(
        video_streams
    )
)

print(
    "Audio streams:",
    len(
        audio_streams
    )
)


print()

print("=" * 70)

print(
    "TEST COMPLETE"
)

print("=" * 70)