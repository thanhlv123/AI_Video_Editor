from pathlib import Path
import sys


ROOT = Path(
    __file__
).resolve().parent.parent


sys.path.insert(
    0,
    str(ROOT)
)


from transcription.whisper_transcriber import (
    WhisperTranscriber,
    WhisperTranscriptionError
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("WHISPER TRANSCRIPTION TEST")
print("=" * 70)


# ==================================================
# PATHS
# ==================================================

audio_path = (
    ROOT
    / "media"
    / "test_voice.mp3"
)


output_path = (
    ROOT
    / "subtitles"
    / "test_voice_full.srt"
)


# ==================================================
# CHECK AUDIO
# ==================================================

if not audio_path.exists():

    raise FileNotFoundError(
        f"Audio file not found: "
        f"{audio_path}"
    )


print()
print(
    "Audio:",
    audio_path
)

print(
    "Output:",
    output_path
)


# ==================================================
# CREATE TRANSCRIBER
# ==================================================

transcriber = WhisperTranscriber(

    model_size="small",

    device="cpu",

    compute_type="int8"
)


# ==================================================
# TRANSCRIBE
# ==================================================

print()
print("=" * 70)
print("STARTING TRANSCRIPTION")
print("=" * 70)

print()
print(
    "NOTE:"
)

print(
    "The first run may download "
    "the Whisper model."
)

print(
    "Please wait until transcription "
    "is completely finished."
)


try:

    result = (
        transcriber.transcribe_to_srt(

            audio_path=audio_path,

            output_path=output_path,

            language=None,

            beam_size=5,

            vad_filter=False
        )
    )

except WhisperTranscriptionError as error:

    print()
    print("=" * 70)
    print("TRANSCRIPTION FAILED")
    print("=" * 70)

    print(
        error
    )

    raise SystemExit(1)


# ==================================================
# GET RESULT
# ==================================================

transcription = result[
    "transcription"
]


segments = transcription[
    "segments"
]


# ==================================================
# DISPLAY INFORMATION
# ==================================================

print()
print("=" * 70)
print("TRANSCRIPTION RESULT")
print("=" * 70)


print(
    "Detected language:",
    transcription.get(
        "language"
    )
)

print(
    "Language probability:",
    transcription.get(
        "language_probability"
    )
)

print(
    "Audio duration:",
    transcription.get(
        "duration"
    )
)

print(
    "Segments:",
    len(
        segments
    )
)

print(
    "SRT:",
    result[
        "srt_path"
    ]
)


# ==================================================
# FIRST SEGMENT
# ==================================================

first_segment = segments[0]


print()
print(
    "First segment:"
)

print(
    "  Start:",
    first_segment[
        "start"
    ]
)

print(
    "  End:",
    first_segment[
        "end"
    ]
)

print(
    "  Text:",
    first_segment[
        "text"
    ]
)


# ==================================================
# LAST SEGMENT
# ==================================================

last_segment = segments[-1]


print()
print(
    "Last segment:"
)

print(
    "  Start:",
    last_segment[
        "start"
    ]
)

print(
    "  End:",
    last_segment[
        "end"
    ]
)

print(
    "  Text:",
    last_segment[
        "text"
    ]
)


# ==================================================
# VALIDATE SRT FILE
# ==================================================

print()
print("=" * 70)
print("VALIDATING SRT")
print("=" * 70)


if not output_path.exists():

    raise RuntimeError(
        "SRT file was not created."
    )


file_size = (
    output_path
    .stat()
    .st_size
)


if file_size <= 0:

    raise RuntimeError(
        "SRT file is empty."
    )


if len(segments) <= 0:

    raise RuntimeError(
        "No transcription segments."
    )


if (
    last_segment["end"]
    <= 0
):

    raise RuntimeError(
        "Invalid final timestamp."
    )


print(
    "SRT exists: True"
)

print(
    "SRT size:",
    file_size,
    "bytes"
)

print(
    "Final speech timestamp:",
    last_segment[
        "end"
    ]
)


# ==================================================
# COVERAGE INFORMATION
# ==================================================

audio_duration = transcription.get(
    "duration"
)


if audio_duration:

    speech_end = float(
        last_segment[
            "end"
        ]
    )

    audio_duration = float(
        audio_duration
    )

    trailing_silence = (
        audio_duration
        - speech_end
    )

    coverage = (
        speech_end
        / audio_duration
        * 100
    )


    print(
        "Audio duration:",
        audio_duration
    )

    print(
        "Trailing silence:",
        trailing_silence
    )

    print(
        "Speech coverage:",
        f"{coverage:.2f}%"
    )


# ==================================================
# PREVIEW FIRST 5 SEGMENTS
# ==================================================

print()
print("=" * 70)
print("FIRST 5 SEGMENTS")
print("=" * 70)


for segment in segments[:5]:

    print(
        f"[{segment['index']}] "
        f"{segment['start']:.2f}"
        " -> "
        f"{segment['end']:.2f}"
        " | "
        f"{segment['text']}"
    )


# ==================================================
# PREVIEW LAST 5 SEGMENTS
# ==================================================

print()
print("=" * 70)
print("LAST 5 SEGMENTS")
print("=" * 70)


for segment in segments[-5:]:

    print(
        f"[{segment['index']}] "
        f"{segment['start']:.2f}"
        " -> "
        f"{segment['end']:.2f}"
        " | "
        f"{segment['text']}"
    )


# ==================================================
# SUCCESS
# ==================================================

print()
print("=" * 70)
print("WHISPER TRANSCRIPTION SUCCESS")
print("=" * 70)

print(
    "Input:",
    audio_path
)

print(
    "Output:",
    output_path
)

print(
    "Segments:",
    len(
        segments
    )
)

print(
    "Language:",
    transcription.get(
        "language"
    )
)

print(
    "Final timestamp:",
    last_segment[
        "end"
    ]
)

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)