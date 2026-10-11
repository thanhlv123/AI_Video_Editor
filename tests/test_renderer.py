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


from engine.renderer import FFmpegRenderer
from engine.ffmpeg import FFprobe


print("=" * 70)
print("AI VIDEO EDITOR")
print("FIRST REAL VIDEO RENDER")
print("=" * 70)


# ==================================================
# FILES
# ==================================================

image_path = (
    ROOT
    / "media"
    / "test_image.jpg"
)

video_path = (
    ROOT
    / "media"
    / "test_video.mp4"
)

voice_path = (
    ROOT
    / "media"
    / "test_voice.mp3"
)

output_path = (
    ROOT
    / "exports"
    / "first_render.mp4"
)


# ==================================================
# RENDER
# ==================================================

renderer = FFmpegRenderer()


result = renderer.render_test_video(

    image_path=image_path,

    video_path=video_path,

    voice_path=voice_path,

    output_path=output_path,

    width=1920,

    height=1080,

    fps=30,

    image_duration=5,

    video_duration=10
)


# ==================================================
# RESULT
# ==================================================

print()
print("=" * 70)
print("RENDER RESULT")
print("=" * 70)

print(
    json.dumps(
        result,
        indent=4
    )
)


# ==================================================
# VERIFY OUTPUT WITH FFPROBE
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
print("DONE")
print("=" * 70)