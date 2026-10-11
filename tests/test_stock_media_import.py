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


from core.project import Project
from core.operations import OperationManager
from automation.executor import CommandExecutor


print("=" * 70)
print("AI VIDEO EDITOR")
print("STOCK MEDIA IMPORT TEST")
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
    / "stock_import_test.json"
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


if not manifest.get("scenes"):

    raise RuntimeError(
        "Manifest contains no scenes."
    )


scene = manifest["scenes"][0]

stock = scene["stock"]


# ==================================================
# REQUIRE VALIDATED STOCK
# ==================================================

if stock.get("status") != "validated":

    raise RuntimeError(
        "Stock is not validated. "
        f"Current status: {stock.get('status')}"
    )


selected = stock.get(
    "selected_media"
)


download = stock.get(
    "download"
)


validation = stock.get(
    "validation"
)


if not selected:

    raise RuntimeError(
        "selected_media is missing."
    )


if not download:

    raise RuntimeError(
        "download information is missing."
    )


if not validation:

    raise RuntimeError(
        "validation information is missing."
    )


if not validation.get("valid"):

    raise RuntimeError(
        "Downloaded media is not valid."
    )


file_path = download.get(
    "path"
)


if not file_path:

    raise RuntimeError(
        "Downloaded media path is missing."
    )


# ==================================================
# STABLE MEDIA ID
# ==================================================

provider = selected.get(
    "provider",
    "stock"
)


source_media_id = str(
    selected.get(
        "media_id"
    )
)


project_media_id = (
    f"stock_"
    f"{provider}_"
    f"{source_media_id}"
)


print()

print(
    "Scene:",
    scene["scene_id"]
)

print(
    "Source media:",
    source_media_id
)

print(
    "Project media ID:",
    project_media_id
)

print(
    "File:",
    file_path
)


# ==================================================
# CREATE PROJECT
# ==================================================

project = Project(
    name="AI Stock Import Test"
)


operations = OperationManager(
    project
)


executor = CommandExecutor(
    operations
)


print()
print(
    "Initial project revision:",
    project.revision
)


# ==================================================
# MEDIA IMPORT COMMAND
# ==================================================

command = {

    "command": "media.import",

    "parameters": {

        "path": file_path,

        "media_id": project_media_id
    }
}


print()
print("=" * 70)
print("IMPORT COMMAND")
print("=" * 70)

print(
    json.dumps(
        command,
        indent=4,
        ensure_ascii=False
    )
)


# ==================================================
# EXECUTE
# ==================================================

result = executor.execute(
    command
)


imported = result[
    "media"
]


# ==================================================
# VERIFY
# ==================================================

if imported["id"] != project_media_id:

    raise RuntimeError(
        "Imported media ID does not match."
    )


if imported["media_type"] != "video":

    raise RuntimeError(
        "Imported stock is not video."
    )


if imported["duration"] <= 0:

    raise RuntimeError(
        "Imported duration is invalid."
    )


if not imported["width"]:

    raise RuntimeError(
        "Imported width is invalid."
    )


if not imported["height"]:

    raise RuntimeError(
        "Imported height is invalid."
    )


project_media = project.get_media(
    project_media_id
)


if project_media is None:

    raise RuntimeError(
        "Imported media was not added "
        "to project media library."
    )


# ==================================================
# DISPLAY IMPORT RESULT
# ==================================================

print()
print("=" * 70)
print("IMPORT RESULT")
print("=" * 70)

print(
    "ID:",
    imported["id"]
)

print(
    "Name:",
    imported["name"]
)

print(
    "Type:",
    imported["media_type"]
)

print(
    "Duration:",
    imported["duration"]
)

print(
    "Resolution:",
    f"{imported['width']}x"
    f"{imported['height']}"
)

print(
    "FPS:",
    imported["fps"]
)

print(
    "Has audio:",
    imported["has_audio"]
)

print(
    "Project revision:",
    project.revision
)

print(
    "Project media count:",
    len(project.media)
)


# ==================================================
# UPDATE MANIFEST
# ==================================================

timeline_data = scene.setdefault(
    "timeline",
    {}
)


timeline_data[
    "media_id"
] = project_media_id


stock[
    "import"
] = {

    "status": "imported",

    "project_media_id": (
        project_media_id
    ),

    "path": imported[
        "path"
    ],

    "duration": imported[
        "duration"
    ],

    "width": imported[
        "width"
    ],

    "height": imported[
        "height"
    ],

    "fps": imported[
        "fps"
    ],

    "has_audio": imported[
        "has_audio"
    ]
}


stock[
    "status"
] = "imported"


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
# SUCCESS
# ==================================================

print()
print("=" * 70)
print("STOCK MEDIA IMPORT SUCCESS")
print("=" * 70)

print(
    "Manifest status:",
    stock["status"]
)

print(
    "Timeline media_id:",
    timeline_data[
        "media_id"
    ]
)

print(
    "Project saved:",
    output_project_path
)

print(
    "Manifest updated:",
    manifest_path
)