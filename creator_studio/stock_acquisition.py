from __future__ import annotations

import inspect
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from creator_studio.project_storage import (
    MediaAssetRecord,
    finalize_media_asset,
    find_media_asset_by_path,
    new_media_asset_target,
    scan_media_assets,
)
from creator_studio.scene_assets import assign_media_asset


STOCK_MANIFEST_FORMAT = "creator_studio_stock_acquisition_m110_2"
STOCK_MANIFEST_FILENAME = "stock_acquisition_manifest.json"
STOCK_DOWNLOAD_DIRNAME = "stock_downloads"
STOCK_SOURCE_PREFIX = "stock"


class StockAcquisitionError(RuntimeError):
    """Controlled M110.2 acquisition failure."""


@dataclass(frozen=True)
class StockAcquisitionReport:
    total_search_scenes: int
    validated_count: int
    assigned_count: int
    unresolved_count: int
    cache_hit_count: int
    new_asset_count: int
    reused_asset_count: int
    provider_names: tuple[str, ...]
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_search_scenes": self.total_search_scenes,
            "validated_count": self.validated_count,
            "assigned_count": self.assigned_count,
            "unresolved_count": self.unresolved_count,
            "cache_hit_count": self.cache_hit_count,
            "new_asset_count": self.new_asset_count,
            "reused_asset_count": self.reused_asset_count,
            "provider_names": list(self.provider_names),
            "manifest_path": self.manifest_path,
        }


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except Exception:
        return float(default)
    return result


