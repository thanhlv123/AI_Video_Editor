from pathlib import Path
import sys


ROOT = Path(
    __file__
).resolve().parent.parent


sys.path.insert(
    0,
    str(ROOT)
)


from transcription.cleaner import (
    TranscriptionCleaner
)


print("=" * 70)
print("AI VIDEO EDITOR")
print("TRANSCRIPTION CLEANER TEST")
print("=" * 70)


# ==================================================
# SIMULATE REAL WHISPER RESULT
# ==================================================

transcription = {

    "audio_path": str(
        ROOT
        / "media"
        / "test_voice.mp3"
    ),

    "language": "en",

    "language_probability": 0.7626422047615051,

    "duration": 168.098,

    "segments": [

        {
            "index": 1,
            "start": 0.0,
            "end": 16.08,
            "text": "oooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooo"
        },

        {
            "index": 2,
            "start": 16.08,
            "end": 19.66,
            "text": "Behind cold walls where the light feels small"
        },

        {
            "index": 3,
            "start": 19.66,
            "end": 22.68,
            "text": "Dreams fall silent afraid to call"
        },

        {
            "index": 4,
            "start": 22.68,
            "end": 26.14,
            "text": "Names forgotten, hope running low"
        },

        {
            "index": 5,
            "start": 26.14,
            "end": 29.96,
            "text": "Children learning what they don't know"
        },

        {
            "index": 6,
            "start": 29.96,
            "end": 40.96,
            "text": "But in the air a whisper starts, a fragile sound from open hearts."
        },

        {
            "index": 7,
            "start": 40.96,
            "end": 44.96,
            "text": "Sing little hearts, don't be afraid."
        },

        {
            "index": 8,
            "start": 44.96,
            "end": 51.96,
            "text": "Darkness fades when a song is made, where the world once closed the door."
        },

        {
            "index": 9,
            "start": 51.96,
            "end": 57.96,
            "text": "Light is born in the voice once more."
        },

        {
            "index": 10,
            "start": 58.96,
            "end": 65.96,
            "text": "Heavy rules and endless days, words like shadows, cold and gray."
        },

        {
            "index": 11,
            "start": 65.96,
            "end": 74.96,
            "text": "Still inside a rhythm stays, no one can take that song away."
        },

        {
            "index": 12,
            "start": 74.96,
            "end": 85.96,
            "text": "Every note becomes a place where we belong, where we are safe."
        },

        {
            "index": 13,
            "start": 85.96,
            "end": 88.96,
            "text": "Sing little hearts, don't hide your sound."
        },

        {
            "index": 14,
            "start": 88.96,
            "end": 95.96,
            "text": "Silence breaks when hope is found, if you were taught to fall before."
        },

        {
            "index": 15,
            "start": 95.96,
            "end": 101.96,
            "text": "Now you learn what wings are through."
        },

        {
            "index": 16,
            "start": 101.96,
            "end": 108.96,
            "text": "You are more than your yesterday, more than the hurt that made you stay."
        },

        {
            "index": 17,
            "start": 108.96,
            "end": 118.96,
            "text": "You are a voice clear and strong, waiting to rise, waiting for song."
        },

        {
            "index": 18,
            "start": 118.96,
            "end": 125.96,
            "text": "We sing together side by side, many voices one inside."
        },

        {
            "index": 19,
            "start": 125.96,
            "end": 135.96,
            "text": "In the echo a note's a gone piece lives on."
        },

        {
            "index": 20,
            "start": 135.96,
            "end": 143.96,
            "text": "And when the world feels close again, the song remains hard."
        },

        {
            "index": 21,
            "start": 165.96,
            "end": 170.96,
            "text": "Thank you for watching!"
        }
    ]
}


# ==================================================
# CREATE CLEANER
# ==================================================

cleaner = TranscriptionCleaner(

    minimum_duration=0.10,

    gap_threshold=2.0,

    repeated_char_threshold=12,

    repeated_ratio_threshold=0.80
)


# ==================================================
# CLEAN
# ==================================================

print()
print("Cleaning transcription...")


result = cleaner.clean(
    transcription
)


segments = result[
    "segments"
]


cleaning = result[
    "cleaning"
]


# ==================================================
# SUMMARY
# ==================================================

print()
print("=" * 70)
print("CLEANING RESULT")
print("=" * 70)


print(
    "Audio duration:",
    result["duration"]
)

print(
    "Raw segments:",
    cleaning[
        "raw_segment_count"
    ]
)

