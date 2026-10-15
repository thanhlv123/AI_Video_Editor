from __future__ import annotations

import errno
import html
import http.client
import json
import math
import os
import re
import socket
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable


YOUTUBE_REFERENCE_FORMAT = "creator_studio_youtube_reference_m110_3"
YOUTUBE_REFERENCE_FILENAME = "youtube_reference_manifest.json"
YOUTUBE_API_ENV = "YOUTUBE_API_KEY"
YOUTUBE_REGION_ENV = "YOUTUBE_REGION_CODE"
YOUTUBE_CC_ONLY_ENV = "YOUTUBE_REFERENCE_CC_ONLY"
YOUTUBE_STOCK_THRESHOLD_ENV = "YOUTUBE_REFERENCE_STOCK_THRESHOLD"
YOUTUBE_FORCE_IPV4_ENV = "YOUTUBE_FORCE_IPV4"
DEFAULT_STOCK_SCORE_THRESHOLD = 0.85
DEFAULT_RESULTS_PER_SCENE = 8


class YouTubeReferenceError(RuntimeError):
    """Controlled M110.3 YouTube-reference discovery failure."""


class YouTubeReferenceRequestError(YouTubeReferenceError):
    """Safe network/API error that never embeds the request URL or API key."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        reason_code: str = "",
        error_code: str = "",
    ):
        super().__init__(str(message or "YouTube API request failed."))
        self.http_status = int(http_status) if http_status is not None else None
        self.reason_code = str(reason_code or "")[:128]
        self.error_code = str(error_code or "")[:128]


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _create_ipv4_connection(
    address: tuple[str, int],
    timeout: float | object = socket._GLOBAL_DEFAULT_TIMEOUT,
    source_address: tuple[str, int] | None = None,
):
    """socket.create_connection equivalent restricted to AF_INET.

    Google APIs publish both AAAA and A records. Some Windows/network setups
    have IPv6 DNS records but no working IPv6 route, causing urllib to wait on
    unreachable IPv6 addresses before it can use IPv4. M110.3.1 keeps the
    workaround local to YouTube transport rather than disabling IPv6 globally.
    """
    host, port = address
    last_error: OSError | None = None
    for family, socktype, proto, _canonname, sockaddr in socket.getaddrinfo(
        host, port, socket.AF_INET, socket.SOCK_STREAM
    ):
        sock = None
        try:
            sock = socket.socket(family, socktype, proto)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            last_error = exc
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
    if last_error is not None:
        raise last_error
    raise OSError(errno.EHOSTUNREACH, f"No IPv4 address available for {host}")


class _IPv4HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _create_ipv4_connection


class _IPv4HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(
            _IPv4HTTPSConnection,
            req,
            context=self._context,
        )


def _safe_http_error(exc: urllib.error.HTTPError) -> YouTubeReferenceRequestError:
    http_status = getattr(exc, "code", None)
    message = f"YouTube API HTTP {http_status or 'error'}."
    reason_code = ""
    error_code = ""
    try:
        raw = exc.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            error_code = str(error.get("code") or "")
            api_message = str(error.get("message") or "").strip()
            if api_message:
                message = api_message[:500]
            details = error.get("errors")
            if isinstance(details, list) and details and isinstance(details[0], dict):
                reason_code = str(details[0].get("reason") or "")[:128]
    except Exception:
        pass
    return YouTubeReferenceRequestError(
        message,
        http_status=http_status,
        reason_code=reason_code,
        error_code=error_code,
    )


@dataclass(frozen=True)
class YouTubeReferenceReport:
    enabled: bool
    target_count: int
    searched_count: int
    reference_scene_count: int
    candidate_count: int
    chapter_segment_count: int
    unresolved_stock_count: int
    weak_stock_count: int
    missing_api_key: bool
    error_count: int
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "target_count": self.target_count,
            "searched_count": self.searched_count,
            "reference_scene_count": self.reference_scene_count,
            "candidate_count": self.candidate_count,
            "chapter_segment_count": self.chapter_segment_count,
            "unresolved_stock_count": self.unresolved_stock_count,
            "weak_stock_count": self.weak_stock_count,
            "missing_api_key": self.missing_api_key,
            "error_count": self.error_count,
            "manifest_path": self.manifest_path,
        }


@dataclass(frozen=True)
class YouTubeReferenceTarget:
    scene_id: str
    primary_query: str
    queries: tuple[str, ...]
    duration_seconds: float
    reason: str
    stock_score: float | None


@dataclass(frozen=True)
class YouTubeReferenceCandidate:
    video_id: str
    title: str
    channel_title: str
    published_at: str
    duration_seconds: float
    license: str
    embeddable: bool
    score: float
    matched_query: str
    chapter_title: str | None = None
    segment_start_seconds: float | None = None
    segment_end_seconds: float | None = None
    segment_basis: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": "youtube_reference",
            "video_id": self.video_id,
            "title": self.title,
            "channel_title": self.channel_title,
            "published_at": self.published_at,
            "duration_seconds": round(float(self.duration_seconds), 3),
            "license": self.license,
            "embeddable": bool(self.embeddable),
            "score": round(float(self.score), 6),
            "matched_query": self.matched_query,
            "chapter_title": self.chapter_title,
            "segment_start_seconds": (
                round(float(self.segment_start_seconds), 3)
                if self.segment_start_seconds is not None
                else None
            ),
            "segment_end_seconds": (
                round(float(self.segment_end_seconds), 3)
                if self.segment_end_seconds is not None
                else None
            ),
            "segment_basis": self.segment_basis,
            # YouTube references are discovery/preview metadata only. They are
            # never treated as local render assets by Creator Studio.
            "preview_only": True,
            "render_eligible": False,
        }


class YouTubeDataTransport:
    """Tiny urllib transport for official YouTube Data API v3 endpoints.

    M110.3.1 prefers IPv4 for Google APIs by default. This avoids long urllib
    stalls on Windows hosts where AAAA DNS works but the IPv6 route does not.
    Set YOUTUBE_FORCE_IPV4=0 to restore the platform default resolver behavior.
    """

    SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
    VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, *, timeout: float = 20.0, force_ipv4: bool | None = None):
        self.timeout = max(1.0, float(timeout or 20.0))
        self.force_ipv4 = (
            _env_flag(YOUTUBE_FORCE_IPV4_ENV, True)
            if force_ipv4 is None
            else bool(force_ipv4)
        )
        self._opener = (
            urllib.request.build_opener(_IPv4HTTPSHandler())
            if self.force_ipv4
            else None
        )

    def get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {
                str(key): str(value)
                for key, value in params.items()
                if value not in (None, "")
            }
        )
        request = urllib.request.Request(
            f"{endpoint}?{query}",
            headers={"Accept": "application/json", "User-Agent": "CreatorStudio-M110.3.1"},
            method="GET",
        )
        try:
            if self._opener is not None:
                response_context = self._opener.open(request, timeout=self.timeout)
            else:
                response_context = urllib.request.urlopen(request, timeout=self.timeout)
            with response_context as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise _safe_http_error(exc) from None
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, socket.timeout):
                message = "YouTube API timed out while connecting."
                reason_code = "timeout"
            else:
                message = f"YouTube API network error: {type(reason).__name__ if reason else 'URLError'}."
                reason_code = type(reason).__name__ if reason else "url_error"
            raise YouTubeReferenceRequestError(
                message,
                reason_code=reason_code,
            ) from None
        except (TimeoutError, socket.timeout):
            raise YouTubeReferenceRequestError(
                "YouTube API timed out while connecting.",
                reason_code="timeout",
            ) from None
        except OSError as exc:
            raise YouTubeReferenceRequestError(
                f"YouTube API network error: {type(exc).__name__}.",
                reason_code=type(exc).__name__,
            ) from None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            raise YouTubeReferenceRequestError(
                "YouTube API returned invalid JSON.",
                reason_code="invalid_json",
            ) from None
        if not isinstance(payload, dict):
            raise YouTubeReferenceRequestError(
                "YouTube API returned an invalid payload.",
                reason_code="invalid_payload",
            )
        return payload


_TIMESTAMP_RE = re.compile(
    r"(?<!\d)(?P<stamp>(?:\d{1,2}:)?\d{1,2}:\d{2})(?!\d)"
)
_TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "the", "to", "with", "video",
    "footage", "clip", "scene", "stock",
}


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
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


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(result):
        return float(default)
    return result


def parse_iso8601_duration(value: str | None) -> float:
    """Parse the subset of ISO-8601 durations returned by YouTube contentDetails."""
    text = str(value or "").strip().upper()
    if not text.startswith("P"):
        return 0.0
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?",
        text,
    )
    if not match:
        return 0.0
    return (
        int(match.group("days") or 0) * 86400
        + int(match.group("hours") or 0) * 3600
        + int(match.group("minutes") or 0) * 60
        + float(match.group("seconds") or 0.0)
    )


def _timestamp_seconds(stamp: str) -> float | None:
    parts = [item.strip() for item in str(stamp).split(":")]
    try:
        numbers = [int(item) for item in parts]
    except ValueError:
        return None
    if len(numbers) == 2:
        minutes, seconds = numbers
        hours = 0
    elif len(numbers) == 3:
        hours, minutes, seconds = numbers
    else:
        return None
    if minutes < 0 or seconds < 0 or seconds >= 60 or hours < 0:
        return None
    return float(hours * 3600 + minutes * 60 + seconds)


def parse_description_timestamps(description: str | None) -> list[tuple[float, str]]:
    """Extract uploader-authored timestamp/chapter labels from a description.

    This does not claim that arbitrary public videos expose frame-level segment
    metadata.  It only uses explicit timestamps written by the uploader.
    """
    chapters: list[tuple[float, str]] = []
    seen: set[float] = set()
    for raw_line in str(description or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _TIMESTAMP_RE.search(line)
        if match is None:
            continue
        seconds = _timestamp_seconds(match.group("stamp"))
        if seconds is None or seconds in seen:
            continue
        seen.add(seconds)
        label = (line[: match.start()] + " " + line[match.end() :]).strip(" -–—|:·\t")
        label = re.sub(r"\s+", " ", label).strip()
        chapters.append((seconds, label[:200]))
    chapters.sort(key=lambda item: item[0])
    return chapters


def _tokens(text: str | None) -> set[str]:
    result: set[str] = set()
    for raw in _TOKEN_RE.findall(str(text or "").lower()):
        token = raw.strip("-_ ")
        if len(token) <= 1 or token in _STOP_WORDS:
            continue
        result.add(token)
    return result


def _overlap(reference: set[str], candidate: set[str]) -> float:
    if not reference:
        return 0.0
    return len(reference & candidate) / len(reference)


def _candidate_score(
    *,
    query: str,
    title: str,
    description: str,
    chapter_title: str | None,
) -> float:
    query_tokens = _tokens(query)
    title_score = _overlap(query_tokens, _tokens(title))
    description_score = _overlap(query_tokens, _tokens(description))
    chapter_score = _overlap(query_tokens, _tokens(chapter_title or ""))
    phrase_bonus = 0.10 if query and query.lower() in f"{title} {description}".lower() else 0.0
    return max(
        0.0,
        min(1.0, 0.45 * title_score + 0.25 * description_score + 0.20 * chapter_score + phrase_bonus),
    )


def _best_chapter(
    chapters: list[tuple[float, str]],
    *,
    query: str,
    video_duration: float,
    scene_duration: float,
) -> tuple[str | None, float | None, float | None, str | None]:
    if not chapters:
        return None, None, None, None
    query_tokens = _tokens(query)
    ranked = []
    for index, (start, title) in enumerate(chapters):
        score = _overlap(query_tokens, _tokens(title))
        ranked.append((score, -start, index, start, title))
    ranked.sort(reverse=True)
    _, _, index, start, title = ranked[0]
    next_start = chapters[index + 1][0] if index + 1 < len(chapters) else 0.0
    if next_start > start:
        end = next_start
    elif video_duration > start:
        desired = max(6.0, float(scene_duration or 0.0) + 2.0)
        end = min(video_duration, start + desired)
    else:
        end = None
    return title or None, start, end, "description_timestamp"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise YouTubeReferenceError(f"JSON không hợp lệ: {Path(path).name}")
    return payload


def _stock_score(stock: dict[str, Any]) -> float | None:
    selection = stock.get("selection") if isinstance(stock.get("selection"), dict) else {}
    value = selection.get("best_score")
    if value in (None, ""):
        selected = stock.get("selected_media") if isinstance(stock.get("selected_media"), dict) else {}
        value = selected.get("final_score")
    if value in (None, ""):
        return None
    score = _to_float(value, -1.0)
    if score < 0:
        return None
    return max(0.0, min(1.0, score))


def build_reference_targets(
    query_plan_path: Path,
    stock_manifest_path: Path,
    *,
    weak_stock_threshold: float = DEFAULT_STOCK_SCORE_THRESHOLD,
) -> list[YouTubeReferenceTarget]:
    query_payload = _load_json(query_plan_path)
    stock_payload = _load_json(stock_manifest_path)
    plans = query_payload.get("plans") or []
    stock_scenes = stock_payload.get("scenes") or []
    by_stock_id = {
        str(item.get("scene_id") or ""): item
        for item in stock_scenes
        if isinstance(item, dict) and str(item.get("scene_id") or "")
    }
    threshold = max(0.0, min(1.0, float(weak_stock_threshold)))
    targets: list[YouTubeReferenceTarget] = []
    for raw in plans:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("strategy") or "search") == "reuse_previous":
            continue
        scene_id = str(raw.get("scene_id") or "").strip()
        if not scene_id:
            continue
        stock_scene = by_stock_id.get(scene_id, {})
        stock = stock_scene.get("stock") if isinstance(stock_scene.get("stock"), dict) else {}
        status = str(stock.get("status") or "").strip().lower()
        score = _stock_score(stock)
        if status != "validated":
            reason = "unresolved_stock"
        elif score is not None and score < threshold:
            reason = "weak_stock"
        else:
            continue
        primary = str(raw.get("primary_query") or "").strip()
        queries = tuple(
            dict.fromkeys(
                [primary]
                + [str(item).strip() for item in (raw.get("queries") or []) if str(item).strip()]
            )
        )
        queries = tuple(item for item in queries if item)
        if not primary and queries:
            primary = queries[0]
        if not primary:
            continue
        targets.append(
            YouTubeReferenceTarget(
                scene_id=scene_id,
                primary_query=primary,
                queries=queries,
                duration_seconds=max(0.0, _to_float(raw.get("duration"), 0.0)),
                reason=reason,
                stock_score=score,
            )
        )
    return targets


class YouTubeReferenceService:
    """Find preview-only YouTube references for unresolved/weak stock scenes.

    M110.3 deliberately does not download, cache, import or render YouTube
    audiovisual bytes.  It uses official Data API metadata and uploader-authored
    description timestamps to suggest relevant videos/segments for later
    query-refinement and preview workflows.
    """

    def __init__(
        self,
        *,
        run_dir: Path,
        query_plan_path: Path,
        stock_manifest_path: Path,
        api_key: str | None = None,
        language: str = "",
        region_code: str = "",
        creative_commons_only: bool = False,
        max_results_per_scene: int = DEFAULT_RESULTS_PER_SCENE,
        weak_stock_threshold: float = DEFAULT_STOCK_SCORE_THRESHOLD,
        transport: Any | None = None,
        progress_callback: Callable[[int, int, str, str], None] | None = None,
    ):
        self.run_dir = Path(run_dir).resolve()
        self.query_plan_path = Path(query_plan_path).resolve()
        self.stock_manifest_path = Path(stock_manifest_path).resolve()
        self.api_key = str(api_key or os.getenv(YOUTUBE_API_ENV) or "").strip()
        self.language = str(language or "").strip()
        self.region_code = str(region_code or os.getenv(YOUTUBE_REGION_ENV) or "").strip().upper()
        self.creative_commons_only = bool(creative_commons_only)
        self.max_results_per_scene = max(1, min(25, int(max_results_per_scene or DEFAULT_RESULTS_PER_SCENE)))
        self.weak_stock_threshold = max(0.0, min(1.0, float(weak_stock_threshold)))
        self.transport = transport or YouTubeDataTransport()
        self.progress_callback = progress_callback

    @classmethod
    def from_runtime_environment(
        cls,
        *,
        run_dir: Path,
        query_plan_path: Path,
        stock_manifest_path: Path,
        runtime_environment: dict[str, str] | None = None,
        language: str = "",
        progress_callback: Callable[[int, int, str, str], None] | None = None,
        transport: Any | None = None,
    ) -> "YouTubeReferenceService":
        env = dict(runtime_environment or {})
        threshold = _to_float(
            env.get(YOUTUBE_STOCK_THRESHOLD_ENV)
            or os.getenv(YOUTUBE_STOCK_THRESHOLD_ENV),
            DEFAULT_STOCK_SCORE_THRESHOLD,
        )
        cc_raw = str(
            env.get(YOUTUBE_CC_ONLY_ENV)
            or os.getenv(YOUTUBE_CC_ONLY_ENV)
            or ""
        ).strip().lower()
        return cls(
            run_dir=run_dir,
            query_plan_path=query_plan_path,
            stock_manifest_path=stock_manifest_path,
            api_key=env.get(YOUTUBE_API_ENV) or os.getenv(YOUTUBE_API_ENV),
            language=language,
            region_code=env.get(YOUTUBE_REGION_ENV) or os.getenv(YOUTUBE_REGION_ENV) or "",
            creative_commons_only=cc_raw in {"1", "true", "yes", "on"},
            weak_stock_threshold=threshold,
            transport=transport,
            progress_callback=progress_callback,
        )

    @property
    def output_path(self) -> Path:
        return self.run_dir / YOUTUBE_REFERENCE_FILENAME

    def _search(self, query: str) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": self.max_results_per_scene,
            "videoEmbeddable": "true",
            "videoSyndicated": "true",
            "safeSearch": "moderate",
            "key": self.api_key,
        }
        if self.creative_commons_only:
            params["videoLicense"] = "creativeCommon"
        language = self.language.split("-")[0].lower()
        if re.fullmatch(r"[a-z]{2}", language):
            params["relevanceLanguage"] = language
        if re.fullmatch(r"[A-Z]{2}", self.region_code):
            params["regionCode"] = self.region_code
        payload = self.transport.get_json(YouTubeDataTransport.SEARCH_ENDPOINT, params)
        return [item for item in (payload.get("items") or []) if isinstance(item, dict)]

    def _video_details(self, video_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        ids = [str(item).strip() for item in video_ids if str(item).strip()]
        if not ids:
            return {}
        payload = self.transport.get_json(
            YouTubeDataTransport.VIDEOS_ENDPOINT,
            {
                "part": "snippet,contentDetails,status",
                "id": ",".join(ids),
                "key": self.api_key,
            },
        )
        result: dict[str, dict[str, Any]] = {}
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            video_id = str(item.get("id") or "").strip()
            if video_id:
                result[video_id] = item
        return result

    def _candidate_from_video(
        self,
        *,
        video_id: str,
        detail: dict[str, Any],
        query: str,
        scene_duration: float,
    ) -> YouTubeReferenceCandidate | None:
        snippet = detail.get("snippet") if isinstance(detail.get("snippet"), dict) else {}
        content = detail.get("contentDetails") if isinstance(detail.get("contentDetails"), dict) else {}
        status = detail.get("status") if isinstance(detail.get("status"), dict) else {}
        if status.get("embeddable") is False:
            return None
        title = html.unescape(str(snippet.get("title") or "")).strip()
        description = html.unescape(str(snippet.get("description") or ""))
        duration = parse_iso8601_duration(str(content.get("duration") or ""))
        chapters = parse_description_timestamps(description)
        chapter_title, start, end, basis = _best_chapter(
            chapters,
            query=query,
            video_duration=duration,
            scene_duration=scene_duration,
        )
        score = _candidate_score(
            query=query,
            title=title,
            description=description,
            chapter_title=chapter_title,
        )
        return YouTubeReferenceCandidate(
            video_id=video_id,
            title=title[:300],
            channel_title=html.unescape(str(snippet.get("channelTitle") or "")).strip()[:200],
            published_at=str(snippet.get("publishedAt") or "")[:64],
            duration_seconds=duration,
            license=str(status.get("license") or "youtube")[:64],
            embeddable=bool(status.get("embeddable", True)),
            score=score,
            matched_query=query,
            chapter_title=chapter_title,
            segment_start_seconds=start,
            segment_end_seconds=end,
            segment_basis=basis,
        )

    def run(self) -> YouTubeReferenceReport:
        if not self.query_plan_path.is_file():
            raise FileNotFoundError(self.query_plan_path)
        if not self.stock_manifest_path.is_file():
            raise FileNotFoundError(self.stock_manifest_path)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        targets = build_reference_targets(
            self.query_plan_path,
            self.stock_manifest_path,
            weak_stock_threshold=self.weak_stock_threshold,
        )
        unresolved_stock_count = sum(1 for item in targets if item.reason == "unresolved_stock")
        weak_stock_count = sum(1 for item in targets if item.reason == "weak_stock")

        if not targets:
            payload = {
                "format": YOUTUBE_REFERENCE_FORMAT,
                "created_at": datetime.now().astimezone().isoformat(),
                "enabled": bool(self.api_key),
                "target_count": 0,
                "weak_stock_threshold": self.weak_stock_threshold,
                "creative_commons_only": self.creative_commons_only,
                "scenes": [],
            }
            _atomic_json_write(self.output_path, payload)
            return YouTubeReferenceReport(
                enabled=bool(self.api_key),
                target_count=0,
                searched_count=0,
                reference_scene_count=0,
                candidate_count=0,
                chapter_segment_count=0,
                unresolved_stock_count=0,
                weak_stock_count=0,
                missing_api_key=False,
                error_count=0,
                manifest_path=str(self.output_path),
            )

        if not self.api_key:
            payload = {
                "format": YOUTUBE_REFERENCE_FORMAT,
                "created_at": datetime.now().astimezone().isoformat(),
                "enabled": False,
                "target_count": len(targets),
                "weak_stock_threshold": self.weak_stock_threshold,
                "creative_commons_only": self.creative_commons_only,
                "missing_api_key": True,
                "scenes": [
                    {
                        "scene_id": item.scene_id,
                        "reason": item.reason,
                        "stock_score": item.stock_score,
                        "status": "not_searched",
                    }
                    for item in targets
                ],
            }
            _atomic_json_write(self.output_path, payload)
            return YouTubeReferenceReport(
                enabled=False,
                target_count=len(targets),
                searched_count=0,
                reference_scene_count=0,
                candidate_count=0,
                chapter_segment_count=0,
                unresolved_stock_count=unresolved_stock_count,
                weak_stock_count=weak_stock_count,
                missing_api_key=True,
                error_count=0,
                manifest_path=str(self.output_path),
            )

        scene_results: list[dict[str, Any]] = []
        total_candidates = 0
        chapter_segments = 0
        reference_scenes = 0
        searched_count = 0
        error_count = 0

        for index, target in enumerate(targets, start=1):
            if self.progress_callback is not None:
                self.progress_callback(index, len(targets), target.scene_id, target.primary_query)
            query = target.primary_query
            try:
                search_items = self._search(query)
                # One alternate query is allowed only when the primary has no hits.
                if not search_items:
                    for alternate in target.queries:
                        if alternate == query:
                            continue
                        query = alternate
                        search_items = self._search(query)
                        if search_items:
                            break
                video_ids = []
                for item in search_items:
                    ident = item.get("id") if isinstance(item.get("id"), dict) else {}
                    video_id = str(ident.get("videoId") or "").strip()
                    if video_id and video_id not in video_ids:
                        video_ids.append(video_id)
                details = self._video_details(video_ids)
                candidates: list[YouTubeReferenceCandidate] = []
                for video_id in video_ids:
                    detail = details.get(video_id)
                    if not detail:
                        continue
                    candidate = self._candidate_from_video(
                        video_id=video_id,
                        detail=detail,
                        query=query,
                        scene_duration=target.duration_seconds,
                    )
                    if candidate is not None:
                        candidates.append(candidate)
                candidates.sort(key=lambda item: (-item.score, item.video_id))
                candidates = candidates[: self.max_results_per_scene]
                searched_count += 1
                total_candidates += len(candidates)
                chapter_segments += sum(
                    1 for item in candidates if item.segment_start_seconds is not None
                )
                if candidates:
                    reference_scenes += 1
                scene_results.append(
                    {
                        "scene_id": target.scene_id,
                        "reason": target.reason,
                        "stock_score": target.stock_score,
                        "status": "searched",
                        "candidate_count": len(candidates),
                        "best_candidate": candidates[0].to_dict() if candidates else None,
                        "candidates": [item.to_dict() for item in candidates],
                    }
                )
            except Exception as exc:
                error_count += 1
                error_item = {
                    "scene_id": target.scene_id,
                    "reason": target.reason,
                    "stock_score": target.stock_score,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:500],
                    "candidate_count": 0,
                    "best_candidate": None,
                    "candidates": [],
                }
                if isinstance(exc, YouTubeReferenceRequestError):
                    error_item["http_status"] = exc.http_status
                    error_item["error_reason"] = exc.reason_code or None
                    error_item["error_code"] = exc.error_code or None
                scene_results.append(error_item)

        payload = {
            "format": YOUTUBE_REFERENCE_FORMAT,
            "created_at": datetime.now().astimezone().isoformat(),
            "enabled": True,
            "target_count": len(targets),
            "weak_stock_threshold": self.weak_stock_threshold,
            "creative_commons_only": self.creative_commons_only,
            "scenes": scene_results,
        }
        _atomic_json_write(self.output_path, payload)
        return YouTubeReferenceReport(
            enabled=True,
            target_count=len(targets),
            searched_count=searched_count,
            reference_scene_count=reference_scenes,
            candidate_count=total_candidates,
            chapter_segment_count=chapter_segments,
            unresolved_stock_count=unresolved_stock_count,
            weak_stock_count=weak_stock_count,
            missing_api_key=False,
            error_count=error_count,
            manifest_path=str(self.output_path),
        )
