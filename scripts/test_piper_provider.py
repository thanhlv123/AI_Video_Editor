from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creator_studio.tts import TTSProviderRegistry, TTSService
from creator_studio.tts.providers import PiperProcessProvider


def main() -> int:
    runtime_root = ROOT / "runtime" / "piper"
    if sys.platform == "win32":
        piper_python = runtime_root / ".venv" / "Scripts" / "python.exe"
    else:
        piper_python = runtime_root / ".venv" / "bin" / "python"

    voices_root = runtime_root / "voices"
    output_path = runtime_root / "test" / "provider_test.wav"

    provider = PiperProcessProvider(
        python_executable=piper_python,
        voices_root=voices_root,
        project_root=ROOT,
    )

    registry = TTSProviderRegistry()
    registry.register(provider)
    service = TTSService(registry)

    ok, detail = service.health_check("piper_local")
    print("Health:", ok, detail)
    if not ok:
        return 2

    voices = service.list_voices("piper_local")
    print("Voices:")
    for voice in voices:
        print(
            f"  - {voice.voice_id} | "
            f"{voice.language or '-'} | "
            f"{voice.quality or '-'}"
        )

    if not voices:
        print("No Piper voices installed.")
        return 3

    result = service.synthesize(
        provider_id="piper_local",
        voice_id=voices[0].voice_id,
        text=(
            "Hello. This audio was generated through the new "
            "provider-neutral text to speech service."
        ),
        output_path=output_path,
        speed=1.0,
        volume=1.0,
    )

    print("Output:", result.output_path)
    print("Duration:", round(result.duration_seconds, 3))
    print("Bytes:", result.byte_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
