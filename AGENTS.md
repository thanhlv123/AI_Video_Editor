# AI VIDEO CREATOR STUDIO
# DEVELOPMENT RULES FOR AI CODING AGENTS

## 1. PROJECT IDENTITY

Project name:

AI VIDEO CREATOR STUDIO

Project root:

D:\YouTubeTools\AI_Video_Editor

Platform:

Windows

Main technologies:

- Python 3.12
- PyQt6
- FFmpeg
- Git
- KIE AI
- Pexels
- Pixabay


## 2. IMPORTANT PROJECT STATUS

This is NOT a new project.

This repository already contains a working production video pipeline.

The current production pipeline has been tested successfully and contains
important fallback logic, search logic, AI analysis logic, media ranking,
timeline generation and FFmpeg rendering.

Do NOT rewrite existing production systems simply because a different
architecture appears cleaner.

Backward compatibility is a major requirement.


## 3. PRODUCT GOAL

We are expanding the existing project into:

AI VIDEO CREATOR STUDIO

The application should allow a non-technical user to create a complete video
from one or more of the following inputs:

- pasted text
- TXT file
- DOCX file
- local video files
- local image files
- local audio files
- user-owned video footage
- voice recordings
- generated TTS voice
- background music
- authorized/licensed media
- YouTube reference URLs
- Facebook reference URLs


The final system should be able to:

1. Understand the script semantically.
2. Divide content into meaningful visual scenes.
3. Generate a visual plan.
4. Search appropriate media.
5. Prefer the user's own footage when appropriate.
6. Analyze reference/competitor content.
7. Generate or import voice.
8. Align script and voice.
9. Create bilingual review subtitles.
10. Automatically construct a timeline.
11. Add music and SFX.
12. Check continuity and quality.
13. Render the final video.
14. Preserve source and rights information.
15. Support project versioning and recovery.


## 4. CORE DEVELOPMENT PRINCIPLE

TEXT IS THE SEMANTIC SOURCE.

VOICE IS PRIMARILY THE TIMING SOURCE.

The new pipeline should prefer:

SCRIPT
→ semantic analysis
→ visual planning
→ media retrieval
→ voice generation/alignment
→ timeline
→ render

instead of relying on arbitrary subtitle chunks as the main semantic source.


## 5. EXISTING STABLE PRODUCTION FILES

Treat the following files as protected production modules.

Do NOT modify them unless the current milestone explicitly requires it and the
change has been reviewed first.

Protected files include:

pipeline/scene_pipeline.py
pipeline/full_video_pipeline.py
pipeline/context_geo.py
pipeline/visual_strategy.py

stock/balanced_search_manager.py
stock/search_manager.py
stock/ranker.py
stock/visual_ranker.py
stock/selector.py
stock/validator.py
stock/downloader.py

config/api_key_manager.py
api_keys_dialog.py

engine/renderer.py
engine/timeline_renderer.py

gui_ai_video.py
run_ai_video.py


## 6. EXISTING SYSTEMS THAT MUST BE PRESERVED

The repository already contains working systems including:

- ScenePipeline
- FullVideoPipeline
- Pexels provider
- Pixabay provider
- BalancedStockSearchManager
- MediaRanker
- VisualRanker
- MediaSelector
- media download
- media validation
- KIE AI integration
- API key management
- timeline building
- FFmpeg rendering
- voice pipeline
- Whisper transcription


Important tested behaviors include:

- AI Visual Fallback V5
- Semantic Window
- Context Geography
- Adaptive Geography
- Visual Strategy
- provider balancing
- local ranking fallback
- project resume/cache behavior

Do not remove or silently replace these behaviors.


## 7. AI VISUAL FALLBACK

Existing AI ranking fallback behavior is important.

Transient API failures must not automatically destroy the production run.

The system should continue to support graceful fallback from AI ranking to
local ranking when appropriate.


## 8. NEW ARCHITECTURE DIRECTION

New functionality should preferably be implemented as NEW modules instead of
rewriting stable production modules.

The target architecture contains these major systems:

