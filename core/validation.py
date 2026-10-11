class ValidationError(Exception):
    pass


def validate_clip_timing(start, duration):

    if start < 0:
        raise ValidationError(
            "Clip start cannot be negative."
        )

    if duration <= 0:
        raise ValidationError(
            "Clip duration must be greater than zero."
        )


def validate_track(project, track_id):

    track = project.timeline.get_track(track_id)

    if track is None:
        raise ValidationError(
            f"Track not found: {track_id}"
        )

    if track.locked:
        raise ValidationError(
            f"Track is locked: {track_id}"
        )

    return track


def validate_media(project, media_id):

    media = project.get_media(media_id)

    if media is None:
        raise ValidationError(
            f"Media not found: {media_id}"
        )

    return media


def validate_clip(project, clip_id):

    clip = project.timeline.get_clip(clip_id)

    if clip is None:
        raise ValidationError(
            f"Clip not found: {clip_id}"
        )

    return clip