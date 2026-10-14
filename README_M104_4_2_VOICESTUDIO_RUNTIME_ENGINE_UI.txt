M104.4.2 - VoiceStudio Runtime Discovery + Engine/Voice UI
===========================================================

WHY THIS MILESTONE EXISTS
-------------------------
M104.4.1 assumed VoiceStudio would always bind to 127.0.0.1:3900 and treated
~30 seconds as enough startup time. VoiceStudio Electron 0.5.6 may select a
fallback loopback port when Windows reserves the default port, and its managed
backend can legitimately need several minutes during first-run preparation.

M104.4.2 therefore:
- discovers VoiceStudio through its loopback discovery marker;
- scans 3900, 4900, 5900, ... through 19900;
- auto-starts VoiceStudio only when a backend is not already running;
- waits up to ~10 minutes while showing elapsed startup time;
- uses the discovered backend URL for every provider request;
- exposes a real Engine / Model selector;
- exposes KittenTTS's eight real preset voices when KittenTTS is selected;
- keeps OpenAI compatibility voice aliases hidden because they all map to the
  active engine's same default voice in VoiceStudio 0.5.6;
- shows clone controls only for engines that support cloning;
- replaces hard-to-see native speed arrows with explicit dark ▲ / ▼ buttons;
- widens voice/model selectors and adds tooltips;
- keeps provider/network error messages short in the main UI.

EXPECTED VOICESTUDIO ENGINES ON THE TEST MACHINE
------------------------------------------------
Based on the user's previous live API result, available TTS engines include:
- omnivoice
- kittentts
- omnivoice-subprocess

KittenTTS preset voices:
Bella, Jasper, Luna, Bruno, Rosie, Hugo, Kiki, Leo

TEST FLOW
---------
1. Close VoiceStudio completely.
2. Start gui_creator_studio_m104_4_2.py.
3. Choose Tạo từ kịch bản (TTS) -> VoiceStudio Local.
4. AI Video Editor should start VoiceStudio and keep waiting while its backend
   prepares. It should automatically discover a fallback port if 3900 is not
   used.
5. When ready, Engine / Model appears.
6. Choose kittentts -> eight preset voices should appear; clone controls hide.
7. Choose omnivoice -> default/saved profiles appear; clone controls show.
8. Preview a short script and then generate the full voice.

DIAGNOSTICS
-----------
python scripts/test_voicestudio_local.py

or:

powershell -ExecutionPolicy Bypass -File scripts/find_voicestudio_local.ps1

Do not commit user/runtime/model data yet. Test the milestone first.
