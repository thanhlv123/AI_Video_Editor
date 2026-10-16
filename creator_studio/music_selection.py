from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import uuid
import wave
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from creator_studio.scene_assets import load_voice_scenes


MUSIC_SELECTION_FORMAT = "creator_studio_music_selection_m112"
MUSIC_SELECTION_FILENAME = "music_selection_manifest.json"
MUSIC_ASSET_FORMAT = "creator_studio_music_asset_m112"
MUSIC_ASSET_META_SUFFIX = ".music.json"
SUPPORTED_MUSIC_SUFFIXES = frozenset({".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"})


class MusicSelectionError(RuntimeError):
    """Controlled M112 background-music selection failure."""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _safe_slug(value: str, fallback: str = "music", max_len: int = 72) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_text).strip("._-")
    return (slug or fallback)[:max_len]


def music_assets_root(project_root: Path) -> Path:
    path = Path(project_root).resolve() / "assets" / "music"
    path.mkdir(parents=True, exist_ok=True)
    return path


def music_origin_root(project_root: Path, origin: str) -> Path:
    value = str(origin or "").strip().lower()
    if value not in {"imported", "generated", "downloaded"}:
        raise MusicSelectionError(f"Nguồn music asset không hợp lệ: {origin}")
    path = music_assets_root(project_root) / value
    path.mkdir(parents=True, exist_ok=True)
    return path


def _metadata_path(audio_path: Path) -> Path:
    audio_path = Path(audio_path)
    return audio_path.with_name(audio_path.name + MUSIC_ASSET_META_SUFFIX)


def _unique_path(folder: Path, base_name: str, suffix: str) -> Path:
    suffix = suffix.lower()
    if not suffix.startswith("."):
        suffix = "." + suffix
    candidate = folder / f"{base_name}{suffix}"
    index = 2
    while candidate.exists() or _metadata_path(candidate).exists():
        candidate = folder / f"{base_name}_{index:02d}{suffix}"
        index += 1
    return candidate


def _normalize_tokens(values: Any) -> tuple[str, ...]:
    import re

    if values is None:
        return ()
    if isinstance(values, str):
        items = [values]
    elif isinstance(values, (list, tuple, set)):
        items = [str(item) for item in values]
    else:
        items = [str(values)]
    tokens: list[str] = []
    seen: set[str] = set()
    for item in items:
        for token in re.findall(r"[A-Za-z0-9]+", item.lower()):
            if token and token not in seen:
                seen.add(token)
                tokens.append(token)
    return tuple(tokens)


@dataclass(frozen=True)
class MusicAssetRecord:
    asset_id: str
    display_name: str
    origin: str
    path: str
    created_at: str
    duration_seconds: float | None = None
    mood: str | None = None
    genre: str | None = None
    energy: str | None = None
    tags: tuple[str, ...] = ()
    source_reference: str | None = None
    size_bytes: int | None = None

    @property
    def audio_path(self) -> Path:
        return Path(self.path)

    @property
    def metadata_path(self) -> Path:
        return _metadata_path(self.audio_path)


def _write_music_record(record: MusicAssetRecord) -> None:
    path = record.metadata_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"format": MUSIC_ASSET_FORMAT, **asdict(record), "tags": list(record.tags)}
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def import_music_asset(
    project_root: Path,
    source_path: Path,
    *,
    display_name: str | None = None,
    mood: str | None = None,
    genre: str | None = None,
    energy: str | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
) -> MusicAssetRecord:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() not in SUPPORTED_MUSIC_SUFFIXES:
        raise MusicSelectionError(f"Định dạng nhạc chưa được hỗ trợ: {source.suffix}")

    folder = music_origin_root(project_root, "imported")
    asset_id = f"music_{uuid.uuid4().hex[:12]}"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    label = _safe_slug(display_name or source.stem, "music", 52)
    target = _unique_path(folder, f"{stamp}_{label}_{asset_id[-6:]}", source.suffix)
    shutil.copy2(source, target)
    record = MusicAssetRecord(
        asset_id=asset_id,
        display_name=display_name or source.stem,
        origin="imported",
        path=str(target.resolve()),
        created_at=_now_iso(),
        mood=str(mood).strip().lower() or None if mood is not None else None,
        genre=str(genre).strip().lower() or None if genre is not None else None,
        energy=str(energy).strip().lower() or None if energy is not None else None,
        tags=_normalize_tokens(tags),
        source_reference=str(source),
        size_bytes=int(target.stat().st_size),
    )
    _write_music_record(record)
    return record


