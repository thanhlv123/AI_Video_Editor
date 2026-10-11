from copy import deepcopy
from typing import Optional

from core.timeline import Clip
from core.history import HistoryEntry, HistoryManager

from core.validation import (
    validate_clip,
    validate_clip_timing,
    validate_media,
    validate_track,
)


class OperationManager:

    def __init__(self, project):

        self.project = project

        self.history = HistoryManager()


    # ==================================================
    # INTERNAL COMMIT
    # ==================================================

    def _commit(
        self,
        operation,
        data,
        before,
        after,
        author
    ):

        self.project.revision += 1

        entry = HistoryEntry(
            operation=operation,
            data=deepcopy(data),
            before=deepcopy(before),
            after=deepcopy(after),
            revision=self.project.revision,
            author=author
        )

        self.history.add(entry)

        return entry


    # ==================================================
    # ADD CLIP
    # ==================================================

    def add_clip(
        self,
        clip_id,
        media_id,
        track_id,
        start,
        duration,
        source_start=0.0,
        author="user"
    ):

        validate_media(
            self.project,
            media_id
        )

        track = validate_track(
            self.project,
            track_id
        )

        validate_clip_timing(
            start,
            duration
        )

        if self.project.timeline.get_clip(clip_id):

            raise ValueError(
                f"Clip ID already exists: {clip_id}"
            )

        clip = Clip(
            id=clip_id,
            media_id=media_id,
            track_id=track_id,
            start=float(start),
            duration=float(duration),
            source_start=float(source_start)
        )

        track.add_clip(clip)

        self._commit(
            operation="ADD_CLIP",

            data={
                "clip_id": clip_id
            },

            before={},

            after=clip.to_dict(),

            author=author
        )

        return clip


    # ==================================================
    # MOVE CLIP
    # ==================================================

    def move_clip(
        self,
        clip_id,
        new_start,
        author="user"
    ):

        clip = validate_clip(
            self.project,
            clip_id
        )

        if new_start < 0:

            raise ValueError(
                "new_start cannot be negative"
            )

        before = clip.to_dict()

        clip.start = float(new_start)

        after = clip.to_dict()

        self._commit(
            operation="MOVE_CLIP",

            data={
                "clip_id": clip_id,
                "new_start": new_start
            },

            before=before,
            after=after,
            author=author
        )

        return clip


    # ==================================================
    # TRIM CLIP
    # ==================================================

    def trim_clip(
        self,
        clip_id,
        new_duration,
        author="user"
    ):

        clip = validate_clip(
            self.project,
            clip_id
        )

        validate_clip_timing(
            clip.start,
            new_duration
        )

        before = clip.to_dict()

        clip.duration = float(
            new_duration
        )

        after = clip.to_dict()

        self._commit(
            operation="TRIM_CLIP",

            data={
                "clip_id": clip_id,
                "new_duration": new_duration
            },

            before=before,
            after=after,
            author=author
        )

        return clip


    # ==================================================
    # DELETE CLIP
    # ==================================================

    def delete_clip(
        self,
        clip_id,
        author="user"
    ):

        clip = validate_clip(
            self.project,
            clip_id
        )

        before = clip.to_dict()

        track = self.project.timeline.get_track(
            clip.track_id
        )

        track.remove_clip(
            clip_id
        )

        self._commit(
            operation="DELETE_CLIP",

            data={
                "clip_id": clip_id
            },

            before=before,

            after={},

            author=author
        )


    # ==================================================
    # UNDO
    # ==================================================

    def undo(self):

        entry = self.history.pop()

        if entry is None:
            return False

        operation = entry.operation

        # ----------------------------------------------
        # Undo ADD_CLIP
        # ----------------------------------------------

        if operation == "ADD_CLIP":

            clip_id = entry.after["id"]

            clip = self.project.timeline.get_clip(
                clip_id
            )

            if clip:

                track = self.project.timeline.get_track(
                    clip.track_id
                )

                track.remove_clip(
                    clip_id
                )


        # ----------------------------------------------
        # Undo MOVE / TRIM
        # ----------------------------------------------

        elif operation in (
            "MOVE_CLIP",
            "TRIM_CLIP"
        ):

            clip_id = entry.before["id"]

            clip = self.project.timeline.get_clip(
                clip_id
            )

            if clip:

                clip.start = entry.before[
                    "start"
                ]

                clip.duration = entry.before[
                    "duration"
                ]

                clip.source_start = entry.before[
                    "source_start"
                ]


        # ----------------------------------------------
        # Undo DELETE
        # ----------------------------------------------

        elif operation == "DELETE_CLIP":

            data = entry.before

            clip = Clip(
                id=data["id"],
                media_id=data["media_id"],
                track_id=data["track_id"],
                start=data["start"],
                duration=data["duration"],
                source_start=data[
                    "source_start"
                ],
                source_duration=data[
                    "source_duration"
                ],
                enabled=data[
                    "enabled"
                ]
            )

            track = self.project.timeline.get_track(
                clip.track_id
            )

            track.add_clip(
                clip
            )


        # ----------------------------------------------
        # Revision
        # ----------------------------------------------

        self.project.revision += 1

        return True