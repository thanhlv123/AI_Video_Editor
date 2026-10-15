from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Sequence

QUERY_PLAN_FORMAT = "creator_studio_visual_query_plan_m110_1_2"
QUERY_PLAN_FILENAME = "visual_query_plan.json"
QUERY_CACHE_FORMAT = "creator_studio_visual_query_cache_m110_1_2"
QUERY_CACHE_VERSION = "m110_1_2_batch_context_v1"
DEFAULT_BATCH_SIZE = 8


@dataclass(frozen=True)
class SceneQueryPlan:
    scene_id: str
    scene_type: str
    start: float
    end: float
    duration: float
    dialogue_sha256: str
    primary_query: str
    queries: tuple[str, ...]
    avoid: tuple[str, ...]
    preferred_type: str
    planner_source: str
    strategy: str = "search"
    context: str = ""
    subject: str = ""
    action: str = ""
    location: str = ""
    mood: str = ""
    shot: str = "any"
    motion: str = "any"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["queries"] = list(self.queries)
        data["avoid"] = list(self.avoid)
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SceneQueryPlan":
        return cls(
            scene_id=str(raw.get("scene_id") or ""),
            scene_type=str(raw.get("scene_type") or "speech"),
            start=_to_float(raw.get("start"), 0.0),
            end=_to_float(raw.get("end"), 0.0),
            duration=max(0.0, _to_float(raw.get("duration"), 0.0)),
            dialogue_sha256=str(raw.get("dialogue_sha256") or ""),
            primary_query=_clean_phrase(raw.get("primary_query")),
            queries=_dedupe_phrases(raw.get("queries") or [], limit=6),
            avoid=_dedupe_phrases(raw.get("avoid") or [], limit=8),
            preferred_type=_normal_preferred_type(raw.get("preferred_type")),
            planner_source=str(raw.get("planner_source") or "unknown"),
            strategy=str(raw.get("strategy") or "search"),
            context=_clean_phrase(raw.get("context")),
            subject=_clean_phrase(raw.get("subject")),
            action=_clean_phrase(raw.get("action")),
            location=_clean_phrase(raw.get("location")),
            mood=_clean_phrase(raw.get("mood")),
            shot=_clean_phrase(raw.get("shot")) or "any",
            motion=_clean_phrase(raw.get("motion")) or "any",
        )


@dataclass(frozen=True)
class QueryPlanningReport:
    plans: tuple[SceneQueryPlan, ...]
    ai_count: int
    cache_hit_count: int
    fallback_count: int
    reused_gap_count: int
    batch_request_count: int


_EN_STOP = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "to", "of", "in", "on",
    "at", "for", "from", "with", "without", "into", "onto", "is", "are", "was", "were", "be",
    "been", "being", "it", "its", "this", "that", "these", "those", "there", "their", "they",
    "them", "he", "she", "his", "her", "we", "our", "you", "your", "i", "my", "as", "by",
    "so", "not", "no", "do", "does", "did", "have", "has", "had", "can", "could", "will",
    "would", "should", "may", "might", "very", "more", "most", "much", "many", "some", "any",
}
_VI_STOP = {
    "và", "là", "của", "có", "cho", "trong", "một", "những", "các", "đã", "đang", "sẽ", "với",
    "từ", "đến", "khi", "mà", "này", "đó", "thì", "nhưng", "không", "cũng", "được", "về", "ra",
    "vào", "ở", "trên", "dưới", "như", "họ", "nó", "anh", "cô", "ông", "bà", "tôi", "chúng",
    "ta", "mình", "bạn", "rất", "hơn", "nhiều", "ít", "mỗi", "lại", "vẫn", "chỉ", "để", "nên",
}


BATCH_SYSTEM_PROMPT = """
You are a video scene analysis engine for automated media discovery.
Analyze several adjacent narration scenes together so that each scene keeps its
own meaning while using neighboring scenes only to resolve context.

For every requested scene, return concrete visual search guidance suitable for
stock-video sites and YouTube reference discovery.

Do not invent unsupported people, places, landmarks, events, dates, brands, or
facts. Prefer search phrases that describe visible subjects, actions, locations,
and environments. Preserve explicit geography when the narration supports it.
""".strip()


