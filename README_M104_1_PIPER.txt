M104.1 - PIPER TTS FOUNDATION

Purpose
-------
This milestone adds a provider-neutral TTS foundation and the first provider:
Piper Local.

Architecture
------------
Creator Studio / GUI
        |
        v
    TTSService
        |
        v
TTSProviderRegistry
        |
        +--> PiperProcessProvider
        |
        +--> future OpenVoiceProvider
        |
        +--> future KieTTSProvider
        |
        +--> future ElevenLabsProvider

Piper is intentionally executed in a separate Python runtime/process. The main
Creator Studio process does not import Piper. This makes future migration to a
VPS worker/container or replacement with OpenVoice much easier.

No existing production file is replaced in M104.1.

New files
---------
creator_studio/tts/__init__.py
creator_studio/tts/models.py
creator_studio/tts/provider.py
creator_studio/tts/registry.py
creator_studio/tts/service.py
creator_studio/tts/providers/__init__.py
creator_studio/tts/providers/piper_provider.py
creator_studio/tts/providers/piper_worker.py
tests/test_tts_provider_foundation.py
scripts/setup_piper_local.ps1
scripts/test_piper_provider.py

Local runtime
-------------
runtime/piper/.venv
runtime/piper/voices
runtime/piper/test

The runtime folder should remain local and should not be committed to Git.

Next milestone
--------------
M104.2 will connect this TTSService to the Vietnamese Voice + Script GUI:
- Imported voice / Generated voice mode
- Provider selector
- Piper voice selector
- Speed
- Preview
- Generate voice from current ProjectManifest script
- Save generated audio as the project's voice input
- Then optionally run the existing VoicePipeline
