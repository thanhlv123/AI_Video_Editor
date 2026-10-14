M104.4.3 - KittenTTS voice mapping + faster preview

Fixes
-----
1. VoiceStudio 0.5.6 KittenTTS accepts raw speaker ids only:
   Bella  -> expr-voice-2-f
   Jasper -> expr-voice-2-m
   Luna   -> expr-voice-3-f
   Bruno  -> expr-voice-3-m
   Rosie  -> expr-voice-4-f
   Hugo   -> expr-voice-4-m
   Kiki   -> expr-voice-5-f
   Leo    -> expr-voice-5-m

   Earlier M104.4.2 sent friendly names. VoiceStudio accepted the request but
   KittenTTSBackend silently fell back to its default voice. M104.4.3 sends the
   engine-native ids and rejects unknown preset names.

2. KittenTTS preview text is reduced from 600 to 220 characters. Full-project
   generation is unchanged. This makes comparing the 8 voices much faster.

3. When KittenTTS is first selected at speed 1.00, Creator Studio changes the
   UI to 1.15 as a narration-oriented starting point. The user can still set
   any speed afterwards.

4. Voice labels now include friendly name + gender while storing the native
   VoiceStudio speaker id.

Important runtime note
----------------------
VoiceStudio 0.5.6 declares KittenTTS as CPU-only. The RTX GPU is not used by
VoiceStudio's KittenTTS adapter. Upstream KittenTTS can use CUDA, so a future
KittenTTS Direct provider can be added if generation throughput needs to be
faster than the VoiceStudio integration.
