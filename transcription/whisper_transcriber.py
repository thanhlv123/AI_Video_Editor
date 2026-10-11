from pathlib import Path

from faster_whisper import WhisperModel


class WhisperTranscriptionError(Exception):
    pass


class WhisperTranscriber:

    def __init__(
        self,
        model_size="small",
        device="cpu",
        compute_type="int8"
    ):

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

        self._model = None


    # ==================================================
    # LOAD MODEL
    # ==================================================

    def _load_model(self):

        if self._model is not None:
            return self._model

        print(
            f"Loading Whisper model: "
            f"{self.model_size}"
        )

        print(
            f"Device: {self.device}"
        )

        print(
            f"Compute type: "
            f"{self.compute_type}"
        )

        try:

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )

        except Exception as error:

            raise WhisperTranscriptionError(
                "Failed to load Whisper model: "
                f"{error}"
            ) from error

        return self._model


    # ==================================================
    # TRANSCRIBE
    # ==================================================

    def transcribe(
        self,
        audio_path,
        language=None,
        beam_size=5,
        vad_filter=False
    ):

        audio_path = Path(
            audio_path
        )

        if not audio_path.exists():

            raise FileNotFoundError(
                f"Audio file not found: "
                f"{audio_path}"
            )


        model = self._load_model()


        print()
        print(
            "Transcribing:",
            audio_path
        )


        try:

            segments_generator, info = (
                model.transcribe(
                    str(audio_path),
                    language=language,
                    beam_size=beam_size,
                    vad_filter=vad_filter
                )
            )

        except Exception as error:

            raise WhisperTranscriptionError(
                "Whisper transcription "
                f"failed: {error}"
            ) from error


        # IMPORTANT:
        # faster-whisper returns a generator.
        # The real transcription work happens
        # while iterating through it.

        segments = []


        try:

            for index, segment in enumerate(
                segments_generator,
                start=1
            ):

                text = (
                    segment.text
                    or ""
                ).strip()


                if not text:
                    continue


                item = {

                    "index": index,

                    "start": float(
                        segment.start
                    ),

                    "end": float(
                        segment.end
                    ),

                    "text": text
                }


                segments.append(
                    item
                )


                print(
                    f"[{index}] "
                    f"{item['start']:.2f}"
                    f" -> "
                    f"{item['end']:.2f}"
                    f" | "
                    f"{text}"
                )

        except Exception as error:

            raise WhisperTranscriptionError(
                "Whisper failed while "
                "processing audio: "
                f"{error}"
            ) from error


        if not segments:

            raise WhisperTranscriptionError(
                "Whisper returned no "
                "transcription segments."
            )


        detected_language = getattr(
            info,
            "language",
            None
        )


        language_probability = getattr(
            info,
            "language_probability",
            None
        )


        duration = getattr(
            info,
            "duration",
            None
        )


        result = {

            "audio_path": str(
                audio_path
            ),

            "language": (
                detected_language
            ),

            "language_probability": (
                language_probability
            ),

            "duration": (
                float(duration)
                if duration is not None
                else None
            ),

            "segments": segments
        }


        return result


    # ==================================================
    # WRITE SRT
    # ==================================================

    def write_srt(
        self,
        transcription,
        output_path
    ):

        if not isinstance(
            transcription,
            dict
        ):

            raise ValueError(
                "Transcription must be "
                "a dictionary."
            )


        segments = transcription.get(
            "segments",
            []
        )


        if not segments:

            raise ValueError(
                "Transcription contains "
                "no segments."
            )


        output_path = Path(
            output_path
        )


        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as file:

            for index, segment in enumerate(
                segments,
                start=1
            ):

                start = (
                    self._format_timestamp(
                        segment["start"]
                    )
                )

                end = (
                    self._format_timestamp(
                        segment["end"]
                    )
                )

                text = (
                    segment["text"]
                    .strip()
                )


                file.write(
                    f"{index}\n"
                )

                file.write(
                    f"{start} --> {end}\n"
                )

                file.write(
                    f"{text}\n\n"
                )


        return output_path


    # ==================================================
    # TRANSCRIBE DIRECTLY TO SRT
    # ==================================================

    def transcribe_to_srt(
        self,
        audio_path,
        output_path,
        language=None,
        beam_size=5,
        vad_filter=False
    ):

        transcription = (
            self.transcribe(
                audio_path=audio_path,
                language=language,
                beam_size=beam_size,
                vad_filter=vad_filter
            )
        )


        srt_path = self.write_srt(
            transcription=transcription,
            output_path=output_path
        )


        return {
            "transcription": transcription,
            "srt_path": str(
                srt_path
            )
        }


    # ==================================================
    # FORMAT SRT TIMESTAMP
    # ==================================================

    def _format_timestamp(
        self,
        seconds
    ):

        seconds = max(
            0.0,
            float(seconds)
        )


        total_milliseconds = round(
            seconds * 1000
        )


        hours = (
            total_milliseconds
            // 3_600_000
        )


        remaining = (
            total_milliseconds
            % 3_600_000
        )


        minutes = (
            remaining
            // 60_000
        )


        remaining = (
            remaining
            % 60_000
        )


        secs = (
            remaining
            // 1000
        )


        milliseconds = (
            remaining
            % 1000
        )


        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{secs:02d},"
            f"{milliseconds:03d}"
        )