M120 - READ-ONLY RENDER PREFLIGHT
================================

Before an expensive FFmpeg export, inspect an M113 timeline and every
required media reference without modifying any project files.

Windows command:
    cd /d D:\YouTubeTools\AI_Video_Editor
    python -m creator_studio.timeline_preflight "C:\path\to\timeline_manifest.json" --project-root "C:\path\to\project"

The command prints a JSON report and exits 0 if ready or 1 if blocked.
It detects missing/empty media, malformed manifests, invalid timing,
incorrect music inclusion, and the existing M114 render contract errors.
Media outside the project is reported as a portability warning.

The check uses the existing M114 project-preparation validator; it does
not start FFmpeg, decode media, access provider APIs, or reserve exports.
A ready report is NOT a guarantee that actual video/audio decoding will
succeed. It only establishes structural and referenced-file readiness.

Known issue: M113 can emit null source_duration_seconds when voice metadata
is unknown, but the current M114 validator rejects null numeric metadata.
The preflight reports this as render_contract instead of silently changing
source duration. Repair this contract in a separate, regression-tested
milestone before treating that case as render-ready.

Tests: tests/test_timeline_preflight_m120.py
CI: M116 Windows release gate full unittest suite.
