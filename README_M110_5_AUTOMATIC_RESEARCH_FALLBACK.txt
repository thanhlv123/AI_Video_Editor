M110.5 — Automatic Re-search / Fallback
========================================

Purpose
-------
Continue automatically from M110.4 when one or more scenes need better media.
M110.5 performs one targeted Pexels/Pixabay re-search round and keeps the
existing render-safe stock assignment unless the replacement is clearly better.

Key behavior
------------
1. Reads media_ranking_manifest.json.
2. Builds media_research_query_plan.json only for requires_research scenes.
3. reference_guided_research may use sanitized YouTube metadata as SEARCH
   GUIDANCE ONLY. YouTube remains preview/reference-only and is never downloaded
   or promoted as a render asset.
4. broaden_stock_search derives broader stock queries from the original scene
   subject/action/location/context.
5. Runs the existing tested StockAcquisitionService in a separate
   media_research_round_1 directory.
6. StockAcquisitionService now supports assign_assets=False. This is backward
   compatible; existing callers still default to True.
7. The current scene assignment is left untouched during re-search.
8. A new validated asset replaces the old one only when it improves score by
   at least 0.06, or crosses the 0.85 strong-stock threshold while improving.
9. If no clear improvement is found, the original validated stock remains the
   render-safe fallback.
10. Writes media_research_manifest.json with safe diagnostics; no API keys.

Artifacts
---------
<run>/media_research_query_plan.json
<run>/media_research_round_1/stock_acquisition_manifest.json
<run>/media_research_manifest.json

Workflow state
--------------
If every searched scene has a render-safe fallback after M110.5:
  media_search      -> COMPLETED
  media_assignment  -> COMPLETED
  next user-visible stage -> background music

If a scene still has no render-safe asset:
  workflow stays at media search and waits for M110.6 final renderable fallback.

Additional fix
--------------
M110.5 removes the old VoicePipeline finished-handler race that incorrectly
cleared media_query_worker after SceneQueryPlanningWorker could already have
been scheduled.
