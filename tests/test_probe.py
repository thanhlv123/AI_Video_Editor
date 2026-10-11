from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)


from engine.ffmpeg import FFprobe


probe = FFprobe()


files = [

    ROOT / "media" / "test_image.jpg",

    ROOT / "media" / "test_video.mp4",

    ROOT / "media" / "test_voice.mp3"
]


print("=" * 70)
print("FFPROBE MEDIA TEST")
print("=" * 70)


for file in files:

    print()
    print("FILE:", file.name)
    print("-" * 70)

    try:

        info = probe.analyze(
            file
        )

        for key, value in info.items():

            print(
                f"{key}: {value}"
            )

    except Exception as error:

        print(
            "ERROR:",
            error
        )