def _read_music_metadata(path: Path) -> MusicAssetRecord:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MusicSelectionError(f"Metadata nhạc không hợp lệ: {path}")
    required = ("asset_id", "display_name", "origin", "path", "created_at")
    if any(not payload.get(key) for key in required):
        raise MusicSelectionError(f"Metadata nhạc thiếu trường bắt buộc: {path}")
    return MusicAssetRecord(
        asset_id=str(payload["asset_id"]),
        display_name=str(payload["display_name"]),
        origin=str(payload["origin"]),
        path=str(payload["path"]),
        created_at=str(payload["created_at"]),
        duration_seconds=float(payload["duration_seconds"]) if payload.get("duration_seconds") is not None else None,
        mood=str(payload.get("mood") or "").strip().lower() or None,
        genre=str(payload.get("genre") or "").strip().lower() or None,
        energy=str(payload.get("energy") or "").strip().lower() or None,
        tags=_normalize_tokens(payload.get("tags")),
        source_reference=str(payload.get("source_reference") or "") or None,
        size_bytes=int(payload["size_bytes"]) if payload.get("size_bytes") is not None else None,
    )


def scan_music_assets(project_root: Path) -> list[MusicAssetRecord]:
    root = music_assets_root(project_root)
    for origin in ("imported", "generated", "downloaded"):
        music_origin_root(project_root, origin)

    records: list[MusicAssetRecord] = []
    known: set[Path] = set()
    for metadata_path in sorted(root.rglob(f"*{MUSIC_ASSET_META_SUFFIX}")):
        try:
            record = _read_music_metadata(metadata_path)
            audio_path = record.audio_path.resolve()
            if not audio_path.is_file() or audio_path.suffix.lower() not in SUPPORTED_MUSIC_SUFFIXES:
                continue
            known.add(audio_path)
            if record.size_bytes != audio_path.stat().st_size:
                record = MusicAssetRecord(**{**asdict(record), "size_bytes": int(audio_path.stat().st_size)})
            records.append(record)
        except Exception:
            continue

    for audio_path in sorted(root.rglob("*")):
        if not audio_path.is_file() or audio_path.suffix.lower() not in SUPPORTED_MUSIC_SUFFIXES:
            continue
        resolved = audio_path.resolve()
        if resolved in known:
            continue
        origin = "imported"
        try:
            rel = resolved.relative_to(root)
            if rel.parts and rel.parts[0].lower() in {"imported", "generated", "downloaded"}:
                origin = rel.parts[0].lower()
        except Exception:
            pass
        stat = audio_path.stat()
        records.append(
            MusicAssetRecord(
                asset_id=f"orphan_{uuid.uuid5(uuid.NAMESPACE_URL, str(resolved)).hex[:12]}",
                display_name=audio_path.stem,
                origin=origin,
                path=str(resolved),
                created_at=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                tags=_normalize_tokens(audio_path.stem),
                size_bytes=int(stat.st_size),
            )
        )

    records.sort(key=lambda item: (item.created_at, item.display_name.lower()), reverse=True)
    return records


def probe_audio_duration(path: Path, *, ffprobe: str = "ffprobe", timeout: float = 20.0) -> float | None:
    audio_path = Path(path).resolve()
    if not audio_path.is_file() or audio_path.stat().st_size <= 0:
        return None

    if audio_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(audio_path), "rb") as handle:
                frames = int(handle.getnframes())
                rate = int(handle.getframerate())
                if frames > 0 and rate > 0:
                    return frames / rate
        except Exception:
            pass

    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(1.0, float(timeout)),
            check=False,
        )
        if completed.returncode != 0:
            return None
        value = float((completed.stdout or "").strip())
        return value if math.isfinite(value) and value > 0 else None
    except Exception:
        return None


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


