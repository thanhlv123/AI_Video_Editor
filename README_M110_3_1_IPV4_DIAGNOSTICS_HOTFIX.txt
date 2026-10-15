AI Video Editor / Creator Studio
M110.3.1 - YouTube IPv4 + Diagnostics Hotfix

Purpose
-------
1. Keep YouTube Data API networking local to Creator Studio and prefer IPv4 by default.
   This avoids urllib timeouts on Windows/network configurations where Google AAAA
   records resolve but the IPv6 route is not usable.
2. Do NOT disable IPv6 globally on Windows.
3. Persist safe per-scene YouTube error diagnostics (HTTP status/reason/message) without
   ever persisting the API key or request URL.
4. Do not show the media-search step as green/completed when YouTube fallback failed
   or when YOUTUBE_API_KEY is missing for weak/unresolved stock scenes.

Compatibility
-------------
- Keeps creator_studio_youtube_reference_m110_3 manifest format.
- Keeps creator_studio_automation_run_m110_2 run format for backward compatibility.
- YOUTUBE_FORCE_IPV4=0 can restore platform-default address selection if needed later.

Changed files
-------------
creator_studio/youtube_reference.py
creator_studio/automation_runner.py

New checkpoint GUI
------------------
gui_creator_studio_m110_3_1.py

New regression tests
--------------------
tests/test_youtube_reference_m110_3_1.py
tests/test_automation_runner_m110_3_1.py

Build verification
------------------
py_compile: PASS
Focused M110.3 + M110.3.1 tests: 19 PASS
