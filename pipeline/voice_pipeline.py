from pathlib import Path

from transcription.whisper_transcriber import (
    WhisperTranscriber,
    WhisperTranscriptionError,
)

from transcription.cleaner import (
    TranscriptionCleaner,
    TranscriptionCleanerError,
)

from scenes.srt_parser import (
    SRTParser,
)

from scenes.scene_builder import (
    SceneBuilder,
)


class VoicePipelineError(Exception):
    pass


class VoicePipeline:
    """
    Complete voice processing pipeline.

    Audio
        ->
    Whisper transcription
        ->
    Transcription cleaner
        ->
    Clean SRT
        ->
    SRT parser
        ->
    Scene builder
        ->
    Full continuous visual timeline

    Important:
    - Original audio timestamps are preserved.
    - Long subtitles are split into shorter scenes.
    - Silent / music / no-speech gaps become gap scenes.
    - Visual timeline can cover the entire audio duration.
    """

    def __init__(
        self,
        model_size="small",
        device="cpu",
        compute_type="int8",
        language=None,
        beam_size=5,
        vad_filter=False,
        target_scene_duration=5.0,
        max_scene_duration=8.0,
        minimum_segment_duration=0.10,
        gap_threshold=2.0,
    ):

        self.language = language

        self.beam_size = int(
            beam_size
        )

        self.vad_filter = bool(
            vad_filter
        )

        self.target_scene_duration = float(
            target_scene_duration
        )

        self.max_scene_duration = float(
            max_scene_duration
        )

        self.gap_threshold = float(
            gap_threshold
        )


        # ==================================================
        # WHISPER
        # ==================================================

        self.transcriber = WhisperTranscriber(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
        )


        # ==================================================
        # CLEANER
        # ==================================================

        self.cleaner = TranscriptionCleaner(
            minimum_duration=minimum_segment_duration,
            gap_threshold=gap_threshold,
        )


        # ==================================================
        # SRT PARSER
        # ==================================================

        self.srt_parser = SRTParser()


        # ==================================================
        # SCENE BUILDER
        # ==================================================

        self.scene_builder = SceneBuilder(
            target_duration=target_scene_duration,
            max_duration=max_scene_duration,
            gap_threshold=gap_threshold,
        )


    # ==================================================
    # RUN
    # ==================================================

    def run(
        self,
        audio_path,
        srt_output_path,
    ):

        audio_path = Path(
            audio_path
        )

        srt_output_path = Path(
            srt_output_path
        )


        # ==================================================
        # VALIDATE INPUT
        # ==================================================

        if not audio_path.exists():

            raise FileNotFoundError(
                f"Audio file not found: "
                f"{audio_path}"
            )


        print("=" * 70)
        print("AI VIDEO EDITOR")
        print("VOICE PIPELINE")
        print("=" * 70)

        print()

        print(
            "Audio:",
            audio_path
        )

        print(
            "Clean SRT:",
            srt_output_path
        )

        print(
            "VAD filter:",
            self.vad_filter
        )

        print(
            "Target scene duration:",
            self.target_scene_duration
        )

        print(
            "Maximum scene duration:",
            self.max_scene_duration
        )


        # ==================================================
        # STEP 1
        # WHISPER TRANSCRIPTION
        # ==================================================

        print()
        print("=" * 70)
        print("[1/5] WHISPER TRANSCRIPTION")
        print("=" * 70)


        try:

            raw_transcription = (
                self.transcriber.transcribe(
                    audio_path=audio_path,
                    language=self.language,
                    beam_size=self.beam_size,
                    vad_filter=self.vad_filter,
                )
            )

        except WhisperTranscriptionError as error:

            raise VoicePipelineError(
                "Whisper transcription failed: "
                f"{error}"
            ) from error


        raw_segments = (
            raw_transcription.get(
                "segments",
                []
            )
        )


        print()

        print(
            "Detected language:",
            raw_transcription.get(
                "language"
            )
        )

        print(
            "Language probability:",
            raw_transcription.get(
                "language_probability"
            )
        )

        print(
            "Audio duration:",
            raw_transcription.get(
                "duration"
            )
        )

        print(
            "Raw segments:",
            len(raw_segments)
        )


        # ==================================================
        # STEP 2
        # CLEAN TRANSCRIPTION
        # ==================================================

        print()
        print("=" * 70)
        print("[2/5] CLEAN TRANSCRIPTION")
        print("=" * 70)


        try:

            clean_transcription = (
                self.cleaner.clean(
                    transcription=raw_transcription,
                    audio_duration=(
                        raw_transcription.get(
                            "duration"
                        )
                    ),
                )
            )

        except TranscriptionCleanerError as error:

            raise VoicePipelineError(
                "Transcription cleaning failed: "
                f"{error}"
            ) from error


        cleaning = (
            clean_transcription.get(
                "cleaning",
                {}
            )
        )


        clean_segments = (
            clean_transcription.get(
                "segments",
                []
            )
        )


        if not clean_segments:

            raise VoicePipelineError(
                "No transcription segments "
                "remain after cleaning."
            )


        print(
            "Raw segments:",
            cleaning.get(
                "raw_segment_count"
            )
        )

        print(
            "Clean segments:",
            cleaning.get(
                "clean_segment_count"
            )
        )

        print(
            "Removed:",
            cleaning.get(
                "removed_segment_count"
            )
        )

        print(
            "Clamped:",
            cleaning.get(
                "clamped_segment_count"
            )
        )

        print(
            "Detected gaps:",
            cleaning.get(
                "gap_count"
            )
        )


        # ==================================================
        # DISPLAY REMOVED SEGMENTS
        # ==================================================

        removed_segments = (
            cleaning.get(
                "removed_segments",
                []
            )
        )


        if removed_segments:

            print()
            print("Removed segments:")


            for segment in removed_segments:

                print(
                    "  -",
                    segment.get(
                        "removed_reason"
                    ),
                    "|",
                    segment.get(
                        "text"
                    )
                )


        # ==================================================
        # DISPLAY DETECTED TRANSCRIPTION GAPS
        # ==================================================

        gaps = cleaning.get(
            "gaps",
            []
        )


        if gaps:

            print()
            print("Detected transcription gaps:")


            for gap in gaps:

                print(
                    f"  - {gap['type']}: "
                    f"{gap['start']:.3f}"
                    f" -> "
                    f"{gap['end']:.3f}"
                    f" "
                    f"({gap['duration']:.3f}s)"
                )


        # ==================================================
        # STEP 3
        # WRITE CLEAN SRT
        # ==================================================

        print()
        print("=" * 70)
        print("[3/5] WRITE CLEAN SRT")
        print("=" * 70)


        try:

            clean_srt_path = (
                self.transcriber.write_srt(
                    transcription=clean_transcription,
                    output_path=srt_output_path,
                )
            )

        except Exception as error:

            raise VoicePipelineError(
                "Failed to write clean SRT: "
                f"{error}"
            ) from error


        print(
            "SRT:",
            clean_srt_path
        )


        if not clean_srt_path.exists():

            raise VoicePipelineError(
                "Clean SRT file was not created."
            )


        print(
            "SRT size:",
            clean_srt_path.stat().st_size,
            "bytes"
        )


        # ==================================================
        # STEP 4
        # PARSE CLEAN SRT
        # ==================================================

        print()
        print("=" * 70)
        print("[4/5] PARSE CLEAN SRT")
        print("=" * 70)


        try:

            subtitles = (
                self.srt_parser.parse(
                    str(clean_srt_path)
                )
            )

        except Exception as error:

            raise VoicePipelineError(
                "SRT parsing failed: "
                f"{error}"
            ) from error


        if not subtitles:

            raise VoicePipelineError(
                "SRT parser returned "
                "no subtitles."
            )


        print(
            "Parsed subtitles:",
            len(subtitles)
        )


        print(
            "First subtitle:",
            f"{subtitles[0].start:.3f}",
            "->",
            f"{subtitles[0].end:.3f}"
        )


        print(
            "Last subtitle:",
            f"{subtitles[-1].start:.3f}",
            "->",
            f"{subtitles[-1].end:.3f}"
        )


        # ==================================================
        # GET REAL AUDIO DURATION
        # ==================================================

        audio_duration = (
            clean_transcription.get(
                "duration"
            )
        )


        if audio_duration is None:

            raise VoicePipelineError(
                "Audio duration is missing."
            )


        audio_duration = float(
            audio_duration
        )


        if audio_duration <= 0:

            raise VoicePipelineError(
                "Invalid audio duration."
            )


        # ==================================================
        # STEP 5
        # BUILD FULL TIMELINE SCENES
        # ==================================================

        print()
        print("=" * 70)
        print("[5/5] BUILD SCENES")
        print("=" * 70)


        try:

            scenes = (
                self.scene_builder.build(
                    subtitles=subtitles,

                    # Video timeline must start at zero.
                    timeline_start=0.0,

                    # Video timeline must cover
                    # the complete audio file.
                    timeline_end=audio_duration,

                    # Turn silent / music areas
                    # into explicit gap scenes.
                    include_gaps=True,
                )
            )

        except Exception as error:

            raise VoicePipelineError(
                "Scene building failed: "
                f"{error}"
            ) from error


        if not scenes:

            raise VoicePipelineError(
                "SceneBuilder returned "
                "no scenes."
            )


        print(
            "Scenes created:",
            len(scenes)
        )


        # ==================================================
        # DISPLAY SCENES
        # ==================================================

        print()
        print("=" * 70)
        print("SCENES")
        print("=" * 70)


        speech_scene_count = 0
        gap_scene_count = 0


        for scene in scenes:

            if (
                scene.scene_type
                == "gap"
            ):

                gap_scene_count += 1

            else:

                speech_scene_count += 1


            print()

            print(
                scene.id
            )

            print(
                "  Type:",
                scene.scene_type
            )

            print(
                "  Time:",
                f"{scene.start:.3f}",
                "->",
                f"{scene.end:.3f}"
            )

            print(
                "  Duration:",
                f"{scene.duration:.3f}"
            )

            print(
                "  Subtitle IDs:",
                scene.subtitle_ids
            )

            print(
                "  Text:",
                scene.text
            )


        # ==================================================
        # TIMELINE INFORMATION
        # ==================================================

        first_scene_start = (
            scenes[0].start
        )

        last_scene_end = (
            scenes[-1].end
        )


        print()
        print("=" * 70)
        print("TIMELINE SUMMARY")
        print("=" * 70)


        print(
            "Audio duration:",
            audio_duration
        )

        print(
            "First scene starts:",
            first_scene_start
        )

        print(
            "Last scene ends:",
            last_scene_end
        )

        print(
            "Total scenes:",
            len(scenes)
        )

        print(
            "Speech scenes:",
            speech_scene_count
        )

        print(
            "Gap scenes:",
            gap_scene_count
        )


        # ==================================================
        # VALIDATE SCENE TIMELINE
        # ==================================================

        print()
        print("=" * 70)
        print("VALIDATE SCENE TIMELINE")
        print("=" * 70)


        tolerance = 0.01


        # --------------------------------------------------
        # FIRST SCENE MUST START AT ZERO
        # --------------------------------------------------

        if (
            abs(
                first_scene_start
                - 0.0
            )
            > tolerance
        ):

            raise VoicePipelineError(
                "Visual timeline does not "
                "start at 0.0 seconds."
            )


        # --------------------------------------------------
        # LAST SCENE MUST REACH AUDIO END
        # --------------------------------------------------

        if (
            abs(
                last_scene_end
                - audio_duration
            )
            > tolerance
        ):

            raise VoicePipelineError(
                "Visual timeline does not "
                "reach the end of audio."
            )


        # --------------------------------------------------
        # VALIDATE EACH SCENE
        # --------------------------------------------------

        previous_end = 0.0


        for scene in scenes:

            if scene.start < 0:

                raise VoicePipelineError(
                    f"{scene.id}: "
                    "negative start timestamp."
                )


            if (
                scene.end
                <= scene.start
            ):

                raise VoicePipelineError(
                    f"{scene.id}: "
                    "invalid scene duration."
                )


            if (
                scene.duration
                > (
                    self.max_scene_duration
                    + tolerance
                )
            ):

                raise VoicePipelineError(
                    f"{scene.id}: "
                    f"duration "
                    f"{scene.duration:.3f}s "
                    f"exceeds maximum "
                    f"{self.max_scene_duration:.3f}s."
                )


            # --------------------------------------------------
            # DETECT TIMELINE GAP
            # --------------------------------------------------

            if (
                scene.start
                - previous_end
                > tolerance
            ):

                raise VoicePipelineError(
                    f"Timeline gap before "
                    f"{scene.id}: "
                    f"{previous_end:.3f}"
                    f" -> "
                    f"{scene.start:.3f}"
                )


            # --------------------------------------------------
            # DETECT OVERLAP
            # --------------------------------------------------

            if (
                previous_end
                - scene.start
                > tolerance
            ):

                raise VoicePipelineError(
                    f"Timeline overlap before "
                    f"{scene.id}: "
                    f"{scene.start:.3f}"
                )


            previous_end = (
                scene.end
            )


        print(
            "Timeline start: PASS"
        )

        print(
            "Timeline end: PASS"
        )

        print(
            "Scene duration limit: PASS"
        )

        print(
            "No timeline gaps: PASS"
        )

        print(
            "No timeline overlaps: PASS"
        )


        # ==================================================
        # RETURN RESULT
        # ==================================================

        result = {

            "success": True,

            "audio_path": str(
                audio_path
            ),

            "audio_duration":
                audio_duration,

            "language":
                clean_transcription.get(
                    "language"
                ),

            "language_probability":
                clean_transcription.get(
                    "language_probability"
                ),

            "raw_transcription":
                raw_transcription,

            "clean_transcription":
                clean_transcription,

            "cleaning":
                cleaning,

            "srt_path": str(
                clean_srt_path
            ),

            "subtitles":
                subtitles,

            "scenes":
                scenes,

            "scene_count":
                len(scenes),

            "speech_scene_count":
                speech_scene_count,

            "gap_scene_count":
                gap_scene_count,

            "gaps":
                gaps,
        }


        # ==================================================
        # SUCCESS
        # ==================================================

        print()
        print("=" * 70)
        print("VOICE PIPELINE SUCCESS")
        print("=" * 70)


        print(
            "Audio:",
            audio_path
        )

        print(
            "Clean SRT:",
            clean_srt_path
        )

        print(
            "Clean segments:",
            len(clean_segments)
        )

        print(
            "Total scenes:",
            len(scenes)
        )

        print(
            "Speech scenes:",
            speech_scene_count
        )

        print(
            "Gap scenes:",
            gap_scene_count
        )

        print(
            "Timeline:",
            f"{first_scene_start:.3f}",
            "->",
            f"{last_scene_end:.3f}"
        )

        print(
            "Audio duration:",
            audio_duration
        )


        return result