def _atomic_json_write(path: Path, payload: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
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


@contextmanager
def _temporary_environment(values: dict[str, str] | None):
    values = {
        str(key): str(value)
        for key, value in (values or {}).items()
        if value not in (None, "")
    }
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def _provider_name(candidate: dict[str, Any]) -> str:
    return str(
        candidate.get("provider")
        or candidate.get("source")
        or "stock"
    ).strip().lower()


def _media_id(candidate: dict[str, Any]) -> str:
    raw = candidate.get("media_id")
    if raw is None:
        raw = candidate.get("id")
    return str(raw or "").strip()


def stock_source_reference(provider: str, media_id: str) -> str:
    return f"{STOCK_SOURCE_PREFIX}:{str(provider).strip().lower()}:{str(media_id).strip()}"


def _read_query_plan(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    plans = payload.get("plans") if isinstance(payload, dict) else None
    if not isinstance(plans, list):
        raise StockAcquisitionError("visual_query_plan.json không chứa danh sách plans hợp lệ.")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(plans, start=1):
        if not isinstance(raw, dict):
            raise StockAcquisitionError(f"Query plan #{index} không hợp lệ.")
        scene_id = str(raw.get("scene_id") or "").strip()
        if not scene_id:
            raise StockAcquisitionError(f"Query plan #{index} thiếu scene_id.")
        if scene_id in seen:
            raise StockAcquisitionError(f"scene_id bị trùng trong query plan: {scene_id}")
        seen.add(scene_id)
        result.append(raw)
    return result


def build_stock_manifest(query_plan_path: Path, output_path: Path) -> Path:
    """Translate M110.1 visual guidance to the tested legacy stock-pipeline shape.

    The full narration is deliberately not copied into this manifest.  The
    structured visual guidance is sufficient for search/ranking and keeps the
    automation run from becoming a second script store.
    """

    scenes: list[dict[str, Any]] = []
    for plan in _read_query_plan(query_plan_path):
        if str(plan.get("strategy") or "search") == "reuse_previous":
            continue
        primary = str(plan.get("primary_query") or "").strip()
        queries = [str(item).strip() for item in (plan.get("queries") or []) if str(item).strip()]
        if not primary and queries:
            primary = queries[0]
        if not primary:
            continue

        start = _to_float(plan.get("start"), 0.0)
        end = _to_float(plan.get("end"), start)
        duration = max(0.0, _to_float(plan.get("duration"), end - start))
        if duration <= 0:
            duration = max(0.0, end - start)
        if end <= start or duration <= 0:
            raise StockAcquisitionError(
                f"Timing không hợp lệ cho {plan.get('scene_id')}: {start} -> {end}"
            )

        context = str(plan.get("context") or "").strip()
        subject = str(plan.get("subject") or "").strip()
        action = str(plan.get("action") or "").strip()
        location = str(plan.get("location") or "").strip()
        mood = str(plan.get("mood") or "").strip()
        shot = str(plan.get("shot") or "any").strip() or "any"
        motion = str(plan.get("motion") or "any").strip() or "any"
        preferred = str(plan.get("preferred_type") or "video").strip().lower()
        if preferred not in {"video", "image", "either"}:
            preferred = "video"

        # The legacy visual ranker expects a dialogue-like semantic field.  Use
        # compact visual intent instead of duplicating narration text.
        semantic_summary = " · ".join(
            value for value in (subject, action, location, context, primary) if value
        )

        scenes.append({
            "scene_id": str(plan["scene_id"]),
            "start": start,
            "end": end,
            "duration": duration,
            "dialogue": semantic_summary or primary,
            "analysis": {
                "context": context,
                "subject": subject,
                "action": action,
                "location": location,
                "mood": mood,
                "shot": shot,
                "motion": motion,
            },
            "search": {
                "primary_keyword": primary,
                "keywords": queries,
                "avoid": [
                    str(item).strip()
                    for item in (plan.get("avoid") or [])
                    if str(item).strip()
                ],
            },
            "stock": {
                "status": "pending",
                "preferred_type": preferred,
                "searches": [],
                "candidates": [],
                "selected_media": None,
            },
            "timeline": {
                "clip_id": None,
                "media_id": None,
                "track_id": "video_1",
            },
        })

    payload = {
        "format": STOCK_MANIFEST_FORMAT,
        "version": 1,
        "source": {"query_plan": Path(query_plan_path).name},
        "ai": {"provider": "CreatorStudio M110.1 visual query plan"},
        "scene_count": len(scenes),
        "scenes": scenes,
    }
    return _atomic_json_write(output_path, payload)


class ProjectStockCache:
    """Index M106 downloaded assets by stable provider/media identity."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self._by_reference: dict[str, MediaAssetRecord] = {}
        for record in scan_media_assets(self.project_root):
            ref = str(record.source_reference or "").strip()
            if ref.startswith(f"{STOCK_SOURCE_PREFIX}:") and record.media_path.is_file():
                self._by_reference.setdefault(ref, record)

    def find(
        self,
        *,
        provider: str,
        media_id: str,
        media_type: str,
        required_duration: float = 0.0,
    ) -> MediaAssetRecord | None:
        if not provider or not media_id:
            return None
        record = self._by_reference.get(stock_source_reference(provider, media_id))
        if record is None or record.media_type != media_type or not record.media_path.is_file():
            return None
        if media_type == "video" and required_duration > 0:
            known_duration = float(record.duration_seconds or 0.0)
            if known_duration <= 0 or known_duration + 0.01 < required_duration:
                return None
        return record

    def remember(self, record: MediaAssetRecord) -> None:
        ref = str(record.source_reference or "").strip()
        if ref:
            self._by_reference[ref] = record


class CachingDownloadAdapter:
    """Reuse M106 assets before falling through to the tested downloader."""

    def __init__(
        self,
        delegate: Any,
        cache: ProjectStockCache,
        required_duration_by_scene: dict[str, float],
    ):
        self.delegate = delegate
        self.cache = cache
        self.required_duration_by_scene = dict(required_duration_by_scene)
        self.cache_hits = 0

    def download(self, media: dict[str, Any], scene_id: str):
        candidate = dict(media or {})
        provider = _provider_name(candidate)
        media_id = _media_id(candidate)
        media_type = str(candidate.get("media_type") or "video").strip().lower()
        if media_type not in {"image", "video"}:
            media_type = "video"
        record = self.cache.find(
            provider=provider,
            media_id=media_id,
            media_type=media_type,
            required_duration=float(self.required_duration_by_scene.get(str(scene_id), 0.0)),
        )
        if record is not None:
            path = record.media_path.resolve()
            self.cache_hits += 1
            return {
                "status": "cached",
                "path": str(path),
                "filename": path.name,
                "size": int(path.stat().st_size),
            }
        return self.delegate.download(media=media, scene_id=scene_id)


def _instantiate_provider(cls: type, api_key: str | None) -> Any | None:
    try:
        return cls()
    except TypeError:
        pass
    try:
        signature = inspect.signature(cls)
    except Exception:
        return None
    required = [
        p
        for p in signature.parameters.values()
        if p.name != "self"
        and p.default is inspect.Parameter.empty
        and p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    ]
    if len(required) != 1 or not api_key:
        return None
    parameter = required[0]
    if parameter.kind is inspect.Parameter.KEYWORD_ONLY:
        try:
            return cls(**{parameter.name: api_key})
        except Exception:
            return None
    try:
        return cls(api_key)
    except Exception:
        try:
            return cls(**{parameter.name: api_key})
        except Exception:
            return None


def _ensure_provider(search_manager: Any, module_name: str, class_name: str, api_key: str | None) -> None:
    providers = list(getattr(search_manager, "providers", []) or [])
    wanted = class_name.replace("Provider", "").lower()
    for provider in providers:
        name = str(getattr(provider, "name", provider.__class__.__name__)).lower()
        if wanted in name:
            return
    if not api_key:
        return
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        provider = _instantiate_provider(cls, api_key)
    except Exception:
        provider = None
    if provider is None:
        return
    providers.append(provider)
    try:
        search_manager.providers = providers
    except Exception:
        return


def _ensure_enabled_stock_providers(batch_pipeline: Any, runtime_environment: dict[str, str]) -> tuple[str, ...]:
    scene_pipeline = getattr(batch_pipeline, "scene_pipeline", None)
    search_manager = getattr(scene_pipeline, "search_manager", None)
    if search_manager is not None:
        _ensure_provider(
            search_manager,
            "stock.pexels",
            "PexelsProvider",
            runtime_environment.get("PEXELS_API_KEY") or os.getenv("PEXELS_API_KEY"),
        )
        _ensure_provider(
            search_manager,
            "stock.pixabay",
            "PixabayProvider",
            runtime_environment.get("PIXABAY_API_KEY") or os.getenv("PIXABAY_API_KEY"),
        )
    names: list[str] = []
    for provider in list(getattr(search_manager, "providers", []) or []):
        label = str(getattr(provider, "name", provider.__class__.__name__)).strip()
        if label and label not in names:
            names.append(label)
    return tuple(names)


def _copy_or_reuse_asset(
    *,
    project_root: Path,
    cache: ProjectStockCache,
    selected: dict[str, Any],
    download: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[MediaAssetRecord, bool]:
    source = Path(str(download.get("path") or "")).expanduser().resolve()
    if not source.is_file():
        raise StockAcquisitionError(f"Downloaded media does not exist: {source}")

    existing_by_path = find_media_asset_by_path(project_root, source)
    if existing_by_path is not None:
        cache.remember(existing_by_path)
        return existing_by_path, True

    provider = _provider_name(selected)
    media_id = _media_id(selected)
    media_type = str(selected.get("media_type") or "video").strip().lower()
    if media_type not in {"image", "video"}:
        media_type = "video"
    reusable = cache.find(
        provider=provider,
        media_id=media_id,
        media_type=media_type,
        required_duration=_to_float(validation.get("duration"), 0.0),
    )
    if reusable is not None:
        return reusable, True

    extension = source.suffix.lower() or (".mp4" if media_type == "video" else ".jpg")
    source_ref = stock_source_reference(provider, media_id) if provider and media_id else None
    display_name = f"{provider}_{media_id}" if media_id else source.stem
    target_record = new_media_asset_target(
        project_root,
        media_type=media_type,
        origin="downloaded",
        extension=extension,
        display_name=display_name,
        provider_id=provider or None,
        source_reference=source_ref,
    )
    shutil.copy2(source, target_record.media_path)
    finalized = finalize_media_asset(
        target_record,
        mime_type=str(validation.get("mime_type") or "") or None,
        width=int(validation.get("width")) if validation.get("width") not in (None, "") else None,
        height=int(validation.get("height")) if validation.get("height") not in (None, "") else None,
        duration_seconds=_to_float(validation.get("duration"), 0.0) or None,
    )
    cache.remember(finalized)
    return finalized, False


class StockAcquisitionService:
    """M110.2 adapter around the existing tested stock pipeline.

    Responsibilities added by Creator Studio:
      * convert M110.1 query plans to the legacy stock-manifest contract;
      * ensure configured Pexels/Pixabay providers participate when available;
      * reuse M106 project assets through a stable provider/media cache;
      * reuse the legacy duration filter, ranking, download and validation code;
      * promote validated downloads to the M106 asset library;
      * create M107 scene assignments automatically.
    """

    def __init__(
        self,
        *,
        project_root: Path,
        run_dir: Path,
        query_plan_path: Path,
        source_scenes_path: Path,
        voice_asset_id: str,
        runtime_environment: dict[str, str] | None = None,
        progress_callback: Callable[[int, int, str, str], None] | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.query_plan_path = Path(query_plan_path).resolve()
        self.source_scenes_path = Path(source_scenes_path).resolve()
        self.voice_asset_id = str(voice_asset_id or "").strip()
        self.runtime_environment = dict(runtime_environment or {})
        self.progress_callback = progress_callback

    def run(self) -> StockAcquisitionReport:
        if not self.query_plan_path.is_file():
            raise FileNotFoundError(self.query_plan_path)
        if not self.source_scenes_path.is_file():
            raise FileNotFoundError(self.source_scenes_path)
        if not self.voice_asset_id:
            raise StockAcquisitionError("Thiếu Voice Asset ID để gán tư liệu tự động.")
        if not (
            self.runtime_environment.get("PEXELS_API_KEY")
            or self.runtime_environment.get("PIXABAY_API_KEY")
            or os.getenv("PEXELS_API_KEY")
            or os.getenv("PIXABAY_API_KEY")
        ):
            raise StockAcquisitionError(
                "Chưa có PEXELS_API_KEY hoặc PIXABAY_API_KEY. Hãy cấu hình ít nhất một nguồn stock."
            )

        self.run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = build_stock_manifest(
            self.query_plan_path,
            self.run_dir / STOCK_MANIFEST_FILENAME,
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        search_scenes = list(manifest.get("scenes") or [])
        total = len(search_scenes)
        if total == 0:
            return StockAcquisitionReport(
                total_search_scenes=0,
                validated_count=0,
                assigned_count=0,
                unresolved_count=0,
                cache_hit_count=0,
                new_asset_count=0,
                reused_asset_count=0,
                provider_names=(),
                manifest_path=str(manifest_path),
            )

        download_dir = self.run_dir / STOCK_DOWNLOAD_DIRNAME
        download_dir.mkdir(parents=True, exist_ok=True)
        required = {
            str(scene.get("scene_id")): _to_float(scene.get("duration"), 0.0)
            for scene in search_scenes
        }

        with _temporary_environment(self.runtime_environment):
            from pipeline.batch_pipeline import BatchPipeline

            batch = BatchPipeline(
                manifest_path=manifest_path,
                download_dir=download_dir,
                review_mode="auto",
                resume=True,
                per_query=5,
                max_candidates=20,
                visual_top_n=5,
            )
            provider_names = _ensure_enabled_stock_providers(batch, self.runtime_environment)
            scene_pipeline = getattr(batch, "scene_pipeline", None)
            if scene_pipeline is None:
                raise StockAcquisitionError("BatchPipeline không cung cấp scene_pipeline.")

            cache = ProjectStockCache(self.project_root)
            downloader = getattr(scene_pipeline, "downloader", None)
            if downloader is None:
                raise StockAcquisitionError("ScenePipeline không cung cấp downloader.")
            caching_downloader = CachingDownloadAdapter(downloader, cache, required)
            scene_pipeline.downloader = caching_downloader

            original_run = scene_pipeline.run
            counter = {"value": 0}

            def wrapped_run(scene):
                index = counter["value"] + 1
                scene_id = str(scene.get("scene_id") or f"scene_{index:03d}")
                if self.progress_callback is not None:
                    self.progress_callback(index, total, scene_id, "searching")
                result = original_run(scene)
                counter["value"] = index
                status = str((result or {}).get("status") or "done") if isinstance(result, dict) else "done"
                if self.progress_callback is not None:
                    self.progress_callback(index, total, scene_id, status)
                return result

            scene_pipeline.run = wrapped_run
            batch.run()

        final_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validated_count = 0
        assigned_count = 0
        new_asset_count = 0
        reused_asset_count = 0

        for raw_scene in final_manifest.get("scenes") or []:
            if not isinstance(raw_scene, dict):
                continue
            stock = raw_scene.get("stock") if isinstance(raw_scene.get("stock"), dict) else {}
            if stock.get("status") != "validated":
                continue
            selected = stock.get("selected_media") if isinstance(stock.get("selected_media"), dict) else {}
            download = stock.get("download") if isinstance(stock.get("download"), dict) else {}
            validation = stock.get("validation") if isinstance(stock.get("validation"), dict) else {}
            scene_id = str(raw_scene.get("scene_id") or "").strip()
            if not scene_id:
                continue
            validated_count += 1
            asset, reused = _copy_or_reuse_asset(
                project_root=self.project_root,
                cache=cache,
                selected=selected,
                download=download,
                validation=validation,
            )
            if reused:
                reused_asset_count += 1
            else:
                new_asset_count += 1
            assign_media_asset(
                self.project_root,
                self.voice_asset_id,
                self.source_scenes_path,
                scene_id,
                asset.asset_id,
            )
            assigned_count += 1

        unresolved = max(0, total - assigned_count)
        return StockAcquisitionReport(
            total_search_scenes=total,
            validated_count=validated_count,
            assigned_count=assigned_count,
            unresolved_count=unresolved,
            cache_hit_count=caching_downloader.cache_hits,
            new_asset_count=new_asset_count,
            reused_asset_count=reused_asset_count,
            provider_names=provider_names,
            manifest_path=str(manifest_path),
        )
