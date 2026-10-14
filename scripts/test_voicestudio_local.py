from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creator_studio.tts.providers import VoiceStudioLocalProvider
from creator_studio.tts.voicestudio_runtime import VoiceStudioLocalRuntimeManager


def main() -> int:
    runtime = VoiceStudioLocalRuntimeManager()
    print("VoiceStudio executable:", runtime.discover_executable() or "NOT FOUND")
    print("Scanning loopback endpoints...")
    endpoint = runtime.discover_backend_url(timeout_seconds=0.20)
    if not endpoint:
        print("Backend: NOT FOUND")
        print("Candidates:")
        for url in runtime.candidate_backend_urls():
            print("  -", url)
        print("\nOpen VoiceStudio and wait until its setup/backend is ready, then run this script again.")
        return 2

    print("Backend:", endpoint)
    provider = VoiceStudioLocalProvider(base_url=endpoint)
    ok, detail = provider.health_check()
    print("Health:", ok, detail)
    if not ok:
        return 3

    print("\nEngines:")
    try:
        engines = provider.list_engines()
    except Exception as exc:
        print("Engine listing failed:", type(exc).__name__, exc)
        return 4

    for engine in engines:
        clone = "clone=yes" if engine.supports_voice_cloning else "clone=no"
        alias = "alias" if engine.is_alias else "engine"
        print(f"  - {engine.engine_id} | {engine.display_name} | {clone} | {alias}")

    print("\nVoices by engine:")
    for engine in engines:
        try:
            voices = provider.list_voices_for_engine(engine.engine_id)
        except Exception as exc:
            print(f"  [{engine.engine_id}] ERROR: {type(exc).__name__}: {exc}")
            continue
        print(f"  [{engine.engine_id}] {len(voices)} voice(s)")
        for voice in voices:
            print(f"      - {voice.voice_id} | {voice.display_name} | {voice.language or '-'}")

    print("\nVoiceStudio Local integration is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
