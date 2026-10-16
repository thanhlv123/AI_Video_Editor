M118 - REAL OFFLINE RENDER ACCEPTANCE
=====================================

Purpose
-------
M117 verified the real production Qt window could be constructed. M118
adds a real, provider-independent FFmpeg export acceptance gate.

Run:
    python scripts/m118_render_acceptance.py
    python scripts/m118_render_acceptance.py --report .automation/m118_acceptance.json

The harness creates disposable synthetic color videos, a narration WAV,
and a music WAV under a Unicode-named temporary project directory.
It supplies a ready M113 timeline manifest to the real M114
RenderExportService, renders an MP4, verifies audio/video streams,
resolution and duration using ffprobe, and exports a second time to
verify that existing output files are never overwritten.

All media is generated locally. No external API, user credentials,
existing projects, or internet connection is required. Temporary
fixtures are removed automatically. The harness uses 320x180 at 12 fps
for speed; this is an acceptance smoke test, not a production-quality
render benchmark.

The Windows release gate runs this real acceptance before the full
unittest regression suite. Provider-specific TTS, search, GPU, and
network flows still need separate real-world validation.
