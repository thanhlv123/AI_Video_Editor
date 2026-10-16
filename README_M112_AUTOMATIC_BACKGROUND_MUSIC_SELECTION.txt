M112 - AUTOMATIC BACKGROUND MUSIC SELECTION
===========================================

Scope
-----
M112 continues the existing one-click Creator Studio workflow after M110.6
Final Renderable Asset. It does not render or mix audio yet. It selects one
project-local background-music asset and writes a deterministic mix plan for
M113/M114.

Pipeline boundary
-----------------
M110.6 final_renderable_assets.json
    -> M112 BackgroundMusicSelectionService
    -> music_selection_manifest.json
    -> M113 Timeline Assembly (next milestone)

Project-local music library
---------------------------
<Project>\assets\music\
    imported\
    generated\
    downloaded\

Supported audio extensions:
.wav .mp3 .m4a .aac .flac .ogg .opus

Files may be indexed with *.music.json metadata created by import_music_asset(),
or may simply be copied into one of the music folders. Unindexed audio files are
still discovered safely.

Selection policy
----------------
- Voice/narration is always primary.
- Project duration comes from voice_scenes.json.
- Intent is inferred deterministically from scene text (mood + energy).
- Local project tracks are ranked by mood/energy/tags/filename and duration.
- The selected file remains unchanged; M112 emits only a plan.
- If the track is shorter than narration, loop_required=true is recorded for
  later timeline/render handling.
- If the track is longer, trim_to_target=true is recorded.
- Default music gain is conservative (-24/-22/-20 dB by energy).
- Fade in 1.5s, fade out up to 2.0s, ducking plan enabled.
- If no music exists or music is disabled, the stage is SKIPPED, not FAILED.
- No network search is performed in M112.

Manifest
--------
<Project>\work\automation\run_...\music_selection_manifest.json

The manifest stores:
- status: selected / skipped_disabled / skipped_no_music / skipped_no_valid_music
- voice-authoritative target duration
- inferred music intent
- ranked project-local candidates
- selected project-relative music path
- gain/fade/ducking/loop/trim plan

Security / portability
----------------------
- No API keys are used or persisted.
- Selected path is project-relative in the manifest.
- No narration file is modified.
- No YouTube audiovisual content is downloaded or rendered.

Focused regression command
--------------------------
python -m unittest ^
 tests.test_final_renderable_m110_6 ^
 tests.test_automation_runner_m110_6 ^
 tests.test_gui_m110_6_final_renderable ^
 tests.test_music_selection_m112 ^
 tests.test_automation_runner_m112 ^
 tests.test_gui_m112_music_selection -v

Package verification result
---------------------------
py_compile: PASS
Focused regression: 23 tests PASS