1. Project Manifest V2
2. Project Orchestrator
3. Content Ingest Engine
4. Semantic Story Engine
5. Visual Director
6. Competitor / Reference Intelligence
7. Personal Media Library
8. Media Retrieval Engine
9. Voice Studio
10. Forced Alignment Engine
11. Bilingual Subtitle & Review Engine
12. Auto Editor
13. Story / Pacing Engine
14. Audio / Music / SFX Director
15. Continuity Guard
16. Rights & Source Provenance
17. Quality Control
18. Cache / Resume / Reliability Layer
19. Project Versioning
20. Renderer / Export
21. YouTube Package
22. Future Analytics Feedback Loop


## 9. PROJECT MANIFEST V2

Project Manifest V2 will become the central source of truth.

All new engines should communicate through structured project state rather
than hidden global state.

The manifest should eventually support:

- project metadata
- schema version
- script
- source language
- review language
- input files
- owned media
- reference media
- reference URLs
- scenes
- visual plans
- search queries
- avoid queries
- selected media
- source rights
- voice configuration
- voice file
- alignment
- subtitle tracks
- translation review status
- music
- SFX
- timeline
- processing states
- cache signatures
- errors
- project versions


## 10. PERSONAL MEDIA LIBRARY

Personal Media Library is a major product feature.

The user may own hundreds or thousands of self-recorded videos.

The system should index those videos and allow semantic search of individual
shots.

IMPORTANT:

Do NOT physically split source videos during indexing.

Store:

source file
+
start timestamp
+
end timestamp

Actual FFmpeg extraction should occur only when a shot is selected for a
project.


The Personal Media Library should eventually support:

- SQLite database
- media records
- virtual shots
- collections
- automatic tags
- semantic descriptions
- subject
- action
- environment
- object tags
- shot type
- camera movement
- transcript
- orientation
- resolution
- quality score
- semantic embeddings
- times used
- last project used
- rights status
- analysis status


Search should eventually combine:

- keyword search
- semantic search
- metadata filters
- visual similarity
- usage history


Default source priority should favor original user footage:

1. Personal Media Library
2. Current project media
3. Licensed media
4. Pexels
5. Pixabay
6. AI Image
7. AI Video


## 11. REPETITION GUARD

The system should avoid repeatedly using the same media.

Track:

- times_used
- last_used
- last_project
- current project usage

Repeated media should receive a ranking penalty when appropriate.


## 12. COMPETITOR / REFERENCE INTELLIGENCE

Competitor YouTube/Facebook content is:

REFERENCE_ONLY

by default.

Reference content may be analyzed for:

- topic
- transcript
- hook
- scene structure
- shot duration
- visual concepts
- B-roll ideas
- pacing
- transitions
- title patterns
- thumbnail patterns
- search keyword ideas

Competitor/reference media must NOT automatically become final-project
footage.


Only content explicitly marked as one of the following may become editable
source media:

- OWNED
- LICENSED
- PUBLIC_DOMAIN
- appropriately authorized / compatible licensed content


Media with unknown rights remains:

REFERENCE_ONLY


## 13. RIGHTS AND SOURCE PROVENANCE

Every media asset should eventually contain source information.

Possible rights states:

OWNED
LICENSED
PUBLIC_DOMAIN
REFERENCE_ONLY
UNKNOWN

For external stock media, preserve useful metadata such as:

- provider
- original URL
- source ID
- license metadata when available

The system should eventually be able to produce a source report.


## 14. VOICE STUDIO

Voice should support both imported voice and generated voice.

Future provider architecture should be modular.

Possible providers may include:

- KIE-supported TTS
- ElevenLabs
- Edge TTS
- Google
- Azure
- OpenAI
- other future providers

Do not tightly couple the project model to one TTS provider.


Voice features may eventually include:

- language
- voice
- speed
- style
- pitch
- emotion
- pronunciation dictionary
- preview
- selected scene generation
- full project generation


## 15. FORCED ALIGNMENT

When script and voice are both available, use alignment rather than blindly
retranscribing the generated voice.

Preferred architecture:

SCRIPT
+
VOICE
→ alignment
→ timestamps


If no source script exists:

VOICE
→ speech-to-text
→ reconstructed semantic text
→ scene planning


