M134 - PYAV / FASTER-WHISPER COMPATIBILITY
===========================================

Issue found during real Windows end-to-end testing
--------------------------------------------------
M133 correctly installed faster-whisper, but content analysis then failed while
decoding the generated WAV:

    TypeError: open() got an unexpected keyword argument 'metadata_errors'

Root cause
----------
The current faster-whisper release used by this project still calls
av.open(..., metadata_errors="ignore"). PyAV 19 removed that keyword.
A broad transitive dependency range allowed pip to install an incompatible
PyAV major version even though faster-whisper itself imported successfully.

Fix
---
- Pin PyAV to av>=11,<19 in both Windows runtime and CI requirements.
- Extend Runtime Doctor with a required PyAV/faster-whisper compatibility check.
- Add regression tests for PyAV 19 rejection and PyAV 18 acceptance.
- Keep setup non-destructive: running setup_creator_studio.cmd updates the
  existing .venv and preserves project data.

Local recovery
--------------
After pulling M134:
1. Close Creator Studio.
2. Run setup_creator_studio.cmd again.
3. Run start_creator_studio.cmd --doctor and confirm both:
       faster_whisper: ok
       pyav_faster_whisper_compat: ok
4. Reopen the existing M132_TEST_LOCAL project and run TẠO VIDEO again.

No project recreation, script re-entry, or VoiceStudio reconfiguration is
required.
