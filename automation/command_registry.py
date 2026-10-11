COMMANDS = {
        "media.import": {
        "description": "Import a media file and analyze it with FFprobe.",

        "required": [
            "path"
        ],

        "optional": [
            "media_id"
        ]
    },


    "timeline.add_clip": {
        "description": "Add a media clip to a timeline track.",

        "required": [
            "clip_id",
            "media_id",
            "track_id",
            "start",
            "duration"
        ],

        "optional": [
            "source_start",
            "author"
        ]
    },


    "timeline.move_clip": {
        "description": "Move a clip to a new timeline position.",

        "required": [
            "clip_id",
            "new_start"
        ],

        "optional": [
            "author"
        ]
    },


    "timeline.trim_clip": {
        "description": "Change clip duration.",

        "required": [
            "clip_id",
            "new_duration"
        ],

        "optional": [
            "author"
        ]
    },


    "timeline.delete_clip": {
        "description": "Delete a clip from the timeline.",

        "required": [
            "clip_id"
        ],

        "optional": [
            "author"
        ]
    },


    "history.undo": {
        "description": "Undo the most recent edit operation.",

        "required": [],

        "optional": []
    }
}


def get_command(name):

    return COMMANDS.get(name)


def list_commands():

    return COMMANDS


def validate_command(name, parameters):

    specification = get_command(name)

    if specification is None:

        raise ValueError(
            f"Unknown command: {name}"
        )

    required = specification.get(
        "required",
        []
    )

    for parameter in required:

        if parameter not in parameters:

            raise ValueError(
                f"Missing required parameter: {parameter}"
            )

    return True