def _relative_project_path(project_root: Path, path: Path) -> str:
    root = Path(project_root).resolve()
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except Exception as exc:
        raise MusicSelectionError(f"Music asset phải nằm trong project: {resolved}") from exc


def _scene_text(scene: dict[str, Any]) -> str:
    for key in ("text", "dialogue", "dialogue_en", "content", "voice"):
        value = str(scene.get(key) or "").strip()
        if value:
            return value
    return ""


def _project_duration(scenes: list[dict[str, Any]]) -> float:
    result = 0.0
    for scene in scenes:
        try:
            end = float(scene.get("end") or 0.0)
            if end <= 0:
                start = float(scene.get("start") or 0.0)
                end = start + float(scene.get("duration") or 0.0)
            result = max(result, end)
        except Exception:
            continue
    return max(0.0, result)


def infer_music_intent(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join(_scene_text(scene) for scene in scenes).lower()
    groups = [
        ("tense", "medium", {"danger", "fear", "war", "crime", "horror", "dark", "threat", "murder", "disaster"}),
        ("uplifting", "medium", {"travel", "festival", "celebrate", "success", "happy", "joy", "food", "nightlife", "adventure"}),
        ("warm", "low", {"love", "family", "romance", "wedding", "home", "together", "child", "grandmother", "grandfather"}),
        ("reflective", "low", {"history", "old", "elderly", "leaving", "goodbye", "population", "emigration", "memory", "lonely", "economic"}),
        ("calm", "low", {"nature", "river", "village", "rural", "peaceful", "slow", "quiet", "relax"}),
    ]
    scores: list[tuple[int, int, str, str, set[str]]] = []
    for order, (mood, energy, terms) in enumerate(groups):
        score = sum(text.count(term) for term in terms)
        scores.append((score, -order, mood, energy, terms))
    scores.sort(reverse=True)
    score, _, mood, energy, terms = scores[0]
    if score <= 0:
        mood = "neutral"
        energy = "low"
        terms = {"ambient", "cinematic", "instrumental"}
    keyword_hits = [term for term in sorted(terms) if term in text][:8]
    return {
        "mood": mood,
        "energy": energy,
        "keywords": keyword_hits,
        "voice_priority": True,
    }


def _candidate_tokens(record: MusicAssetRecord) -> set[str]:
    values = [record.display_name, record.mood or "", record.genre or "", record.energy or "", *record.tags]
    return set(_normalize_tokens(values))


def _candidate_score(record: MusicAssetRecord, intent: dict[str, Any], duration: float | None) -> float:
    tokens = _candidate_tokens(record)
    score = 0.25
    mood = str(intent.get("mood") or "neutral").lower()
    energy = str(intent.get("energy") or "low").lower()
    keywords = {str(item).lower() for item in intent.get("keywords") or []}

    mood_aliases = {
        "reflective": {"reflective", "documentary", "cinematic", "piano", "emotional", "sad", "memory"},
        "warm": {"warm", "romantic", "love", "acoustic", "gentle", "family"},
        "uplifting": {"uplifting", "happy", "positive", "travel", "upbeat", "inspiring"},
        "tense": {"tense", "dark", "suspense", "dramatic", "thriller"},
        "calm": {"calm", "ambient", "relax", "peaceful", "soft", "nature"},
        "neutral": {"ambient", "cinematic", "instrumental", "background"},
    }
    if record.mood and record.mood.lower() == mood:
        score += 0.34
    elif tokens & mood_aliases.get(mood, set()):
        score += 0.24

    if record.energy and record.energy.lower() == energy:
        score += 0.18
    elif energy in tokens:
        score += 0.12

    overlap = tokens & keywords
    score += min(0.16, 0.04 * len(overlap))
    if tokens & {"instrumental", "ambient", "cinematic", "background", "piano", "acoustic"}:
        score += 0.08
    if duration is not None and duration >= 10.0:
        score += 0.05
    return max(0.0, min(1.0, round(score, 6)))


@dataclass(frozen=True)
class MusicSelectionReport:
    status: str
    candidate_count: int
    eligible_count: int
    selected_asset_id: str
    selected_duration_seconds: float
    project_duration_seconds: float
    loop_required: bool
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BackgroundMusicSelectionService:
    """Select one project-local background track and emit a render-neutral mix plan.

    M112 does not alter narration audio and does not render/mix audio.  It only
    chooses a project-owned music asset and records the parameters that M113/M114
    can later apply with FFmpeg.  If no usable music exists, the stage is skipped
    rather than failing the video workflow.
    """

    def __init__(
        self,
        *,
        project_root: Path,
        run_dir: Path,
        source_scenes_path: Path,
        final_renderable_manifest_path: Path,
        enabled: bool = True,
        duration_probe: Callable[[Path], float | None] | None = None,
        progress_callback: Callable[[int, int, str, float], None] | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.source_scenes_path = Path(source_scenes_path).resolve()
        self.final_renderable_manifest_path = Path(final_renderable_manifest_path).resolve()
        self.enabled = bool(enabled)
        self.duration_probe = duration_probe or (lambda path: probe_audio_duration(path))
        self.progress_callback = progress_callback

    @property
    def output_path(self) -> Path:
        return self.run_dir / MUSIC_SELECTION_FILENAME

    def _write_skipped(self, *, status: str, scenes: list[dict[str, Any]], candidates: list[MusicAssetRecord]) -> MusicSelectionReport:
        duration = _project_duration(scenes)
        payload = {
            "format": MUSIC_SELECTION_FORMAT,
            "created_at": _now_iso(),
            "status": status,
            "project_duration_seconds": duration,
            "intent": infer_music_intent(scenes),
            "summary": {
                "candidate_count": len(candidates),
                "eligible_count": 0,
                "selected_count": 0,
            },
            "selected": None,
            "mix": {
                "voice_is_primary": True,
                "music_gain_db": -22.0,
                "fade_in_seconds": 1.5,
                "fade_out_seconds": 2.0,
                "ducking_enabled": True,
                "ducking_reduction_db": 6.0,
                "start_seconds": 0.0,
                "target_duration_seconds": duration,
                "loop_required": False,
            },
            "policy": {
                "local_project_assets_only": True,
                "network_search": False,
                "narration_audio_modified": False,
                "no_music_is_nonfatal": True,
            },
            "candidates": [],
        }
        _atomic_json_write(self.output_path, payload)
        return MusicSelectionReport(
            status=status,
            candidate_count=len(candidates),
            eligible_count=0,
            selected_asset_id="",
            selected_duration_seconds=0.0,
            project_duration_seconds=duration,
            loop_required=False,
            manifest_path=str(self.output_path),
        )

    def run(self) -> MusicSelectionReport:
        if not self.source_scenes_path.is_file():
            raise FileNotFoundError(self.source_scenes_path)
        if not self.final_renderable_manifest_path.is_file():
            raise FileNotFoundError(self.final_renderable_manifest_path)

        final_payload = json.loads(self.final_renderable_manifest_path.read_text(encoding="utf-8"))
        summary = final_payload.get("summary") if isinstance(final_payload, dict) else None
        if not isinstance(summary, dict) or int(summary.get("unresolved_count") or 0) != 0:
            raise MusicSelectionError("M112 chỉ chạy khi toàn bộ scene đã có final renderable asset.")

        scenes = load_voice_scenes(self.source_scenes_path)
        candidates = scan_music_assets(self.project_root)
        if not self.enabled:
            return self._write_skipped(status="skipped_disabled", scenes=scenes, candidates=candidates)
        if not candidates:
            return self._write_skipped(status="skipped_no_music", scenes=scenes, candidates=candidates)

        intent = infer_music_intent(scenes)
        project_duration = _project_duration(scenes)
        ranked: list[dict[str, Any]] = []
        total = len(candidates)
        for index, record in enumerate(candidates, start=1):
            path = record.audio_path.resolve()
            issues: list[str] = []
            if not path.is_file() or path.stat().st_size <= 0:
                issues.append("missing_or_empty_file")
                duration = None
            else:
                duration = record.duration_seconds
                if duration is None or duration <= 0:
                    duration = self.duration_probe(path)
                if duration is None or not math.isfinite(float(duration)) or float(duration) <= 0:
                    issues.append("duration_unavailable")
                    duration = None
            score = _candidate_score(record, intent, duration)
            eligible = not issues
            ranked.append(
                {
                    "asset_id": record.asset_id,
                    "display_name": record.display_name,
                    "origin": record.origin,
                    "path": _relative_project_path(self.project_root, path),
                    "duration_seconds": round(float(duration), 6) if duration is not None else None,
                    "mood": record.mood,
                    "genre": record.genre,
                    "energy": record.energy,
                    "tags": list(record.tags),
                    "score": score,
                    "eligible": eligible,
                    "issues": issues,
                }
            )
            if self.progress_callback is not None:
                self.progress_callback(index, total, record.asset_id, score)

        eligible = [item for item in ranked if item["eligible"]]
        eligible.sort(key=lambda item: (-float(item["score"]), str(item["display_name"]).lower(), str(item["asset_id"])))
        if not eligible:
            duration = _project_duration(scenes)
            payload = {
                "format": MUSIC_SELECTION_FORMAT,
                "created_at": _now_iso(),
                "status": "skipped_no_valid_music",
                "project_duration_seconds": duration,
                "intent": intent,
                "summary": {"candidate_count": len(ranked), "eligible_count": 0, "selected_count": 0},
                "selected": None,
                "mix": {
                    "voice_is_primary": True,
                    "music_gain_db": -22.0,
                    "fade_in_seconds": 1.5,
                    "fade_out_seconds": 2.0,
                    "ducking_enabled": True,
                    "ducking_reduction_db": 6.0,
                    "start_seconds": 0.0,
                    "target_duration_seconds": duration,
                    "loop_required": False,
                },
                "policy": {
                    "local_project_assets_only": True,
                    "network_search": False,
                    "narration_audio_modified": False,
                    "no_music_is_nonfatal": True,
                },
                "candidates": ranked,
            }
            _atomic_json_write(self.output_path, payload)
            return MusicSelectionReport(
                status="skipped_no_valid_music",
                candidate_count=len(ranked),
                eligible_count=0,
                selected_asset_id="",
                selected_duration_seconds=0.0,
                project_duration_seconds=duration,
                loop_required=False,
                manifest_path=str(self.output_path),
            )

        selected = eligible[0]
        music_duration = float(selected["duration_seconds"] or 0.0)
        loop_required = project_duration > 0 and music_duration + 0.05 < project_duration
        gain_by_energy = {"low": -24.0, "medium": -22.0, "high": -20.0}
        music_gain = gain_by_energy.get(str(intent.get("energy") or "low"), -22.0)
        fade_out = min(2.0, max(0.0, project_duration / 3.0)) if project_duration else 2.0

        payload = {
            "format": MUSIC_SELECTION_FORMAT,
            "created_at": _now_iso(),
            "status": "selected",
            "project_duration_seconds": round(project_duration, 6),
            "intent": intent,
            "summary": {
                "candidate_count": len(ranked),
                "eligible_count": len(eligible),
                "selected_count": 1,
            },
            "selected": selected,
            "mix": {
                "voice_is_primary": True,
                "music_gain_db": music_gain,
                "fade_in_seconds": 1.5,
                "fade_out_seconds": round(fade_out, 3),
                "ducking_enabled": True,
                "ducking_reduction_db": 6.0,
                "start_seconds": 0.0,
                "target_duration_seconds": round(project_duration, 6),
                "loop_required": loop_required,
                "trim_to_target": music_duration > project_duration > 0,
            },
            "policy": {
                "local_project_assets_only": True,
                "network_search": False,
                "narration_audio_modified": False,
                "no_music_is_nonfatal": True,
            },
            "candidates": ranked,
        }
        _atomic_json_write(self.output_path, payload)
        return MusicSelectionReport(
            status="selected",
            candidate_count=len(ranked),
            eligible_count=len(eligible),
            selected_asset_id=str(selected["asset_id"]),
            selected_duration_seconds=music_duration,
            project_duration_seconds=project_duration,
            loop_required=loop_required,
            manifest_path=str(self.output_path),
        )