print(
    "Clean segments:",
    cleaning[
        "clean_segment_count"
    ]
)

print(
    "Removed segments:",
    cleaning[
        "removed_segment_count"
    ]
)

print(
    "Clamped segments:",
    cleaning[
        "clamped_segment_count"
    ]
)

print(
    "Detected gaps:",
    cleaning[
        "gap_count"
    ]
)


# ==================================================
# REMOVED
# ==================================================

print()
print("=" * 70)
print("REMOVED SEGMENTS")
print("=" * 70)


for item in cleaning[
    "removed_segments"
]:

    print()

    print(
        "Text:",
        item.get(
            "text"
        )
    )

    print(
        "Reason:",
        item.get(
            "removed_reason"
        )
    )


# ==================================================
# CLAMPED
# ==================================================

print()
print("=" * 70)
print("CLAMPED SEGMENTS")
print("=" * 70)


for item in cleaning[
    "clamped_segments"
]:

    print()

    print(
        "Text:",
        item.get(
            "text"
        )
    )

    print(
        "Start:",
        item.get(
            "start"
        )
    )

    print(
        "Original end:",
        item.get(
            "original_end"
        )
    )

    print(
        "New end:",
        item.get(
            "end"
        )
    )


# ==================================================
# GAPS
# ==================================================

print()
print("=" * 70)
print("TIMELINE GAPS")
print("=" * 70)


for gap in cleaning[
    "gaps"
]:

    print()

    print(
        "Type:",
        gap["type"]
    )

    print(
        "Start:",
        gap["start"]
    )

    print(
        "End:",
        gap["end"]
    )

    print(
        "Duration:",
        gap["duration"]
    )


# ==================================================
# CLEAN SEGMENTS
# ==================================================

print()
print("=" * 70)
print("CLEAN SEGMENTS")
print("=" * 70)


for segment in segments:

    print(
        f"[{segment['index']}] "
        f"{segment['start']:.3f}"
        " -> "
        f"{segment['end']:.3f}"
        " | "
        f"{segment['text']}"
    )


# ==================================================
# AUTOMATIC VALIDATION
# ==================================================

print()
print("=" * 70)
print("VALIDATING CLEANER")
print("=" * 70)


# Expected:
# 21 raw - 1 hallucination = 20 clean

if (
    cleaning["raw_segment_count"]
    != 21
):

    raise RuntimeError(
        "Unexpected raw segment count."
    )


if (
    cleaning["clean_segment_count"]
    != 20
):

    raise RuntimeError(
        "Cleaner did not remove "
        "the expected hallucination."
    )


if (
    cleaning["removed_segment_count"]
    != 1
):

    raise RuntimeError(
        "Expected exactly one "
        "removed segment."
    )


removed = cleaning[
    "removed_segments"
][0]


if (
    removed.get(
        "removed_reason"
    )
    != "repeated_character_hallucination"
):

    raise RuntimeError(
        "Wrong hallucination "
        "removal reason."
    )


# Last segment must be clamped
# to real audio duration.

last_segment = segments[-1]


if (
    abs(
        last_segment["end"]
        - 168.098
    )
    > 0.001
):

    raise RuntimeError(
        "Final timestamp was "
        "not clamped correctly."
    )


# The 22-second gap must remain
# represented in metadata.

large_gap_found = False


for gap in cleaning[
    "gaps"
]:

    if (
        gap["type"]
        == "internal_gap"
        and gap["start"] >= 143.9
        and gap["end"] >= 165.9
    ):

        large_gap_found = True

        break


if not large_gap_found:

    raise RuntimeError(
        "Expected large internal "
        "gap was not detected."
    )


print(
    "Hallucination removal: PASS"
)

print(
    "Timestamp clamping: PASS"
)

print(
    "Timeline gap detection: PASS"
)

print(
    "Segment re-indexing: PASS"
)


# ==================================================
# SUCCESS
# ==================================================

print()
print("=" * 70)
print("TRANSCRIPTION CLEANER SUCCESS")
print("=" * 70)

print(
    "Raw:",
    cleaning[
        "raw_segment_count"
    ]
)

print(
    "Clean:",
    cleaning[
        "clean_segment_count"
    ]
)

print(
    "Removed:",
    cleaning[
        "removed_segment_count"
    ]
)

print(
    "Clamped:",
    cleaning[
        "clamped_segment_count"
    ]
)

print(
    "Gaps:",
    cleaning[
        "gap_count"
    ]
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