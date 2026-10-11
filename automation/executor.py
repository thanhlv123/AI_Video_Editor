from automation.command_registry import validate_command
from core.media_importer import MediaImporter


class CommandExecutor:

    def __init__(self, operation_manager):

        self.operations = operation_manager
        self.media_importer = MediaImporter()


    def execute(self, command):

        # ==============================================
        # VALIDATE COMMAND OBJECT
        # ==============================================

        if not isinstance(command, dict):

            raise ValueError(
                "Command must be a dictionary."
            )


        # ==============================================
        # GET COMMAND NAME
        # ==============================================

        command_name = command.get(
            "command"
        )

        if not command_name:

            raise ValueError(
                "Command name is required."
            )


        # ==============================================
        # GET PARAMETERS
        # ==============================================

        parameters = command.get(
            "parameters",
            {}
        )


        # ==============================================
        # VALIDATE PARAMETERS
        # ==============================================

        validate_command(
            command_name,
            parameters
        )


        # ==============================================
        # MEDIA IMPORT
        # ==============================================

        if command_name == "media.import":

            media = self.media_importer.import_file(

                file_path=parameters["path"],

                media_id=parameters.get(
                    "media_id"
                )
            )

            self.operations.project.add_media(
                media
            )

            return {
                "success": True,
                "command": command_name,
                "media": media.to_dict(),
                "revision": self.operations.project.revision
            }


        # ==============================================
        # ADD CLIP
        # ==============================================

        elif command_name == "timeline.add_clip":

            clip = self.operations.add_clip(

                clip_id=parameters["clip_id"],

                media_id=parameters["media_id"],

                track_id=parameters["track_id"],

                start=parameters["start"],

                duration=parameters["duration"],

                source_start=parameters.get(
                    "source_start",
                    0.0
                ),

                author=parameters.get(
                    "author",
                    "automation"
                )
            )

            return {
                "success": True,
                "command": command_name,
                "clip": clip.to_dict(),
                "revision": self.operations.project.revision
            }


        # ==============================================
        # MOVE CLIP
        # ==============================================

        elif command_name == "timeline.move_clip":

            clip = self.operations.move_clip(

                clip_id=parameters["clip_id"],

                new_start=parameters["new_start"],

                author=parameters.get(
                    "author",
                    "automation"
                )
            )

            return {
                "success": True,
                "command": command_name,
                "clip": clip.to_dict(),
                "revision": self.operations.project.revision
            }


        # ==============================================
        # TRIM CLIP
        # ==============================================

        elif command_name == "timeline.trim_clip":

            clip = self.operations.trim_clip(

                clip_id=parameters["clip_id"],

                new_duration=parameters[
                    "new_duration"
                ],

                author=parameters.get(
                    "author",
                    "automation"
                )
            )

            return {
                "success": True,
                "command": command_name,
                "clip": clip.to_dict(),
                "revision": self.operations.project.revision
            }


        # ==============================================
        # DELETE CLIP
        # ==============================================

        elif command_name == "timeline.delete_clip":

            self.operations.delete_clip(

                clip_id=parameters["clip_id"],

                author=parameters.get(
                    "author",
                    "automation"
                )
            )

            return {
                "success": True,
                "command": command_name,
                "revision": self.operations.project.revision
            }


        # ==============================================
        # UNDO
        # ==============================================

        elif command_name == "history.undo":

            success = self.operations.undo()

            return {
                "success": success,
                "command": command_name,
                "revision": self.operations.project.revision
            }


        # ==============================================
        # NOT IMPLEMENTED
        # ==============================================

        raise ValueError(
            f"Command not implemented: {command_name}"
        )