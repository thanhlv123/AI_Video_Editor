from __future__ import annotations

import argparse
import sys
import unicodedata
import wave
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Isolated Piper synthesis worker for AI Video Editor."
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--config")
    parser.add_argument("--output", required=True)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--volume", type=float, default=1.0)
    parser.add_argument("--speaker-id", type=int)
    return parser


def _sanitize_text(value: str) -> str:
    cleaned = "".join(
        " " if 0xD800 <= ord(char) <= 0xDFFF else char
        for char in value
    )
    return unicodedata.normalize("NFC", cleaned)


def main() -> int:
    args = build_parser().parse_args()

    if args.speed <= 0:
        raise ValueError("speed must be > 0")
    if args.volume <= 0:
        raise ValueError("volume must be > 0")

    # Piper is imported only inside the isolated worker process.
    from piper import PiperVoice, SynthesisConfig

    model_path = Path(args.model).resolve()
    output_path = Path(args.output).resolve()

    if not model_path.is_file():
        raise FileNotFoundError(f"Piper model not found: {model_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    config_path = Path(args.config).resolve() if args.config else None
    load_kwargs = {}
    if config_path is not None and config_path.is_file():
        load_kwargs["config_path"] = str(config_path)

    voice = PiperVoice.load(str(model_path), **load_kwargs)

    # Piper's length_scale is inverse to the user-facing "speed".
    syn_config = SynthesisConfig(
        volume=float(args.volume),
        length_scale=1.0 / float(args.speed),
    )

    text = _sanitize_text(sys.stdin.read())
    if not text.strip():
        raise ValueError("text must not be empty")

    # Avoid masking a Piper/Unicode exception with Wave_write.close() complaining
    # that channel parameters were never initialized. On synthesis failure we
    # detach the wave wrapper and remove the partial file, preserving the real
    # exception for the parent process.
    raw_file = output_path.open("wb")
    wav_file = wave.open(raw_file, "wb")
    try:
        kwargs = {"syn_config": syn_config}
        if args.speaker_id is not None:
            kwargs["speaker_id"] = args.speaker_id
        voice.synthesize_wav(text, wav_file, **kwargs)
        wav_file.close()
    except Exception:
        try:
            wav_file._file = None  # Prevent wave.__del__ from masking root cause.
        except Exception:
            pass
        try:
            raw_file.close()
        except Exception:
            pass
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    if not output_path.is_file() or output_path.stat().st_size <= 44:
        raise RuntimeError("Piper did not create a valid WAV file")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
