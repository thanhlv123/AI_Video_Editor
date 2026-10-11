import re
from copy import deepcopy


class TranscriptionCleanerError(Exception):
    pass


class TranscriptionCleaner:
    """
    Clean and normalize Whisper transcription segments
    without changing the original audio timeline.

    Main responsibilities:

    1. Remove empty/invalid segments.
    2. Clamp timestamps to real audio duration.
    3. Remove obvious hallucination-like segments.
    4. Detect timeline gaps.
    5. Re-index segments.
    6. Preserve the original timing whenever possible.
    """

    def __init__(
        self,
        minimum_duration=0.10,
        gap_threshold=2.0,
        repeated_char_threshold=12,
        repeated_ratio_threshold=0.80
    ):

        self.minimum_duration = float(
            minimum_duration
        )

        self.gap_threshold = float(
            gap_threshold
        )

        self.repeated_char_threshold = int(
            repeated_char_threshold
        )

        self.repeated_ratio_threshold = float(
            repeated_ratio_threshold
        )


    # ==================================================
    # CLEAN TRANSCRIPTION
    # ==================================================

    def clean(
        self,
        transcription,
        audio_duration=None
    ):

        if not isinstance(
            transcription,
            dict
        ):
            raise TranscriptionCleanerError(
                "Transcription must be a dictionary."
            )


        raw_segments = transcription.get(
            "segments",
            []
        )


        if not isinstance(
            raw_segments,
            list
        ):
            raise TranscriptionCleanerError(
                "Transcription segments must be a list."
            )


        # --------------------------------------------------
        # GET AUDIO DURATION
        # --------------------------------------------------

        if audio_duration is None:

            audio_duration = transcription.get(
                "duration"
            )


        if audio_duration is not None:

            try:

                audio_duration = float(
                    audio_duration
                )

            except (
                TypeError,
                ValueError
            ) as error:

                raise TranscriptionCleanerError(
                    "Invalid audio duration."
                ) from error


            if audio_duration <= 0:

                audio_duration = None


        # --------------------------------------------------
        # CLEAN SEGMENTS
        # --------------------------------------------------

        cleaned_segments = []

        removed_segments = []

        clamped_segments = []


        for raw_segment in raw_segments:

            result = self._clean_segment(
                raw_segment=raw_segment,
                audio_duration=audio_duration
            )


            status = result[
                "status"
            ]


            if status == "removed":

                removed_segments.append(
                    result[
                        "segment"
                    ]
                )

                continue


            segment = result[
                "segment"
            ]


            if status == "clamped":

                clamped_segments.append(
                    deepcopy(
                        segment
                    )
                )


            cleaned_segments.append(
                segment
            )


        # --------------------------------------------------
        # SORT BY TIMESTAMP
        # --------------------------------------------------

        cleaned_segments.sort(
            key=lambda item: (
                item["start"],
                item["end"]
            )
        )


        # --------------------------------------------------
        # REMOVE OVERLAP CAUSED BY BAD TIMESTAMPS
        # --------------------------------------------------

        normalized_segments = []

        previous_end = 0.0


        for segment in cleaned_segments:

            segment = deepcopy(
                segment
            )


            if (
                segment["start"]
                < previous_end
            ):

                segment[
                    "start"
                ] = previous_end


            if (
                segment["end"]
                <= segment["start"]
            ):

                removed_segments.append({

                    **segment,

                    "removed_reason":
                        "invalid_after_overlap_normalization"
                })

                continue


            duration = (
                segment["end"]
                - segment["start"]
            )


            if (
                duration
                < self.minimum_duration
            ):

                removed_segments.append({

                    **segment,

                    "removed_reason":
                        "too_short_after_normalization"
                })

                continue


            normalized_segments.append(
                segment
            )


            previous_end = segment[
                "end"
            ]


        # --------------------------------------------------
        # RE-INDEX
        # --------------------------------------------------

        for index, segment in enumerate(
            normalized_segments,
            start=1
        ):

            segment[
                "index"
            ] = index


        # --------------------------------------------------
        # DETECT GAPS
        # --------------------------------------------------

        gaps = self._detect_gaps(
            segments=normalized_segments,
            audio_duration=audio_duration
        )


        # --------------------------------------------------
        # BUILD RESULT
        # --------------------------------------------------

        cleaned_transcription = deepcopy(
            transcription
        )


        cleaned_transcription[
            "segments"
        ] = normalized_segments


        cleaned_transcription[
            "duration"
        ] = audio_duration


        cleaned_transcription[
            "cleaning"
        ] = {

            "raw_segment_count":
                len(raw_segments),

            "clean_segment_count":
                len(normalized_segments),

            "removed_segment_count":
                len(removed_segments),

            "clamped_segment_count":
                len(clamped_segments),

            "gap_count":
                len(gaps),

            "removed_segments":
                removed_segments,

            "clamped_segments":
                clamped_segments,

            "gaps":
                gaps
        }


        return cleaned_transcription


    # ==================================================
    # CLEAN SINGLE SEGMENT
    # ==================================================

    def _clean_segment(
        self,
        raw_segment,
        audio_duration
    ):

        if not isinstance(
            raw_segment,
            dict
        ):

            return {

                "status": "removed",

                "segment": {
                    "raw": raw_segment,
                    "removed_reason":
                        "segment_not_dictionary"
                }
            }


        segment = deepcopy(
            raw_segment
        )


        text = segment.get(
            "text",
            ""
        )


        if text is None:

            text = ""


        text = str(
            text
        ).strip()


        # Collapse repeated whitespace.

        text = re.sub(
            r"\s+",
            " ",
            text
        )


        segment[
            "text"
        ] = text


        # --------------------------------------------------
        # EMPTY TEXT
        # --------------------------------------------------

        if not text:

            segment[
                "removed_reason"
            ] = "empty_text"

            return {
                "status": "removed",
                "segment": segment
            }


        # --------------------------------------------------
        # TIMESTAMPS
        # --------------------------------------------------

        try:

            start = float(
                segment.get(
                    "start",
                    0.0
                )
            )

            end = float(
                segment.get(
                    "end",
                    0.0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            segment[
                "removed_reason"
            ] = "invalid_timestamp"

            return {
                "status": "removed",
                "segment": segment
            }


        # Negative start should never survive.

        start = max(
            0.0,
            start
        )


        # --------------------------------------------------
        # SEGMENT STARTS AFTER AUDIO
        # --------------------------------------------------

        if (
            audio_duration is not None
            and start >= audio_duration
        ):

            segment[
                "removed_reason"
            ] = "starts_after_audio"

            return {
                "status": "removed",
                "segment": segment
            }


        was_clamped = False


        # --------------------------------------------------
        # CLAMP END TO REAL AUDIO DURATION
        # --------------------------------------------------

        if (
            audio_duration is not None
            and end > audio_duration
        ):

            segment[
                "original_end"
            ] = end

            end = audio_duration

            was_clamped = True


        segment[
            "start"
        ] = start

        segment[
            "end"
        ] = end


        # --------------------------------------------------
        # INVALID DURATION
        # --------------------------------------------------

        if end <= start:

            segment[
                "removed_reason"
            ] = "end_before_start"

            return {
                "status": "removed",
                "segment": segment
            }


        duration = (
            end - start
        )


        if (
            duration
            < self.minimum_duration
        ):

            segment[
                "removed_reason"
            ] = "segment_too_short"

            return {
                "status": "removed",
                "segment": segment
            }


        # --------------------------------------------------
        # OBVIOUS HALLUCINATION
        # --------------------------------------------------

        hallucination_reason = (
            self._detect_hallucination(
                text
            )
        )


        if hallucination_reason:

            segment[
                "removed_reason"
            ] = hallucination_reason

            return {
                "status": "removed",
                "segment": segment
            }


        # --------------------------------------------------
        # SUCCESS
        # --------------------------------------------------

        segment[
            "duration"
        ] = duration


        return {

            "status": (
                "clamped"
                if was_clamped
                else "clean"
            ),

            "segment": segment
        }


    # ==================================================
    # DETECT OBVIOUS HALLUCINATION
    # ==================================================

    def _detect_hallucination(
        self,
        text
    ):

        compact = re.sub(
            r"[^A-Za-z0-9]+",
            "",
            text
        )


        if not compact:

            return (
                "no_alphanumeric_content"
            )


        # --------------------------------------------------
        # SAME CHARACTER REPEATED MANY TIMES
        #
        # Example:
        # ooooooooooooooooooooooooooooo
        # --------------------------------------------------

        if (
            len(compact)
            >= self.repeated_char_threshold
        ):

            counts = {}


            for char in compact.lower():

                counts[char] = (
                    counts.get(
                        char,
                        0
                    )
                    + 1
                )


            largest_count = max(
                counts.values()
            )


            ratio = (
                largest_count
                / len(compact)
            )


            if (
                ratio
                >= self.repeated_ratio_threshold
            ):

                return (
                    "repeated_character_hallucination"
                )


        # --------------------------------------------------
        # REPEATED WORD
        #
        # Example:
        # hello hello hello hello hello...
        # --------------------------------------------------

        words = re.findall(
            r"[A-Za-z0-9']+",
            text.lower()
        )


        if len(words) >= 6:

            unique_words = set(
                words
            )


            if len(unique_words) == 1:

                return (
                    "repeated_word_hallucination"
                )


        return None


    # ==================================================
    # DETECT TIMELINE GAPS
    # ==================================================

    def _detect_gaps(
        self,
        segments,
        audio_duration
    ):

        gaps = []


        if not segments:

            if (
                audio_duration is not None
                and audio_duration > 0
            ):

                gaps.append({

                    "start": 0.0,

                    "end":
                        audio_duration,

                    "duration":
                        audio_duration,

                    "type":
                        "full_audio_gap"
                })


            return gaps


        # --------------------------------------------------
        # GAP BEFORE FIRST SPEECH
        # --------------------------------------------------

        first_start = segments[
            0
        ][
            "start"
        ]


        if (
            first_start
            >= self.gap_threshold
        ):

            gaps.append({

                "start": 0.0,

                "end": first_start,

                "duration":
                    first_start,

                "type":
                    "leading_gap"
            })


        # --------------------------------------------------
        # GAPS BETWEEN SEGMENTS
        # --------------------------------------------------

        for previous, current in zip(
            segments,
            segments[1:]
        ):

            gap_start = previous[
                "end"
            ]

            gap_end = current[
                "start"
            ]

            gap_duration = (
                gap_end
                - gap_start
            )


            if (
                gap_duration
                >= self.gap_threshold
            ):

                gaps.append({

                    "start":
                        gap_start,

                    "end":
                        gap_end,

                    "duration":
                        gap_duration,

                    "type":
                        "internal_gap"
                })


        # --------------------------------------------------
        # GAP AFTER LAST SPEECH
        # --------------------------------------------------

        if audio_duration is not None:

            last_end = segments[
                -1
            ][
                "end"
            ]


            trailing_duration = (
                audio_duration
                - last_end
            )


            if (
                trailing_duration
                >= self.gap_threshold
            ):

                gaps.append({

                    "start":
                        last_end,

                    "end":
                        audio_duration,

                    "duration":
                        trailing_duration,

                    "type":
                        "trailing_gap"
                })


        return gaps