def _dialogue_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _stable_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get(raw: Any, *names: str, default: Any = None) -> Any:
    if isinstance(raw, dict):
        for name in names:
            if name in raw:
                return raw.get(name)
        return default
    for name in names:
        if hasattr(raw, name):
            return getattr(raw, name)
    return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clean_phrase(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n,.;:-")


def _dedupe_phrases(values: Iterable[Any], *, limit: int = 6) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        phrase = _clean_phrase(value)
        key = phrase.casefold()
        if not phrase or key in seen:
            continue
        seen.add(key)
        result.append(phrase)
        if len(result) >= limit:
            break
    return tuple(result)


def _normal_preferred_type(value: Any) -> str:
    preferred = str(value or "video").casefold()
    if preferred not in {"video", "image", "either"}:
        return "video"
    return preferred


def _extract_tokens(text: str, *, language: str = "und") -> list[str]:
    words = re.findall(r"[^\W_]+(?:['’-][^\W_]+)?", str(text or ""), flags=re.UNICODE)
    stop = _EN_STOP | _VI_STOP
    result: list[str] = []
    seen: set[str] = set()
    for word in words:
        token = word.strip("'’- ")
        key = token.casefold()
        if len(key) < 2 or key in stop or key in seen or key.isdigit():
            continue
        seen.add(key)
        result.append(token)
    return result


def _fallback_queries(text: str, *, language: str = "und") -> tuple[str, tuple[str, ...]]:
    tokens = _extract_tokens(text, language=language)
    if not tokens:
        return "cinematic documentary scene", ("cinematic documentary scene",)
    primary = " ".join(tokens[:6])
    phrases: list[str] = [primary]
    if len(tokens) >= 4:
        phrases.append(" ".join(tokens[:4]))
    if len(tokens) >= 7:
        phrases.append(" ".join(tokens[3:8]))
    if len(tokens) >= 10:
        phrases.append(" ".join(tokens[7:12]))
    if len(tokens) >= 2:
        phrases.append(" ".join(tokens[:2] + ["documentary", "footage"]))
    return primary, _dedupe_phrases(phrases, limit=5)


@contextmanager
def _temporary_environment(values: dict[str, str] | None):
    values = {str(k): str(v) for k, v in (values or {}).items() if v not in (None, "")}
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


def _strip_json_fence(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


class SceneQueryCache:
    """Small project-local cache for successful AI scene-intelligence results.

    Cache identity includes previous/current/next dialogue hashes so a scene is
    not reused when its surrounding context changes.
    """

    def __init__(self, root: Path | None):
        self.root = Path(root).resolve() if root is not None else None
        if self.root is not None:
            self.root.mkdir(parents=True, exist_ok=True)

    def key_for(
        self,
        *,
        language: str,
        scene_type: str,
        previous_hash: str,
        dialogue_hash: str,
        next_hash: str,
    ) -> str:
        return _stable_sha256({
            "version": QUERY_CACHE_VERSION,
            "language": str(language or "und"),
            "scene_type": str(scene_type or "speech"),
            "previous": previous_hash,
            "current": dialogue_hash,
            "next": next_hash,
        })

    def _path(self, key: str) -> Path | None:
        if self.root is None:
            return None
        return self.root / f"{key}.json"

    def load(self, key: str) -> SceneQueryPlan | None:
        path = self._path(key)
        if path is None or not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("format") != QUERY_CACHE_FORMAT or payload.get("cache_key") != key:
                return None
            raw_plan = payload.get("plan")
            if not isinstance(raw_plan, dict):
                return None
            plan = SceneQueryPlan.from_dict(raw_plan)
            if plan.planner_source not in {"kie_batch_scene_ai", "kie_scene_ai"}:
                return None
            if not plan.scene_id or not plan.primary_query or not plan.queries:
                return None
            return plan
        except Exception:
            return None

    def save(self, key: str, plan: SceneQueryPlan) -> None:
        path = self._path(key)
        if path is None:
            return
        payload = {
            "format": QUERY_CACHE_FORMAT,
            "cache_key": key,
            "plan": plan.to_dict(),
        }
        _atomic_json_write(path, payload)


class KieBatchSceneAnalyzer:
    """Batch adapter around the existing KieAIProvider request transport.

    It deliberately reuses KieAIProvider's retry/backoff, response extraction,
    model, and credential behavior.  One request analyzes up to batch_size scenes.
    """

    def __init__(
        self,
        *,
        runtime_environment: dict[str, str] | None = None,
        model: str = "gpt-6-luna",
        reasoning_effort: str = "low",
    ):
        self.runtime_environment = dict(runtime_environment or {})
        with _temporary_environment(self.runtime_environment):
            from ai.providers.kie_provider import KieAIProvider
            self.provider = KieAIProvider(model=model, reasoning_effort=reasoning_effort)

    def analyze_batch(self, scenes: Sequence[SimpleNamespace]) -> dict[str, dict[str, Any]]:
        if not scenes:
            return {}

        scene_rows = []
        for scene in scenes:
            scene_rows.append({
                "scene_id": scene.id,
                "start": round(float(scene.start), 3),
                "end": round(float(scene.end), 3),
                "duration": round(float(scene.duration), 3),
                "narration": scene.text,
            })

        user_prompt = f"""
Analyze these adjacent narration scenes for automated visual-media discovery.

INPUT SCENES:
{json.dumps(scene_rows, ensure_ascii=False, indent=2)}

Return ONLY valid JSON with this exact outer shape:
{{
  "scenes": [
    {{
      "scene_id": "scene_001",
      "context": "string",
      "subject": "string",
      "action": "string",
      "location": "string",
      "mood": "string",
      "shot": "wide | medium | close_up | aerial | detail | any",
      "motion": "static | slow | normal | fast | any",
      "primary_keyword": "2-6 concrete search words",
      "keywords": ["3-6 concrete search phrases"],
      "avoid": ["unsupported or misleading concepts"],
      "preferred_type": "video | image | either"
    }}
  ]
}}

RULES:
1. Return exactly one result for each input scene_id and preserve scene_id exactly.
2. Think visually; do not merely repeat narration.
3. Queries will be used for Pexels, Pixabay, and YouTube reference discovery.
4. Use neighboring scenes only to resolve context; do not merge scenes together.
5. Preserve explicit geography, people, objects, and events only when supported.
6. Prefer video unless an image clearly works better.
7. No Markdown and no commentary outside the JSON object.
""".strip()

        payload = {
            "model": self.provider.model,
            "stream": False,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": BATCH_SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            "reasoning": {"effort": self.provider.reasoning_effort},
        }

        with _temporary_environment(self.runtime_environment):
            response_data = self.provider._send_request(payload)
            output_text = self.provider._extract_output_text(response_data)

        if not output_text:
            raise RuntimeError("KIE batch returned no output text.")

        parsed = json.loads(_strip_json_fence(output_text))
        rows = parsed.get("scenes") if isinstance(parsed, dict) else None
        if not isinstance(rows, list):
            raise ValueError("KIE batch response must contain a scenes list.")

        requested = {scene.id for scene in scenes}
        result: dict[str, dict[str, Any]] = {}
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            scene_id = str(raw.get("scene_id") or "").strip()
            if scene_id not in requested or scene_id in result:
                continue
            result[scene_id] = raw
        if not result:
            raise ValueError("KIE batch response did not contain any requested scene_id.")
        return result


class VisualQueryPlanner:
    """Turn VoicePipeline scenes into compact, cached, batch-planned queries.

    M110.1.2 avoids one AI request per scene.  Uncached speech scenes are sent in
    groups (default 8).  A failed batch falls back deterministically for that
    batch, so temporary KIE 5xx errors cannot stop the automation pipeline.
    """

    def __init__(
        self,
        *,
        language: str = "und",
        runtime_environment: dict[str, str] | None = None,
        analyzer: Any | None = None,
        batch_analyzer: Any | None = None,
        allow_dynamic_ai: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
        cache_dir: Path | None = None,
    ):
        self.language = str(language or "und")
        self.runtime_environment = dict(runtime_environment or {})
        self.analyzer = analyzer
        self.batch_analyzer = batch_analyzer
        self.allow_dynamic_ai = bool(allow_dynamic_ai)
        self.batch_size = max(1, min(16, int(batch_size or DEFAULT_BATCH_SIZE)))
        self.cache = SceneQueryCache(cache_dir)
        self._dynamic_batch_attempted = False

    def _scene_proxy(self, raw: Any) -> SimpleNamespace:
        scene_id = str(_get(raw, "id", "scene_id", default="") or "").strip()
        start = _to_float(_get(raw, "start", default=0.0))
        end = _to_float(_get(raw, "end", default=start), default=start)
        duration = _to_float(_get(raw, "duration", default=end - start), default=end - start)
        text = str(_get(raw, "text", "dialogue", default="") or "")
        scene_type = str(_get(raw, "scene_type", "type", default="speech") or "speech")
        if not scene_id:
            raise ValueError("Scene is missing id/scene_id.")
        return SimpleNamespace(
            id=scene_id,
            scene_id=scene_id,
            start=start,
            end=end,
            duration=max(0.0, duration),
            text=text,
            dialogue=text,
            scene_type=scene_type,
        )

    def _ensure_batch_analyzer(self) -> Any | None:
        if self.batch_analyzer is not None:
            return self.batch_analyzer
        if self._dynamic_batch_attempted or not self.allow_dynamic_ai:
            return None
        self._dynamic_batch_attempted = True
        env_key = self.runtime_environment.get("KIE_API_KEY") or os.getenv("KIE_API_KEY")
        if not env_key:
            return None
        try:
            self.batch_analyzer = KieBatchSceneAnalyzer(
                runtime_environment=self.runtime_environment,
            )
        except Exception:
            self.batch_analyzer = None
        return self.batch_analyzer

    @staticmethod
    def _payload(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return result
        to_dict = getattr(result, "to_dict", None)
        if callable(to_dict):
            data = to_dict()
            if isinstance(data, dict):
                return data
        return {}

    def _gap_plan(self, scene: SimpleNamespace) -> SceneQueryPlan:
        return SceneQueryPlan(
            scene_id=scene.id,
            scene_type=scene.scene_type,
            start=scene.start,
            end=scene.end,
            duration=scene.duration,
            dialogue_sha256=_dialogue_hash(scene.text),
            primary_query="",
            queries=(),
            avoid=(),
            preferred_type="either",
            planner_source="gap_policy",
            strategy="reuse_previous",
        )

    def _fallback_plan(self, scene: SimpleNamespace) -> SceneQueryPlan:
        primary, queries = _fallback_queries(scene.text, language=self.language)
        return SceneQueryPlan(
            scene_id=scene.id,
            scene_type=scene.scene_type,
            start=scene.start,
            end=scene.end,
            duration=scene.duration,
            dialogue_sha256=_dialogue_hash(scene.text),
            primary_query=primary,
            queries=queries,
            avoid=(),
            preferred_type="video",
            planner_source="deterministic_fallback",
        )

    def _plan_from_ai_payload(
        self,
        scene: SimpleNamespace,
        payload: dict[str, Any],
        *,
        source: str,
    ) -> SceneQueryPlan:
        # Supports both the old SceneAnalysis.to_dict() shape and the new batch row shape.
        search = payload.get("search") if isinstance(payload.get("search"), dict) else payload
        media = payload.get("media") if isinstance(payload.get("media"), dict) else payload
        analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else payload

        primary = _clean_phrase(search.get("primary_keyword"))
        queries = _dedupe_phrases([primary, *(search.get("keywords") or [])], limit=6)
        if not primary or not queries:
            raise ValueError(f"{scene.id}: AI query payload is incomplete.")

        return SceneQueryPlan(
            scene_id=scene.id,
            scene_type=scene.scene_type,
            start=scene.start,
            end=scene.end,
            duration=scene.duration,
            dialogue_sha256=_dialogue_hash(scene.text),
            primary_query=primary,
            queries=queries,
            avoid=_dedupe_phrases(search.get("avoid") or [], limit=8),
            preferred_type=_normal_preferred_type(media.get("preferred_type")),
            planner_source=source,
            context=_clean_phrase(analysis.get("context")),
            subject=_clean_phrase(analysis.get("subject")),
            action=_clean_phrase(analysis.get("action")),
            location=_clean_phrase(analysis.get("location")),
            mood=_clean_phrase(analysis.get("mood")),
            shot=_clean_phrase(analysis.get("shot")) or "any",
            motion=_clean_phrase(analysis.get("motion")) or "any",
        )

    def plan_scene(self, raw: Any) -> SceneQueryPlan:
        """Compatibility single-scene API used by existing tests/manual callers."""
        scene = self._scene_proxy(raw)
        text = scene.text.strip()
        if scene.scene_type.casefold() == "gap" or not text:
            return self._gap_plan(scene)

        if self.analyzer is not None:
            try:
                with _temporary_environment(self.runtime_environment):
                    payload = self._payload(self.analyzer.analyze(scene))
                return self._plan_from_ai_payload(scene, payload, source="kie_scene_ai")
            except Exception:
                pass

        return self._fallback_plan(scene)

    def _cache_identity(self, scenes: Sequence[SimpleNamespace], index: int) -> tuple[str, str]:
        scene = scenes[index]
        current_hash = _dialogue_hash(scene.text)
        previous_hash = _dialogue_hash(scenes[index - 1].text) if index > 0 else ""
        next_hash = _dialogue_hash(scenes[index + 1].text) if index + 1 < len(scenes) else ""
        key = self.cache.key_for(
            language=self.language,
            scene_type=scene.scene_type,
            previous_hash=previous_hash,
            dialogue_hash=current_hash,
            next_hash=next_hash,
        )
        return key, current_hash

    def plan_scenes(
        self,
        raw_scenes: Sequence[Any],
        *,
        progress_callback: Callable[[int, int, SceneQueryPlan], None] | None = None,
        batch_callback: Callable[[int, int, int], None] | None = None,
    ) -> QueryPlanningReport:
        scenes = [self._scene_proxy(raw) for raw in list(raw_scenes or [])]
        total = len(scenes)
        plans: list[SceneQueryPlan | None] = [None] * total
        cache_keys: dict[int, str] = {}
        cache_hits = 0
        reused_gaps = 0

        missing_indices: list[int] = []
        for index, scene in enumerate(scenes):
            if scene.scene_type.casefold() == "gap" or not scene.text.strip():
                plans[index] = self._gap_plan(scene)
                reused_gaps += 1
                continue

            cache_key, _ = self._cache_identity(scenes, index)
            cache_keys[index] = cache_key
            cached = self.cache.load(cache_key)
            if cached is not None:
                # Timing/ID belong to this current scene; query semantics come from cache.
                plans[index] = SceneQueryPlan(
                    scene_id=scene.id,
                    scene_type=scene.scene_type,
                    start=scene.start,
                    end=scene.end,
                    duration=scene.duration,
                    dialogue_sha256=_dialogue_hash(scene.text),
                    primary_query=cached.primary_query,
                    queries=cached.queries,
                    avoid=cached.avoid,
                    preferred_type=cached.preferred_type,
                    planner_source="cache_kie_batch_scene_ai",
                    strategy=cached.strategy,
                    context=cached.context,
                    subject=cached.subject,
                    action=cached.action,
                    location=cached.location,
                    mood=cached.mood,
                    shot=cached.shot,
                    motion=cached.motion,
                )
                cache_hits += 1
            else:
                missing_indices.append(index)

        analyzer = self._ensure_batch_analyzer()
        batches = [
            missing_indices[start:start + self.batch_size]
            for start in range(0, len(missing_indices), self.batch_size)
        ]
        batch_request_count = 0
        ai_count = 0
        fallback_count = 0

        for batch_no, indices in enumerate(batches, start=1):
            if batch_callback is not None:
                batch_callback(batch_no, len(batches), len(indices))

            response_by_id: dict[str, dict[str, Any]] = {}
            if analyzer is not None and indices:
                batch_request_count += 1
                try:
                    response_by_id = analyzer.analyze_batch([scenes[i] for i in indices]) or {}
                except Exception:
                    response_by_id = {}

            for index in indices:
                scene = scenes[index]
                raw_payload = response_by_id.get(scene.id)
                if isinstance(raw_payload, dict):
                    try:
                        plan = self._plan_from_ai_payload(
                            scene,
                            raw_payload,
                            source="kie_batch_scene_ai",
                        )
                        plans[index] = plan
                        self.cache.save(cache_keys[index], plan)
                        ai_count += 1
                        continue
                    except Exception:
                        pass

                plans[index] = self._fallback_plan(scene)
                fallback_count += 1

        # If AI is disabled/no key, all missing speech scenes become deterministic fallback.
        for index in missing_indices:
            if plans[index] is None:
                plans[index] = self._fallback_plan(scenes[index])
                fallback_count += 1

        final_plans = tuple(plan for plan in plans if plan is not None)
        if len(final_plans) != total:
            raise RuntimeError("Query planner did not produce one plan per scene.")

        if progress_callback is not None:
            for index, plan in enumerate(final_plans, start=1):
                progress_callback(index, total, plan)

        return QueryPlanningReport(
            plans=final_plans,
            ai_count=ai_count,
            cache_hit_count=cache_hits,
            fallback_count=fallback_count,
            reused_gap_count=reused_gaps,
            batch_request_count=batch_request_count,
        )


def load_voice_scene_payload(path: Path) -> list[Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        scenes = payload.get("scenes")
        if isinstance(scenes, list):
            return scenes
    raise ValueError("voice_scenes.json must contain a list of scenes.")


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


def save_query_plan(path: Path, plans: Iterable[SceneQueryPlan], *, source_scenes: Path) -> Path:
    items = list(plans)
    payload = {
        "format": QUERY_PLAN_FORMAT,
        "source_voice_scenes": Path(source_scenes).name,
        "scene_count": len(items),
        "plans": [item.to_dict() for item in items],
    }
    return _atomic_json_write(Path(path), payload)
