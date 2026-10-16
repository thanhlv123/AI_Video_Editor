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


from stock.validator import (
    MediaValidator,
    MediaValidationError
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("DOWNLOADED MEDIA VALIDATION TEST")
print("=" * 70)


# ==================================================
# LOAD MANIFEST
# ==================================================

manifest_path = (
    ROOT
    / "projects"
    / "analysis_manifest.json"
)


with open(
    manifest_path,
    "r",
    encoding="utf-8"
) as file:

    manifest = json.load(
        file
    )


scene = manifest[
    "scenes"
][0]


stock = scene[
    "stock"
]


selected = stock.get(
    "selected_media"
)


download = stock.get(
    "download"
)


if not selected:

    raise RuntimeError(
        "No selected_media found."
    )


if not download:

    raise RuntimeError(
        "No download information found."
    )


file_path = download.get(
    "path"
)


if not file_path:

    raise RuntimeError(
        "Download path is missing."
    )


expected_type = selected.get(
    "media_type"
)


# ==================================================
# DISPLAY INPUT
# ==================================================

print()

print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Media ID:",
    selected.get(
        "media_id"
    )
)

print(
    "Expected type:",
    expected_type
)

print(
    "File:",
    file_path
)


# ==================================================
# VALIDATE
# ==================================================

validator = MediaValidator()


print()
print(
    "Running FFprobe validation..."
)


try:

    result = validator.validate(

        file_path=file_path,

        expected_type=expected_type
    )


except MediaValidationError as error:

    print()
    print("=" * 70)
    print("MEDIA VALIDATION FAILED")
    print("=" * 70)

    print(error)

    raise SystemExit(1)


# ==================================================
# DISPLAY FFPROBE RESULT
# ==================================================

print()
print("=" * 70)
print("FFPROBE RESULT")
print("=" * 70)

print(
    "Valid:",
    result["valid"]
)

print(
    "Duration:",
    result["duration"]
)

print(
    "Has video:",
    result["has_video"]
)

print(
    "Has audio:",
    result["has_audio"]
)

print(
    "Resolution:",
    f"{result['width']}x"
    f"{result['height']}"
)

print(
    "Video codec:",
    result["video_codec"]
)

print(
    "FPS:",
    result["fps"]
)

print(
    "Audio codec:",
    result["audio_codec"]
)

print(
    "Sample rate:",
    result["sample_rate"]
)

print(
    "Channels:",
    result["channels"]
)


# ==================================================
# UPDATE MANIFEST
# ==================================================

stock[
    "validation"
] = result


stock[
    "status"
] = "validated"


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
print("MEDIA VALIDATION SUCCESS")
print("=" * 70)

print(
    "Media ID:",
    selected.get(
        "media_id"
    )
)

print(
    "Status:",
    stock[
        "status"
    ]
)

print(
    "Validated file:",
    result[
        "path"
    ]
)