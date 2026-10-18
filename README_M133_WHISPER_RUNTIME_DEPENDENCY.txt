M133 - WHISPER RUNTIME DEPENDENCY HARDENING
=============================================

Issue found during Windows-local acceptance:
The automatic workflow successfully completed script ingestion and VoiceStudio
TTS, then failed at content analysis with:

    ModuleNotFoundError: No module named 'faster_whisper'

Root cause:
The production voice pipeline imports faster_whisper directly, but the Windows
runtime requirements and bootstrap readiness probe did not require it.

Fix:
- Add faster-whisper to requirements-runtime.txt.
- Add the same dependency to CI so the release gate exercises the real import.
- Make M131 bootstrap readiness probe import faster_whisper.
- Make Runtime Doctor treat faster_whisper as required for end-to-end local
  video creation.
- Add regression coverage.

User recovery after pulling this milestone:
1. Close Creator Studio.
2. Run setup_creator_studio.cmd again. It updates the existing repository-local
   .venv without deleting project data.
3. Run start_creator_studio.cmd --doctor and confirm status=ready.
4. Reopen Creator Studio and continue testing the existing M132_TEST_LOCAL
   project. The Voice Asset already created by the failed run may be reused.

No VPS or multi-user changes are included.
