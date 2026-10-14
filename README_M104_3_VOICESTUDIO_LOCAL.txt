M104.3 - VOICESTUDIO LOCAL PROVIDER

Goal
----
Add VoiceStudio as a second local TTS provider without embedding or copying
VoiceStudio source code into AI Video Editor.

Runtime boundary
----------------
AI Video Editor -> TTSService -> VoiceStudioLocalProvider
                -> http://127.0.0.1:3900 -> VoiceStudio Electron/backend

The provider is intentionally loopback-only. A future VPS/remote integration
must use a separate remote provider with explicit authentication/TLS policy.

What this milestone adds
------------------------
1. VoiceStudio Local appears beside Piper Local in the TTS provider selector.
2. Health check through GET /health.
3. Voice/profile discovery through GET /v1/audio/voices.
4. TTS through POST /v1/audio/speech with WAV output.
5. Long scripts are chunked under VoiceStudio's 4096-character API limit and
   merged back into one WAV.
6. Provider-level voice-clone method using POST /profiles is included for the
   next GUI milestone. The GUI does not expose cloning yet.
7. OpenAI alias voices are hidden because VoiceStudio documents them as aliases
   for the active engine's default, not independent VoiceStudio voices.

Important
---------
VoiceStudio itself is not bundled in this milestone. Install the official
Electron desktop app and let it supervise its own backend. Do not launch a
second VoiceStudio backend process.

Local loopback normally requires no API key. If a local VoiceStudio instance is
configured with OMNIVOICE_API_KEY, set VOICESTUDIO_API_KEY or OMNIVOICE_API_KEY
in the environment before launching AI Video Editor.

Files to replace/add
--------------------
gui_creator_studio_m104_3.py
creator_studio/tts/providers/__init__.py
creator_studio/tts/providers/voicestudio_provider.py
tests/test_voicestudio_local_provider.py
scripts/test_voicestudio_local.py

The existing Piper provider and worker are included in the ZIP as checkpoints.
