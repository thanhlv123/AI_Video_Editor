from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


MEDIA_RANKING_FORMAT = "creator_studio_media_ranking_m110_4"
MEDIA_RANKING_FILENAME = "media_ranking_manifest.json"
DEFAULT_STRONG_STOCK_THRESHOLD = 0.85
DEFAULT_LOW_STOCK_THRESHOLD = 0.65
DEFAULT_REFERENCE_RELEVANCE = 0.70
DEFAULT_REFERENCE_MARGIN = 0.05


class MediaRankingError(RuntimeError):
    """Controlled M110.4 unified-ranking failure."""


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


def _load_json(path: Path) -> dict[str, Any]:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise MediaRankingError(f"Không thể đọc {target.name}: {type(exc).__name__}.") from None
    if not isinstance(payload, dict):
        raise MediaRankingError(f"{target.name} phải chứa JSON object.")
    return payload


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> Path:
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


def _stock_score(stock: dict[str, Any]) -> float | None:
    selection = stock.get("selection") if isinstance(stock.get("selection"), dict) else {}
    value = selection.get("best_score")
    if value in (None, ""):
        selected = stock.get("selected_media") if isinstance(stock.get("selected_media"), dict) else {}
        value = selected.get("final_score")
    return _score(value)


def _safe_stock_identity(stock: dict[str, Any]) -> dict[str, Any] | None:
    selected = stock.get("selected_media") if isinstance(stock.get("selected_media"), dict) else {}
    if not selected:
        return None
    return {
        "provider": str(selected.get("provider") or selected.get("source") or "").strip(),
        "media_id": str(selected.get("media_id") or selected.get("id") or "").strip(),
        "media_type": str(selected.get("media_type") or selected.get("type") or "").strip(),
    }


def _best_reference(scene: dict[str, Any]) -> dict[str, Any] | None:
    best = scene.get("best_candidate") if isinstance(scene.get("best_candidate"), dict) else None
    if best:
        return best
    candidates = scene.get("candidates") if isinstance(scene.get("candidates"), list) else []
    valid = [item for item in candidates if isinstance(item, dict)]
    if not valid:
        return None
    valid.sort(key=lambda item: (-(_score(item.get("score")) or 0.0), str(item.get("video_id") or "")))
    return valid[0]


def _safe_reference(best: dict[str, Any] | None) -> dict[str, Any] | None:
    if not best:
        return None
    return {
        "provider": "youtube_reference",
        "video_id": str(best.get("video_id") or "").strip(),
        "title": str(best.get("title") or "").strip()[:300],
        "channel_title": str(best.get("channel_title") or "").strip()[:200],
        "score": _score(best.get("score")),
        "matched_query": str(best.get("matched_query") or "").strip()[:300],
        "chapter_title": str(best.get("chapter_title") or "").strip()[:300] or None,
        "segment_start_seconds": _to_float(best.get("segment_start_seconds"), None),
        "segment_end_seconds": _to_float(best.get("segment_end_seconds"), None),
        "segment_basis": str(best.get("segment_basis") or "").strip()[:100] or None,
        "preview_only": True,
        "render_eligible": False,
    }


def _recommended_terms(reference: dict[str, Any] | None) -> list[str]:
    if not reference:
        return []
    result: list[str] = []
    for value in (
        reference.get("chapter_title"),
        reference.get("matched_query"),
        reference.get("title"),
    ):
        text = str(value or "").strip()
        if text and text.casefold() not in {item.casefold() for item in result}:
            result.append(text[:300])
    return result[:3]


@dataclass(frozen=True)
class MediaRankingReport:
    total_scene_count: int
    compared_count: int
    keep_stock_count: int
    reference_guided_count: int
    broaden_search_count: int
    render_ready_count: int
    unresolved_render_count: int
    manifest_path: str

    @property
    def research_count(self) -> int:
        return int(self.reference_guided_count) + int(self.broaden_search_count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_scene_count": self.total_scene_count,
            "compared_count": self.compared_count,
            "keep_stock_count": self.keep_stock_count,
            "reference_guided_count": self.reference_guided_count,
            "broaden_search_count": self.broaden_search_count,
            "research_count": self.research_count,
            "render_ready_count": self.render_ready_count,
            "unresolved_render_count": self.unresolved_render_count,
            "manifest_path": self.manifest_path,
        }


