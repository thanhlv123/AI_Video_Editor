from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


MEDIA_RESEARCH_FORMAT = "creator_studio_media_research_m110_5"
MEDIA_RESEARCH_FILENAME = "media_research_manifest.json"
MEDIA_RESEARCH_QUERY_PLAN_FILENAME = "media_research_query_plan.json"
MEDIA_RESEARCH_ROUND_DIRNAME = "media_research_round_1"
DEFAULT_MINIMUM_IMPROVEMENT = 0.06
DEFAULT_STRONG_STOCK_THRESHOLD = 0.85


class MediaResearchError(RuntimeError):
    """Controlled M110.5 targeted re-search failure."""


def _to_float(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _score(value: Any) -> float | None:
    result = _to_float(value, None)
    if result is None or result < 0:
        return None
    return max(0.0, min(1.0, result))


def _load_json(path: Path) -> Any:
    target = Path(path)
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise MediaResearchError(f"Không thể đọc {target.name}: {type(exc).__name__}.") from None


def _atomic_json_write(path: Path, payload: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(temp_name, target)
    except Exception:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except Exception:
            pass
        raise
    return target


def _clean_phrase(value: Any, *, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n,.;:-|/")
    return text[:limit]


def _dedupe(values: list[Any], *, limit: int = 6) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_phrase(value)
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _stock_score(stock: dict[str, Any]) -> float | None:
    selection = stock.get("selection") if isinstance(stock.get("selection"), dict) else {}
    value = selection.get("best_score")
    if value in (None, ""):
        selected = stock.get("selected_media") if isinstance(stock.get("selected_media"), dict) else {}
        value = selected.get("final_score")
    return _score(value)


def _stock_validated(stock: dict[str, Any]) -> bool:
    return str(stock.get("status") or "").strip().lower() == "validated"


def _selected_identity(stock: dict[str, Any]) -> dict[str, str] | None:
    selected = stock.get("selected_media") if isinstance(stock.get("selected_media"), dict) else {}
    if not selected:
        return None
    provider = str(selected.get("provider") or selected.get("source") or "").strip().lower()
    media_id = str(selected.get("media_id") or selected.get("id") or "").strip()
    media_type = str(selected.get("media_type") or selected.get("type") or "video").strip().lower()
    if media_type not in {"image", "video"}:
        media_type = "video"
    if not provider or not media_id:
        return None
    return {"provider": provider, "media_id": media_id, "media_type": media_type}


def _scene_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("scenes") or []:
        if not isinstance(item, dict):
            continue
        scene_id = str(item.get("scene_id") or "").strip()
        if scene_id:
            result[scene_id] = item
    return result


def _plan_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("plans") or []:
        if not isinstance(item, dict):
            continue
        scene_id = str(item.get("scene_id") or "").strip()
        if scene_id:
            result[scene_id] = item
    return result


def _reference_terms(ranking_scene: dict[str, Any]) -> list[str]:
    ranking = ranking_scene.get("ranking") if isinstance(ranking_scene.get("ranking"), dict) else {}
    yt = ranking_scene.get("youtube_reference") if isinstance(ranking_scene.get("youtube_reference"), dict) else {}
    best = yt.get("best_candidate") if isinstance(yt.get("best_candidate"), dict) else {}
    return _dedupe([
        *(ranking.get("recommended_search_terms") or []),
        best.get("chapter_title"),
        best.get("matched_query"),
        best.get("title"),
    ], limit=4)


def _broaden_terms(plan: dict[str, Any]) -> list[str]:
    primary = _clean_phrase(plan.get("primary_query"))
    subject = _clean_phrase(plan.get("subject"))
    action = _clean_phrase(plan.get("action"))
    location = _clean_phrase(plan.get("location"))
    context = _clean_phrase(plan.get("context"))
    original = [_clean_phrase(x) for x in (plan.get("queries") or [])]

    combinations: list[str] = []
    if location and subject and action:
        combinations.append(f"{location} {subject} {action}")
    if location and subject:
        combinations.append(f"{location} {subject} documentary footage")
    if subject and action:
        combinations.append(f"{subject} {action} real life footage")
    if primary:
        combinations.append(f"{primary} documentary footage")
    if context and subject:
        combinations.append(f"{subject} {context}")
    combinations.extend(original)
    if primary:
        combinations.append(primary)
    return _dedupe(combinations, limit=6)


def build_research_query_plan(
    original_query_plan_path: Path,
    ranking_manifest_path: Path,
    output_path: Path,
) -> Path:
    """Build a small query plan containing only scenes M110.4 wants improved.

    YouTube metadata may influence search phrases, but the output remains a
    stock-search plan.  No YouTube URL or media bytes are promoted as render
    assets here.
    """

    original_payload = _load_json(Path(original_query_plan_path))
    ranking_payload = _load_json(Path(ranking_manifest_path))
    if not isinstance(original_payload, dict) or not isinstance(ranking_payload, dict):
        raise MediaResearchError("Query plan/ranking manifest phải là JSON object.")

    original_by_id = _plan_map(original_payload)
    plans: list[dict[str, Any]] = []

    for ranked in ranking_payload.get("scenes") or []:
        if not isinstance(ranked, dict):
            continue
        ranking = ranked.get("ranking") if isinstance(ranked.get("ranking"), dict) else {}
        if not bool(ranking.get("requires_research")):
            continue
        scene_id = str(ranked.get("scene_id") or "").strip()
        source = original_by_id.get(scene_id)
        if not source:
            continue

        action = str(ranking.get("action") or "broaden_stock_search").strip()
        if action == "reference_guided_research":
            queries = _dedupe(_reference_terms(ranked) + _broaden_terms(source), limit=6)
        else:
            queries = _broaden_terms(source)

        if not queries:
            primary = _clean_phrase(source.get("primary_query")) or "documentary footage"
            queries = [primary]

        plan = dict(source)
        plan["strategy"] = "search"
        plan["planner_source"] = "m110_5_targeted_research"
        plan["primary_query"] = queries[0]
        plan["queries"] = queries
        plan["research_action"] = action
        plan["research_source"] = str(ranking.get("semantic_preference") or "stock")
        plans.append(plan)

    payload = {
        "format": "creator_studio_visual_query_plan_m110_5_research",
        "scene_count": len(plans),
        "source": {
            "original_query_plan": Path(original_query_plan_path).name,
            "ranking_manifest": Path(ranking_manifest_path).name,
        },
        "plans": plans,
    }
    return _atomic_json_write(Path(output_path), payload)


def should_accept_research_candidate(
    *,
    old_validated: bool,
    old_score: float | None,
    new_validated: bool,
    new_score: float | None,
    minimum_improvement: float = DEFAULT_MINIMUM_IMPROVEMENT,
    strong_stock_threshold: float = DEFAULT_STRONG_STOCK_THRESHOLD,
) -> bool:
    """Conservative replacement gate used by M110.5.

    A new render-safe asset is always useful when there was no previous render
    asset.  Otherwise it must be clearly better, or cross the strong-stock
    threshold while still improving the old score.
    """

    if not new_validated:
        return False
    if not old_validated:
        return True
    if new_score is None:
        return False
    if old_score is None:
        return True
    if new_score >= old_score + max(0.0, float(minimum_improvement)):
        return True
    if new_score >= float(strong_stock_threshold) and new_score > old_score:
        return True
    return False


@dataclass(frozen=True)
class MediaResearchReport:
    total_scene_count: int
    target_count: int
    improved_count: int
    acquired_count: int
    fallback_preserved_count: int
    unresolved_count: int
    assigned_count: int
    manifest_path: str
    query_plan_path: str
    round_stock_manifest_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_scene_count": self.total_scene_count,
            "target_count": self.target_count,
            "improved_count": self.improved_count,
            "acquired_count": self.acquired_count,
            "fallback_preserved_count": self.fallback_preserved_count,
            "unresolved_count": self.unresolved_count,
            "assigned_count": self.assigned_count,
            "manifest_path": self.manifest_path,
            "query_plan_path": self.query_plan_path,
            "round_stock_manifest_path": self.round_stock_manifest_path,
        }


class AutomaticMediaResearchService:
    """Targeted one-round stock re-search after M110.4 ranking.

    The service deliberately keeps the current assignment untouched during the
    search.  Only a candidate that passes the replacement gate is assigned.
    If no better candidate is found, an already validated stock asset remains
    the render-safe fallback.
    """

    def __init__(
        self,
        *,
        project_root: Path,
        run_dir: Path,
        query_plan_path: Path,
        source_scenes_path: Path,
        voice_asset_id: str,
        ranking_manifest_path: Path,
        stock_manifest_path: Path,
        runtime_environment: dict[str, str] | None = None,
        minimum_improvement: float = DEFAULT_MINIMUM_IMPROVEMENT,
        strong_stock_threshold: float = DEFAULT_STRONG_STOCK_THRESHOLD,
        progress_callback: Callable[[int, int, str, str], None] | None = None,
        stock_service_factory: Callable[..., Any] | None = None,
        asset_lookup: Callable[[dict[str, str], float], Any | None] | None = None,
        asset_assigner: Callable[[str, Any], None] | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.query_plan_path = Path(query_plan_path).resolve()
        self.source_scenes_path = Path(source_scenes_path).resolve()
        self.voice_asset_id = str(voice_asset_id or "").strip()
        self.ranking_manifest_path = Path(ranking_manifest_path).resolve()
        self.stock_manifest_path = Path(stock_manifest_path).resolve()
        self.runtime_environment = dict(runtime_environment or {})
        self.minimum_improvement = max(0.0, float(minimum_improvement))
        self.strong_stock_threshold = max(0.0, min(1.0, float(strong_stock_threshold)))
        self.progress_callback = progress_callback
        self.stock_service_factory = stock_service_factory
        self.asset_lookup = asset_lookup
        self.asset_assigner = asset_assigner

    @property
    def output_path(self) -> Path:
        return self.run_dir / MEDIA_RESEARCH_FILENAME

    @property
    def research_query_plan_path(self) -> Path:
        return self.run_dir / MEDIA_RESEARCH_QUERY_PLAN_FILENAME

    @property
    def round_dir(self) -> Path:
        return self.run_dir / MEDIA_RESEARCH_ROUND_DIRNAME

    def _default_stock_service_factory(self):
        from creator_studio.stock_acquisition import StockAcquisitionService
        return StockAcquisitionService

    def _default_asset_lookup(self, identity: dict[str, str], required_duration: float):
        from creator_studio.stock_acquisition import ProjectStockCache
        cache = ProjectStockCache(self.project_root)
        return cache.find(
            provider=identity["provider"],
            media_id=identity["media_id"],
            media_type=identity["media_type"],
            required_duration=required_duration,
        )

    def _default_asset_assigner(self, scene_id: str, record: Any) -> None:
        from creator_studio.scene_assets import assign_media_asset
        asset_id = str(getattr(record, "asset_id", "") or "").strip()
        if not asset_id:
            raise MediaResearchError(f"Asset mới cho {scene_id} không có asset_id.")
        assign_media_asset(
            self.project_root,
            self.voice_asset_id,
            self.source_scenes_path,
            scene_id,
            asset_id,
        )

    def run(self) -> MediaResearchReport:
        for path in (
            self.query_plan_path,
            self.source_scenes_path,
            self.ranking_manifest_path,
            self.stock_manifest_path,
        ):
            if not Path(path).is_file():
                raise FileNotFoundError(path)
        if not self.voice_asset_id:
            raise MediaResearchError("Thiếu Voice Asset ID cho M110.5.")

        ranking_payload = _load_json(self.ranking_manifest_path)
        old_stock_payload = _load_json(self.stock_manifest_path)
        original_plan_payload = _load_json(self.query_plan_path)
        if not isinstance(ranking_payload, dict) or not isinstance(old_stock_payload, dict) or not isinstance(original_plan_payload, dict):
            raise MediaResearchError("Manifest đầu vào M110.5 không hợp lệ.")

        ranking_scenes = [x for x in (ranking_payload.get("scenes") or []) if isinstance(x, dict)]
        target_scenes = [
            x for x in ranking_scenes
            if isinstance(x.get("ranking"), dict) and bool(x["ranking"].get("requires_research"))
        ]
        total_scene_count = len(ranking_scenes)
        target_count = len(target_scenes)

        build_research_query_plan(
            self.query_plan_path,
            self.ranking_manifest_path,
            self.research_query_plan_path,
        )

        if target_count == 0:
            payload = {
                "format": MEDIA_RESEARCH_FORMAT,
                "created_at": datetime.now().astimezone().isoformat(),
                "scene_count": total_scene_count,
                "target_count": 0,
                "policy": {
                    "minimum_improvement": self.minimum_improvement,
                    "strong_stock_threshold": self.strong_stock_threshold,
                    "youtube_render_policy": "preview_reference_only",
                },
                "scenes": [],
            }
            _atomic_json_write(self.output_path, payload)
            return MediaResearchReport(
                total_scene_count=total_scene_count,
                target_count=0,
                improved_count=0,
                acquired_count=0,
                fallback_preserved_count=0,
                unresolved_count=sum(1 for x in ranking_scenes if not bool((x.get("stock") or {}).get("render_eligible"))),
                assigned_count=0,
                manifest_path=str(self.output_path),
                query_plan_path=str(self.research_query_plan_path),
                round_stock_manifest_path=None,
            )

        service_cls = self.stock_service_factory or self._default_stock_service_factory()

        def stock_progress(current: int, total: int, scene_id: str, phase: str):
            if self.progress_callback is not None:
                self.progress_callback(int(current), int(total), str(scene_id), str(phase))

        self.round_dir.mkdir(parents=True, exist_ok=True)
        service = service_cls(
            project_root=self.project_root,
            run_dir=self.round_dir,
            query_plan_path=self.research_query_plan_path,
            source_scenes_path=self.source_scenes_path,
            voice_asset_id=self.voice_asset_id,
            runtime_environment=self.runtime_environment,
            progress_callback=stock_progress,
            assign_assets=False,
        )
        stock_report = service.run()
        round_stock_manifest_path = Path(str(getattr(stock_report, "manifest_path", "") or ""))
        if not round_stock_manifest_path.is_file():
            raise MediaResearchError("M110.5 không tìm thấy stock manifest của lượt re-search.")

        new_stock_payload = _load_json(round_stock_manifest_path)
        if not isinstance(new_stock_payload, dict):
            raise MediaResearchError("Stock manifest của lượt re-search không hợp lệ.")

        old_by_id = _scene_map(old_stock_payload)
        new_by_id = _scene_map(new_stock_payload)
        plan_by_id = _plan_map(original_plan_payload)

        improved_count = 0
        acquired_count = 0
        fallback_preserved_count = 0
        unresolved_count = 0
        assigned_count = 0
        results: list[dict[str, Any]] = []

        lookup = self.asset_lookup or self._default_asset_lookup
        assigner = self.asset_assigner or self._default_asset_assigner

        for index, ranked in enumerate(target_scenes, start=1):
            scene_id = str(ranked.get("scene_id") or f"scene_{index:03d}").strip()
            old_scene = old_by_id.get(scene_id, {})
            new_scene = new_by_id.get(scene_id, {})
            old_stock = old_scene.get("stock") if isinstance(old_scene.get("stock"), dict) else {}
            new_stock = new_scene.get("stock") if isinstance(new_scene.get("stock"), dict) else {}
            old_validated = _stock_validated(old_stock)
            new_validated = _stock_validated(new_stock)
            old_score = _stock_score(old_stock)
            new_score = _stock_score(new_stock)
            old_identity = _selected_identity(old_stock)
            new_identity = _selected_identity(new_stock)
            same_media = bool(
                old_identity
                and new_identity
                and old_identity.get("provider") == new_identity.get("provider")
                and old_identity.get("media_id") == new_identity.get("media_id")
            )
            accept_new = should_accept_research_candidate(
                old_validated=old_validated,
                old_score=old_score,
                new_validated=new_validated,
                new_score=new_score,
                minimum_improvement=self.minimum_improvement,
                strong_stock_threshold=self.strong_stock_threshold,
            )
            # Re-ranking the exact same provider/media id is not a visual
            # improvement even if a stochastic AI score changes between runs.
            if old_validated and same_media:
                accept_new = False

            outcome = "still_unresolved"
            assignment_error = None
            assigned_identity = None

            if accept_new:
                identity = _selected_identity(new_stock)
                plan = plan_by_id.get(scene_id, {})
                required_duration = max(0.0, _to_float(plan.get("duration"), 0.0) or 0.0)
                record = lookup(identity, required_duration) if identity is not None else None
                if record is not None:
                    try:
                        assigner(scene_id, record)
                        assigned_count += 1
                        assigned_identity = identity
                        if old_validated:
                            outcome = "improved"
                            improved_count += 1
                        else:
                            outcome = "render_asset_acquired"
                            acquired_count += 1
                    except Exception as exc:
                        assignment_error = f"{type(exc).__name__}: {exc}"
                        if old_validated:
                            outcome = "fallback_preserved"
                            fallback_preserved_count += 1
                        else:
                            outcome = "still_unresolved"
                            unresolved_count += 1
                else:
                    assignment_error = "Không tìm thấy asset đã promote trong Project Media Library."
                    if old_validated:
                        outcome = "fallback_preserved"
                        fallback_preserved_count += 1
                    else:
                        unresolved_count += 1
            elif old_validated:
                outcome = "fallback_preserved"
                fallback_preserved_count += 1
            else:
                unresolved_count += 1

            if self.progress_callback is not None:
                self.progress_callback(index, max(1, target_count), scene_id, outcome)

            ranking = ranked.get("ranking") if isinstance(ranked.get("ranking"), dict) else {}
            results.append({
                "scene_id": scene_id,
                "research_action": str(ranking.get("action") or ""),
                "original": {
                    "validated": old_validated,
                    "score": old_score,
                    "selected_media": old_identity,
                },
                "research": {
                    "validated": new_validated,
                    "score": new_score,
                    "selected_media": new_identity,
                    "same_as_original": same_media,
                },
                "decision": {
                    "accepted_new_asset": bool(accept_new and assigned_identity is not None),
                    "outcome": outcome,
                    "minimum_improvement": self.minimum_improvement,
                    "assignment_error": assignment_error,
                    "render_source": "stock" if outcome != "still_unresolved" else "none",
                },
            })

        # Non-target scenes that were already render-safe remain ready.  Count
        # any pre-existing unresolved non-target defensively.
        for ranked in ranking_scenes:
            if ranked in target_scenes:
                continue
            stock = ranked.get("stock") if isinstance(ranked.get("stock"), dict) else {}
            if not bool(stock.get("render_eligible")):
                unresolved_count += 1

        payload = {
            "format": MEDIA_RESEARCH_FORMAT,
            "created_at": datetime.now().astimezone().isoformat(),
            "scene_count": total_scene_count,
            "target_count": target_count,
            "policy": {
                "minimum_improvement": self.minimum_improvement,
                "strong_stock_threshold": self.strong_stock_threshold,
                "max_research_rounds": 1,
                "youtube_render_policy": "preview_reference_only",
                "replacement_policy": "only_clear_improvement_or_missing_render_asset",
            },
            "source": {
                "ranking_manifest": self.ranking_manifest_path.name,
                "original_stock_manifest": self.stock_manifest_path.name,
                "research_query_plan": self.research_query_plan_path.name,
                "round_stock_manifest": str(round_stock_manifest_path.relative_to(self.run_dir)) if self.run_dir in round_stock_manifest_path.parents else round_stock_manifest_path.name,
            },
            "summary": {
                "improved_count": improved_count,
                "acquired_count": acquired_count,
                "fallback_preserved_count": fallback_preserved_count,
                "unresolved_count": unresolved_count,
                "assigned_count": assigned_count,
            },
            "scenes": results,
        }
        _atomic_json_write(self.output_path, payload)

        return MediaResearchReport(
            total_scene_count=total_scene_count,
            target_count=target_count,
            improved_count=improved_count,
            acquired_count=acquired_count,
            fallback_preserved_count=fallback_preserved_count,
            unresolved_count=unresolved_count,
            assigned_count=assigned_count,
            manifest_path=str(self.output_path),
            query_plan_path=str(self.research_query_plan_path),
            round_stock_manifest_path=str(round_stock_manifest_path),
        )