## 16. BILINGUAL REVIEW SUBTITLES

Bilingual subtitle review is a core feature.

Example:

Audience language:
English

Voice:
English

Creator review language:
Vietnamese


Preview should support:

- Original + Vietnamese
- Original only
- Vietnamese only
- subtitles off


The review subtitle does NOT have to appear in the final rendered video.

Original and translated tracks should share aligned timing.


Each subtitle segment should eventually support:

- scene_id
- start
- end
- original_text
- translated_text
- translation_confidence
- review_status
- original_locked
- translation_locked


A user-approved translation must not be silently regenerated.


## 17. VISUAL REVIEW

Preview should eventually allow the user to identify when the visual does not
match the narration.

Future quality control may compare:

NARRATION
↔
CURRENT VISUAL

and report low-confidence visual matches.


## 18. STORY / PACING ENGINE

The system should not merely choose semantically correct media.

It should also maintain an engaging visual rhythm.

Examples:

- hook
- establishing shot
- detail shot
- people/activity shot
- close-up
- movement shot
- payoff
- CTA


Avoid long repetitive sequences such as:

wide landscape
→ wide landscape
→ wide landscape
→ wide landscape

when alternative visual structures are appropriate.


## 19. VISUAL CONTINUITY

Future continuity checks may include:

- day/night consistency
- weather consistency
- geographic consistency
- season consistency
- time-period consistency
- environment consistency
- wardrobe/context consistency

Do not infer sensitive human attributes.

Use visible non-sensitive context such as:

- environment
- architecture
- terrain
- weather
- activity
- clothing style
- urban/rural setting


## 20. AUDIO DIRECTOR

The system should eventually support:

- background music
- multiple music sections
- ambience
- SFX
- fade in
- fade out
- crossfade
- voice ducking
- volume normalization


Audio selection may use scene mood and story pacing.


## 21. PROJECT VERSIONING

Important AI actions should eventually be recoverable.

Examples:

V1 Auto Build
V2 New Voice
V3 Scene 12 Media Replacement
V4 Subtitle Review

Do not design irreversible AI operations when a recoverable approach is
reasonable.


## 22. CACHE AND RELIABILITY

The application should avoid recomputing expensive results.

If a source file has already been:

- transcribed
- analyzed
- shot-detected
- tagged
- embedded
- thumbnailed

reuse cached data when the source signature is unchanged.


If one script sentence changes, avoid rebuilding unrelated scenes when
possible.


Long-running operations should support:

- progress
- retry
- timeout
- fallback
- cancellation where possible
- resume
- meaningful error messages


## 23. API COST MANAGEMENT

Future AI operations may cost money.

The architecture should allow future modes such as:

- Economy
- Balanced
- Best Quality

Avoid unnecessary repeated AI requests.


## 24. GUI PRINCIPLES

The GUI is intended for non-technical users.

The MAIN WINDOW must remain simple.

Primary workflow should look like:

1. Content
2. Media
3. Voice
4. Preview
5. Export


The main workspace may contain:

- project name
- scene list
- suggested media
- preview player
- project progress
- simple timeline
- render button


Do NOT permanently show every advanced control.


Advanced functions should open only when requested, for example:

- API management
- Personal Media Library
- Competitor research
- voice configuration
- subtitle editor
- advanced media filters
- export settings
- logs
- AI settings
- workflow configuration


## 25. NEW GUI

The future Creator Studio should use a new launcher:

gui_creator_studio.py


Do NOT replace or delete:

gui_ai_video.py

until the new GUI has been proven stable.


## 26. PYQT THREADING RULE

Never perform long-running work directly on the PyQt GUI event loop.

Long operations such as:

- AI calls
- transcription
- video indexing
- media downloading
- FFmpeg
- rendering
- semantic embedding
- external API calls

must use an appropriate worker architecture such as:

- QThread
- QProcess
- subprocess worker
- existing asynchronous system


The GUI must remain responsive.


## 27. SECRET MANAGEMENT

Never print real API keys.

Never store real API keys in source files.

Never store real credentials in test fixtures.

Never commit credentials.

Reuse the existing API key management architecture where appropriate.

Do not replace the existing credential system without explicit approval.