class UnifiedMediaRankingService:
    """Compare render-safe stock with preview-only YouTube references.

    The two source scores are not treated as interchangeable measurements:
    stock score comes from the visual stock pipeline while YouTube score is
    metadata/chapter relevance. M110.4 therefore uses threshold bands and a
    conservative policy instead of simply choosing the numerically larger
    score. YouTube can guide the next stock search, but never becomes a render
    asset here.
    """

    def __init__(
        self,
        *,
        run_dir: Path,
        stock_manifest_path: Path,
        youtube_manifest_path: Path,
        strong_stock_threshold: float = DEFAULT_STRONG_STOCK_THRESHOLD,
        low_stock_threshold: float = DEFAULT_LOW_STOCK_THRESHOLD,
        reference_relevance: float = DEFAULT_REFERENCE_RELEVANCE,
        reference_margin: float = DEFAULT_REFERENCE_MARGIN,
        progress_callback: Callable[[int, int, str, str], None] | None = None,
    ):
        self.run_dir = Path(run_dir).resolve()
        self.stock_manifest_path = Path(stock_manifest_path).resolve()
        self.youtube_manifest_path = Path(youtube_manifest_path).resolve()
        self.strong_stock_threshold = max(0.0, min(1.0, float(strong_stock_threshold)))
        self.low_stock_threshold = max(0.0, min(self.strong_stock_threshold, float(low_stock_threshold)))
        self.reference_relevance = max(0.0, min(1.0, float(reference_relevance)))
        self.reference_margin = max(0.0, min(1.0, float(reference_margin)))
        self.progress_callback = progress_callback

    @property
    def output_path(self) -> Path:
        return self.run_dir / MEDIA_RANKING_FILENAME

    def _decision(
        self,
        *,
        stock_validated: bool,
        stock_score: float | None,
        reference: dict[str, Any] | None,
    ) -> tuple[str, str, str]:
        ref_score = _score((reference or {}).get("score")) if reference else None
        has_chapter = bool((reference or {}).get("chapter_title"))

        if stock_validated and stock_score is not None and stock_score >= self.strong_stock_threshold:
            return (
                "keep_stock",
                "stock",
                "Stock đã đạt ngưỡng chất lượng cao; YouTube không được dùng làm render asset.",
            )

        if not stock_validated:
            if reference is not None and ref_score is not None and ref_score >= max(0.55, self.reference_relevance - 0.15):
                return (
                    "reference_guided_research",
                    "youtube_reference",
                    "Chưa có render asset; dùng YouTube Reference để hướng dẫn tìm lại nguồn render-safe.",
                )
            return (
                "broaden_stock_search",
                "none",
                "Chưa có render asset và reference chưa đủ mạnh; cần mở rộng truy vấn stock.",
            )

        # A validated stock file is always retained as the render-safe fallback.
        if reference is not None and ref_score is not None:
            reference_is_strong = ref_score >= self.reference_relevance
            advantage = stock_score is None or ref_score >= stock_score + self.reference_margin
            if reference_is_strong and (advantage or has_chapter or (stock_score is not None and stock_score < self.low_stock_threshold)):
                return (
                    "reference_guided_research",
                    "youtube_reference",
                    "Stock được giữ làm fallback; reference đủ liên quan để hướng dẫn một lượt tìm stock tốt hơn.",
                )

        if stock_score is None or stock_score < self.low_stock_threshold:
            return (
                "broaden_stock_search",
                "stock",
                "Stock đã render được nhưng điểm chất lượng thấp/không rõ; cần mở rộng truy vấn trước khi chốt.",
            )

        return (
            "keep_stock",
            "stock",
            "Stock đã render được và reference không đủ mạnh để biện minh cho một lượt tìm lại.",
        )

    def run(self) -> MediaRankingReport:
        stock_payload = _load_json(self.stock_manifest_path)
        youtube_payload = _load_json(self.youtube_manifest_path)
        stock_scenes = [item for item in (stock_payload.get("scenes") or []) if isinstance(item, dict)]
        youtube_scenes = [item for item in (youtube_payload.get("scenes") or []) if isinstance(item, dict)]
        youtube_by_id = {
            str(item.get("scene_id") or "").strip(): item
            for item in youtube_scenes
            if str(item.get("scene_id") or "").strip()
        }

        results: list[dict[str, Any]] = []
        keep_stock_count = 0
        reference_guided_count = 0
        broaden_search_count = 0
        render_ready_count = 0
        compared_count = 0
        total = len(stock_scenes)

        for index, scene in enumerate(stock_scenes, start=1):
            scene_id = str(scene.get("scene_id") or "").strip() or f"scene_{index:03d}"
            stock = scene.get("stock") if isinstance(scene.get("stock"), dict) else {}
            stock_status = str(stock.get("status") or "").strip().lower()
            stock_validated = stock_status == "validated"
            stock_score = _stock_score(stock)
            stock_identity = _safe_stock_identity(stock)
            yt_scene = youtube_by_id.get(scene_id, {})
            yt_status = str(yt_scene.get("status") or "not_targeted").strip().lower()
            reference = _safe_reference(_best_reference(yt_scene))
            if reference is not None:
                compared_count += 1

            action, semantic_preference, reason = self._decision(
                stock_validated=stock_validated,
                stock_score=stock_score,
                reference=reference,
            )
            if action == "keep_stock":
                keep_stock_count += 1
            elif action == "reference_guided_research":
                reference_guided_count += 1
            else:
                broaden_search_count += 1
            if stock_validated:
                render_ready_count += 1

            ref_score = _score((reference or {}).get("score")) if reference else None
            score_gap = None
            if stock_score is not None and ref_score is not None:
                score_gap = round(ref_score - stock_score, 6)

            result = {
                "scene_id": scene_id,
                "stock": {
                    "status": stock_status or "unknown",
                    "score": stock_score,
                    "selected_media": stock_identity,
                    "render_eligible": bool(stock_validated),
                },
                "youtube_reference": {
                    "status": yt_status,
                    "candidate_count": int(yt_scene.get("candidate_count") or 0),
                    "best_candidate": reference,
                    "preview_only": True,
                    "render_eligible": False,
                },
                "ranking": {
                    "action": action,
                    "semantic_preference": semantic_preference,
                    "render_source": "stock" if stock_validated else "none",
                    "requires_research": action != "keep_stock",
                    "score_gap_diagnostic_only": score_gap,
                    "reason": reason,
                    "recommended_search_terms": _recommended_terms(reference),
                },
            }
            results.append(result)
            if self.progress_callback is not None:
                self.progress_callback(index, max(1, total), scene_id, action)

        unresolved_render_count = max(0, total - render_ready_count)
        payload = {
            "format": MEDIA_RANKING_FORMAT,
            "created_at": datetime.now().astimezone().isoformat(),
            "policy": {
                "strong_stock_threshold": self.strong_stock_threshold,
                "low_stock_threshold": self.low_stock_threshold,
                "reference_relevance": self.reference_relevance,
                "reference_margin": self.reference_margin,
                "score_comparability": "diagnostic_only",
                "youtube_render_policy": "preview_reference_only",
            },
            "source": {
                "stock_manifest": self.stock_manifest_path.name,
                "youtube_reference_manifest": self.youtube_manifest_path.name,
            },
            "scene_count": total,
            "scenes": results,
        }
        _atomic_json_write(self.output_path, payload)
        return MediaRankingReport(
            total_scene_count=total,
            compared_count=compared_count,
            keep_stock_count=keep_stock_count,
            reference_guided_count=reference_guided_count,
            broaden_search_count=broaden_search_count,
            render_ready_count=render_ready_count,
            unresolved_render_count=unresolved_render_count,
            manifest_path=str(self.output_path),
        )
