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


from stock.downloader import (
    DownloadManager,
    DownloadError
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("DOWNLOAD MANAGER TEST")
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


if not selected:

    raise RuntimeError(
        "No selected_media found."
    )


print()
print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Provider:",
    selected.get(
        "provider"
    )
)

print(
    "Media ID:",
    selected.get(
        "media_id"
    )
)

print(
    "Type:",
    selected.get(
        "media_type"
    )
)

print(
    "Expected resolution:",
    f"{selected.get('width')}x"
    f"{selected.get('height')}"
)


# ==================================================
# DOWNLOAD
# ==================================================

output_dir = (
    ROOT
    / "media"
    / "downloads"
)


manager = DownloadManager(
    output_dir=output_dir
)


print()
print(
    "Downloading selected media..."
)


try:

    result = manager.download(

        media=selected,

        scene_id=scene[
            "scene_id"
        ]
    )

except DownloadError as error:

    print()
    print("=" * 70)
    print("DOWNLOAD FAILED")
    print("=" * 70)
    print(error)

    raise SystemExit(1)


# ==================================================
# UPDATE MANIFEST
# ==================================================

stock[
    "download"
] = {

    "status": result[
        "status"
    ],

    "path": result[
        "path"
    ],

    "filename": result[
        "filename"
    ],

    "size": result[
        "size"
    ]
}


stock[
    "status"
] = "downloaded"


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
print("DOWNLOAD SUCCESS")
print("=" * 70)

print(
    "Status:",
    result["status"]
)

print(
    "Filename:",
    result["filename"]
)

print(
    "Path:",
    result["path"]
)

print(
    "Size:",
    result["size"],
    "bytes"
)

print(
    "Manifest status:",
    stock["status"]
)