## 28. WINDOWS COMPATIBILITY

This application runs on Windows.

Pay special attention to:

- Windows paths
- spaces in paths
- Unicode filenames
- Vietnamese filenames
- subprocess quoting
- FFmpeg quoting
- file locking
- long path handling
- process termination


Do not assume Linux path semantics.


## 29. DEVELOPMENT SAFETY

Before modifying a production file:

1. Read the actual current file.
2. Understand its existing behavior.
3. Search its callers.
4. Search related tests.
5. Explain why modification is required.

Never rewrite a large existing production file from memory.


## 30. MINIMAL CHANGE PRINCIPLE

Prefer:

new module
+
small integration point

instead of:

large production refactor


Do not perform repository-wide refactoring unless explicitly requested.


## 31. TESTING REQUIREMENTS

For every implementation milestone:

1. Run Python compilation checks.
2. Run relevant unit tests.
3. Run related regression tests.
4. Inspect Git diff.
5. Check protected production files.
6. Check for secrets.
7. Report failures honestly.


At minimum use:

python -m py_compile

for newly created or modified Python modules.


## 32. REQUIRED COMPLETION REPORT

At the end of each milestone report:

FILES CREATED

FILES MODIFIED

FILES DELETED

TESTS RUN

TEST RESULTS

KNOWN LIMITATIONS

GIT DIFF SUMMARY

PRODUCTION FILES TOUCHED

SECRETS CHECK

PASS / FAIL


## 33. MILESTONE RULE

Work on ONE milestone at a time.

Do not automatically continue to the next feature.

When the requested milestone is complete:

STOP.


Do not add unrelated features simply because they seem useful.


## 34. READ-ONLY REQUESTS

If the user says:

READ-ONLY
DO NOT MODIFY FILES
INSPECT ONLY

then:

DO NOT create files.
DO NOT modify files.
DO NOT install packages.
DO NOT run destructive commands.


Only inspect and report.


## 35. PACKAGE INSTALLATION

Do not install new Python or Node packages without explicit approval.

First explain:

- package name
- why it is needed
- alternatives
- project impact


## 36. FORBIDDEN WITHOUT EXPLICIT APPROVAL

Do NOT:

- delete production files
- rename stable production modules
- replace PyQt6
- change Python version
- replace the API key system
- remove fallback systems
- perform mass refactors
- modify unrelated code
- reset Git
- clean Git working tree
- force checkout
- delete user media
- delete project data
- rewrite Git history
- push code to a remote repository


## 37. GIT SAFETY

The repository has a safety baseline.

Do not run destructive Git operations without explicit approval.

Do not automatically use:

git reset --hard
git clean -fd
git checkout -- .
git restore .
git rebase
git push --force


Use Git primarily for:

- status
- diff
- log
- safe milestone commits after user approval


## 38. DEVELOPMENT ROADMAP

Current high-level roadmap:

60 - Creator Studio GUI Shell

61 - Project Manifest V2

62 - Project Orchestrator

63 - Content Ingest

64 - Semantic Story / Scene Planner

65 - Voice Studio / TTS

66 - Forced Alignment

67 - Core Media Retrieval

68 - Auto Editor / Timeline

69 - Audio / Music / SFX

70 - Competitor Intelligence Engine

71 - Personal Media Library Engine

72 - Bilingual Subtitle & Review Engine

73 - Story / Pacing / Continuity

74 - Rights / Source Provenance

75 - Quality Control

76 - Cache / Resume / Reliability

77 - Project Versioning

78 - Export / YouTube Package

79 - Analytics / Feedback Learning


This roadmap may evolve, but changes should be deliberate and documented.


## 39. FIRST PRINCIPLE FOR AI AGENTS

DO NOT GUESS.

Inspect the current repository before answering questions about existing code.

Prefer evidence from actual code over assumptions.


## 40. END GOAL

The final application should feel simple to the user:

INPUT CONTENT
→ AI ANALYSIS
→ MEDIA
→ VOICE
→ PREVIEW
→ REVIEW
→ RENDER


Internally it may contain sophisticated AI systems.

Externally it should remain understandable to a user who does not know
programming or advanced video editing.