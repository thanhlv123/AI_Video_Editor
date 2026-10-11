from dataclasses import dataclass, asdict
from copy import deepcopy
import math


@dataclass
class Scene:
    id: str
    start: float
    end: float
    duration: float
    text: str
    subtitle_ids: list

    # Backward compatible with older code.
    scene_type: str = "speech"

    def to_dict(self):
        return asdict(self)


class SceneBuilder:
    """
    Scene Builder V2

    Goals:

    1. Keep the original audio timeline.
    2. Create continuous visual coverage.
    3. Never intentionally create a scene longer
       than max_duration.
    4. Split long subtitles into several scenes.
    5. Split long subtitle TEXT between those scenes
       instead of repeating the whole sentence.
    6. Large gaps become explicit GAP scenes.
    7. Small gaps are absorbed into neighboring
       visual scenes whenever possible.

    Important:

    Speech timestamps are NOT shifted or compressed.
    We are only deciding how visual scenes cover
    the audio timeline.
    """

    def __init__(
        self,
        target_duration=5.0,
        max_duration=8.0,
        gap_threshold=2.0,
    ):

        self.target_duration = float(
            target_duration
        )

        self.max_duration = float(
            max_duration
        )

        self.gap_threshold = float(
            gap_threshold
        )


        if self.target_duration <= 0:

            raise ValueError(
                "target_duration must be > 0"
            )


        if self.max_duration <= 0:

            raise ValueError(
                "max_duration must be > 0"
            )


        if (
            self.target_duration
            > self.max_duration
        ):

            raise ValueError(
                "target_duration cannot be "
                "greater than max_duration"
            )


        if self.gap_threshold < 0:

            raise ValueError(
                "gap_threshold cannot be negative"
            )


    # ==================================================
    # BUILD
    # ==================================================

    def build(
        self,
        subtitles,
        timeline_start=None,
        timeline_end=None,
        include_gaps=False,
    ):

        if not subtitles:
            return []


        # ==================================================
        # SORT SUBTITLES
        # ==================================================

        subtitles = sorted(
            subtitles,
            key=lambda subtitle: (
                float(
                    subtitle.start
                ),
                float(
                    subtitle.end
                ),
            )
        )


        # ==================================================
        # SUBTITLES -> PIECES
        #
        # Long subtitles are split here.
        # ==================================================

        pieces = []


        for subtitle in subtitles:

            subtitle_pieces = (
                self._subtitle_to_pieces(
                    subtitle
                )
            )


            pieces.extend(
                subtitle_pieces
            )


        if not pieces:
            return []


        # ==================================================
        # BUILD SPEECH SCENES
        # ==================================================

        speech_scenes = (
            self._build_speech_scenes(
                pieces
            )
        )


        if not speech_scenes:
            return []


        # ==================================================
        # OLD COMPATIBILITY MODE
        #
        # Other old tests can still call:
        #
        # builder.build(subtitles)
        #
        # without creating gap scenes.
        # ==================================================

        if not include_gaps:

            return self._renumber_scenes(
                speech_scenes
            )


        # ==================================================
        # FULL TIMELINE MODE
        # ==================================================

        if timeline_start is None:

            timeline_start = (
                speech_scenes[0].start
            )


        if timeline_end is None:

            timeline_end = (
                speech_scenes[-1].end
            )


        timeline_start = float(
            timeline_start
        )

        timeline_end = float(
            timeline_end
        )


        if timeline_start < 0:

            timeline_start = 0.0


        if (
            timeline_end
            < timeline_start
        ):

            raise ValueError(
                "timeline_end must be >= "
                "timeline_start"
            )


        # ==================================================
        # CREATE CONTINUOUS VISUAL TIMELINE
        # ==================================================

        visual_scenes = (
            self._build_continuous_timeline(
                speech_scenes=speech_scenes,
                timeline_start=timeline_start,
                timeline_end=timeline_end,
            )
        )


        visual_scenes.sort(
            key=lambda scene: (
                scene.start,
                scene.end,
            )
        )


        return self._renumber_scenes(
            visual_scenes
        )


    # ==================================================
    # SUBTITLE -> PIECES
    # ==================================================

    def _subtitle_to_pieces(
        self,
        subtitle,
    ):

        start = float(
            subtitle.start
        )

        end = float(
            subtitle.end
        )


        if end <= start:

            return []


        text = str(
            getattr(
                subtitle,
                "text",
                ""
            )
            or ""
        ).strip()


        subtitle_id = (
            self._get_subtitle_id(
                subtitle
            )
        )


        duration = (
            end - start
        )


        # ==================================================
        # NORMAL SUBTITLE
        # ==================================================

        if (
            duration
            <= self.max_duration
        ):

            return [
                {
                    "start":
                        start,

                    "end":
                        end,

                    "text":
                        text,

                    "subtitle_ids": [
                        subtitle_id
                    ],
                }
            ]


        # ==================================================
        # LONG SUBTITLE
        #
        # Example:
        #
        # 28 seconds
        # max_duration = 8
        #
        # ceil(28 / 8) = 4 scenes
        #
        # each scene ~= 7 sec
        #
        # This is better than splitting it into
        # six ~4.6 second duplicated scenes.
        # ==================================================

        chunk_count = max(
            2,
            math.ceil(
                duration
                / self.max_duration
            )
        )


        # ==================================================
        # SPLIT TEXT
        # ==================================================

        text_chunks = (
            self._split_text(
                text=text,
                chunk_count=chunk_count,
            )
        )


        # ==================================================
        # SPLIT TIMELINE EVENLY
        # ==================================================

        chunk_duration = (
            duration
            / chunk_count
        )


        pieces = []


        for index in range(
            chunk_count
        ):

            piece_start = (
                start
                + (
                    index
                    * chunk_duration
                )
            )


            if (
                index
                == chunk_count - 1
            ):

                piece_end = end

            else:

                piece_end = (
                    start
                    + (
                        (
                            index + 1
                        )
                        * chunk_duration
                    )
                )


            pieces.append(
                {
                    "start":
                        piece_start,

                    "end":
                        piece_end,

                    "text":
                        text_chunks[
                            index
                        ],

                    "subtitle_ids": [
                        subtitle_id
                    ],
                }
            )


        return pieces


    # ==================================================
    # SPLIT TEXT BETWEEN LONG SUBTITLE PIECES
    # ==================================================

    def _split_text(
        self,
        text,
        chunk_count,
    ):

        text = str(
            text
            or ""
        ).strip()


        if chunk_count <= 1:

            return [
                text
            ]


        if not text:

            return [
                ""
                for _ in range(
                    chunk_count
                )
            ]


        words = text.split()


        if not words:

            return [
                ""
                for _ in range(
                    chunk_count
                )
            ]


        # ==================================================
        # DISTRIBUTE WORDS AS EVENLY AS POSSIBLE
        #
        # Example:
        #
        # 12 words / 4 scenes
        #
        # scene 1 = words 1-3
        # scene 2 = words 4-6
        # scene 3 = words 7-9
        # scene 4 = words 10-12
        #
        # No complete sentence repetition.
        # ==================================================

        base_size = (
            len(words)
            // chunk_count
        )

        remainder = (
            len(words)
            % chunk_count
        )


        result = []

        cursor = 0


        for index in range(
            chunk_count
        ):

            size = base_size


            if index < remainder:

                size += 1


            if size <= 0:

                result.append(
                    ""
                )

                continue


            chunk_words = words[
                cursor:
                cursor + size
            ]


            cursor += size


            result.append(
                " ".join(
                    chunk_words
                ).strip()
            )


        # Safety:
        # always return exactly chunk_count entries.

        while (
            len(result)
            < chunk_count
        ):

            result.append(
                ""
            )


        return result[
            :chunk_count
        ]


    # ==================================================
    # BUILD SPEECH SCENES
    # ==================================================

    def _build_speech_scenes(
        self,
        pieces,
    ):

        scenes = []

        current_pieces = []


        for piece in pieces:

            if not current_pieces:

                current_pieces = [
                    piece
                ]

                continue


            current_start = float(
                current_pieces[0][
                    "start"
                ]
            )

            current_end = float(
                current_pieces[-1][
                    "end"
                ]
            )


            current_duration = (
                current_end
                - current_start
            )


            gap = (
                float(
                    piece[
                        "start"
                    ]
                )
                - current_end
            )


            proposed_end = max(
                current_end,
                float(
                    piece[
                        "end"
                    ]
                )
            )


            proposed_duration = (
                proposed_end
                - current_start
            )


            # ==================================================
            # LARGE GAP
            #
            # Do not combine speech from opposite
            # sides of a real silent/music gap.
            # ==================================================

            if (
                gap
                >= self.gap_threshold
            ):

                scenes.append(
                    self._create_speech_scene(
                        current_pieces
                    )
                )

                current_pieces = [
                    piece
                ]

                continue


            # ==================================================
            # MAXIMUM DURATION
            # ==================================================

            if (
                proposed_duration
                > self.max_duration
            ):

                scenes.append(
                    self._create_speech_scene(
                        current_pieces
                    )
                )

                current_pieces = [
                    piece
                ]

                continue


            # ==================================================
            # TARGET ALREADY REACHED
            #
            # Prefer approximately 5-8 second scenes
            # rather than making unnecessary long scenes.
            # ==================================================

            if (
                current_duration
                >= self.target_duration
            ):

                scenes.append(
                    self._create_speech_scene(
                        current_pieces
                    )
                )

                current_pieces = [
                    piece
                ]

                continue


            # ==================================================
            # SAFE TO COMBINE
            # ==================================================

            current_pieces.append(
                piece
            )


        # ==================================================
        # FLUSH LAST SCENE
        # ==================================================

        if current_pieces:

            scenes.append(
                self._create_speech_scene(
                    current_pieces
                )
            )


        return scenes


    # ==================================================
    # CREATE SPEECH SCENE
    # ==================================================

    def _create_speech_scene(
        self,
        pieces,
    ):

        start = float(
            pieces[0][
                "start"
            ]
        )

        end = float(
            pieces[-1][
                "end"
            ]
        )


        texts = []

        subtitle_ids = []


        for piece in pieces:

            text = str(
                piece.get(
                    "text",
                    ""
                )
                or ""
            ).strip()


            if text:

                texts.append(
                    text
                )


            for subtitle_id in (
                piece.get(
                    "subtitle_ids",
                    []
                )
            ):

                if (
                    subtitle_id
                    not in subtitle_ids
                ):

                    subtitle_ids.append(
                        subtitle_id
                    )


        scene_text = " ".join(
            texts
        ).strip()


        return Scene(
            id="",

            start=start,

            end=end,

            duration=(
                end - start
            ),

            text=scene_text,

            subtitle_ids=subtitle_ids,

            scene_type="speech",
        )


    # ==================================================
    # BUILD CONTINUOUS VISUAL TIMELINE
    # ==================================================

    def _build_continuous_timeline(
        self,
        speech_scenes,
        timeline_start,
        timeline_end,
    ):

        speech_scenes = [
            deepcopy(
                scene
            )
            for scene in speech_scenes
        ]


        speech_scenes.sort(
            key=lambda scene: (
                scene.start,
                scene.end,
            )
        )


        output = []

        cursor = float(
            timeline_start
        )


        for scene in speech_scenes:

            # ==================================================
            # IGNORE SCENES COMPLETELY BEFORE TIMELINE
            # ==================================================

            if (
                scene.end
                <= timeline_start
            ):

                continue


            # ==================================================
            # STOP AFTER TIMELINE END
            # ==================================================

            if (
                scene.start
                >= timeline_end
            ):

                break


            # ==================================================
            # CLAMP TO TIMELINE
            # ==================================================

            if (
                scene.start
                < timeline_start
            ):

                scene.start = (
                    timeline_start
                )


            if (
                scene.end
                > timeline_end
            ):

                scene.end = (
                    timeline_end
                )


            scene.duration = (
                scene.end
                - scene.start
            )


            # ==================================================
            # GAP BEFORE CURRENT SPEECH SCENE
            # ==================================================

            gap = (
                scene.start
                - cursor
            )


            if gap > 0.001:

                # ==================================================
                # LARGE GAP
                #
                # Example:
                #
                # 0 -> 16.52 sec
                #
                # Create explicit GAP scenes.
                # ==================================================

                if (
                    gap
                    >= self.gap_threshold
                ):

                    gap_scenes = (
                        self._create_gap_chunks(
                            start=cursor,
                            end=scene.start,
                        )
                    )


                    output.extend(
                        gap_scenes
                    )


                    cursor = (
                        scene.start
                    )


                # ==================================================
                # SHORT GAP
                #
                # Examples:
                #
                # 0.72 sec
                # 1.00 sec
                #
                # Do NOT create a separate stock scene
                # if we can absorb it.
                # ==================================================

                else:

                    absorbed = False


                    # ----------------------------------------------
                    # OPTION 1:
                    # Extend previous SPEECH scene.
                    # ----------------------------------------------

                    if output:

                        previous = (
                            output[-1]
                        )


                        if (
                            previous.scene_type
                            == "speech"
                        ):

                            extended_duration = (
                                scene.start
                                - previous.start
                            )


                            if (
                                extended_duration
                                <= self.max_duration
                            ):

                                previous.end = (
                                    scene.start
                                )

                                previous.duration = (
                                    previous.end
                                    - previous.start
                                )

                                cursor = (
                                    scene.start
                                )

                                absorbed = True


                    # ----------------------------------------------
                    # OPTION 2:
                    # Extend current scene backwards.
                    # ----------------------------------------------

                    if not absorbed:

                        extended_duration = (
                            scene.end
                            - cursor
                        )


                        if (
                            extended_duration
                            <= self.max_duration
                        ):

                            scene.start = (
                                cursor
                            )

                            scene.duration = (
                                scene.end
                                - scene.start
                            )

                            absorbed = True


                    # ----------------------------------------------
                    # FALLBACK
                    #
                    # If neither neighboring speech scene can
                    # absorb the gap without exceeding max duration,
                    # preserve timing with a tiny GAP scene.
                    #
                    # This should be uncommon.
                    # ----------------------------------------------

                    if not absorbed:

                        gap_scenes = (
                            self._create_gap_chunks(
                                start=cursor,
                                end=scene.start,
                            )
                        )


                        output.extend(
                            gap_scenes
                        )


                        cursor = (
                            scene.start
                        )


            # ==================================================
            # OVERLAP PROTECTION
            # ==================================================

            if (
                scene.start
                < cursor
            ):

                scene.start = (
                    cursor
                )

                scene.duration = (
                    scene.end
                    - scene.start
                )


            if (
                scene.end
                <= scene.start
            ):

                continue


            # ==================================================
            # FINAL SAFETY
            # ==================================================

            if (
                scene.duration
                > self.max_duration
                + 0.001
            ):

                split_scenes = (
                    self._split_scene_to_max(
                        scene
                    )
                )


                output.extend(
                    split_scenes
                )


                cursor = (
                    split_scenes[-1].end
                )


                continue


            output.append(
                scene
            )


            cursor = (
                scene.end
            )


        # ==================================================
        # TRAILING AREA
        # ==================================================

        trailing_gap = (
            timeline_end
            - cursor
        )


        if trailing_gap > 0.001:

            # ==================================================
            # SHORT TRAILING GAP
            # ==================================================

            if (
                trailing_gap
                < self.gap_threshold
                and output
            ):

                previous = (
                    output[-1]
                )


                extended_duration = (
                    timeline_end
                    - previous.start
                )


                if (
                    previous.scene_type
                    == "speech"
                    and extended_duration
                    <= self.max_duration
                ):

                    previous.end = (
                        timeline_end
                    )

                    previous.duration = (
                        previous.end
                        - previous.start
                    )

                    cursor = (
                        timeline_end
                    )


            # ==================================================
            # STILL NOT COVERED
            # ==================================================

            if (
                timeline_end
                - cursor
                > 0.001
            ):

                output.extend(
                    self._create_gap_chunks(
                        start=cursor,
                        end=timeline_end,
                    )
                )


        return output


    # ==================================================
    # SPLIT A SCENE THAT EXCEEDS MAX DURATION
    # ==================================================

    def _split_scene_to_max(
        self,
        scene,
    ):

        duration = (
            scene.end
            - scene.start
        )


        if (
            duration
            <= self.max_duration
        ):

            return [
                scene
            ]


        chunk_count = (
            math.ceil(
                duration
                / self.max_duration
            )
        )


        text_chunks = (
            self._split_text(
                text=scene.text,
                chunk_count=chunk_count,
            )
        )


        chunk_duration = (
            duration
            / chunk_count
        )


        output = []


        for index in range(
            chunk_count
        ):

            start = (
                scene.start
                + (
                    index
                    * chunk_duration
                )
            )


            if (
                index
                == chunk_count - 1
            ):

                end = (
                    scene.end
                )

            else:

                end = (
                    scene.start
                    + (
                        (
                            index + 1
                        )
                        * chunk_duration
                    )
                )


            output.append(
                Scene(
                    id="",

                    start=start,

                    end=end,

                    duration=(
                        end
                        - start
                    ),

                    text=(
                        text_chunks[
                            index
                        ]
                    ),

                    subtitle_ids=list(
                        scene.subtitle_ids
                    ),

                    scene_type=(
                        scene.scene_type
                    ),
                )
            )


        return output


    # ==================================================
    # CREATE GAP CHUNKS
    # ==================================================

    def _create_gap_chunks(
        self,
        start,
        end,
    ):

        start = float(
            start
        )

        end = float(
            end
        )


        duration = (
            end
            - start
        )


        if duration <= 0.001:

            return []


        # ==================================================
        # SHORT ENOUGH
        # ==================================================

        if (
            duration
            <= self.max_duration
        ):

            return [
                Scene(
                    id="",

                    start=start,

                    end=end,

                    duration=duration,

                    text="",

                    subtitle_ids=[],

                    scene_type="gap",
                )
            ]


        # ==================================================
        # LONG GAP
        #
        # Example:
        #
        # 16.52 sec
        #
        # max 8 sec
        #
        # → 3 scenes ~= 5.5 sec each
        # ==================================================

        chunk_count = (
            math.ceil(
                duration
                / self.max_duration
            )
        )


        chunk_duration = (
            duration
            / chunk_count
        )


        scenes = []


        for index in range(
            chunk_count
        ):

            chunk_start = (
                start
                + (
                    index
                    * chunk_duration
                )
            )


            if (
                index
                == chunk_count - 1
            ):

                chunk_end = end

            else:

                chunk_end = (
                    start
                    + (
                        (
                            index + 1
                        )
                        * chunk_duration
                    )
                )


            scenes.append(
                Scene(
                    id="",

                    start=chunk_start,

                    end=chunk_end,

                    duration=(
                        chunk_end
                        - chunk_start
                    ),

                    text="",

                    subtitle_ids=[],

                    scene_type="gap",
                )
            )


        return scenes


    # ==================================================
    # GET SUBTITLE ID
    # ==================================================

    def _get_subtitle_id(
        self,
        subtitle,
    ):

        for attribute in (
            "id",
            "index",
            "number",
        ):

            value = getattr(
                subtitle,
                attribute,
                None
            )


            if value is not None:

                return value


        return None


    # ==================================================
    # RENUMBER
    # ==================================================

    def _renumber_scenes(
        self,
        scenes,
    ):

        scenes = sorted(
            scenes,
            key=lambda scene: (
                scene.start,
                scene.end,
            )
        )


        for index, scene in enumerate(
            scenes,
            start=1
        ):

            scene.id = (
                f"scene_{index:03d}"
            )


            scene.start = float(
                scene.start
            )

            scene.end = float(
                scene.end
            )

            scene.duration = (
                scene.end
                - scene.start
            )


        return scenes