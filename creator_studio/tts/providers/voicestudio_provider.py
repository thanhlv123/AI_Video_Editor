from __future__ import annotations

import io
import json
import os
import re
import unicodedata
import wave
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

import requests

from ..models import (
    TTSProviderInfo,
    TTSEngine,
    TTSProviderUnavailableError,
    TTSSynthesisError,
    TTSSynthesisRequest,
    TTSSynthesisResult,
    TTSVoice,
    TTSVoiceCloneRequest,
    TTSVoiceCloneResult,
)


class VoiceStudioLocalProvider:
    """Local VoiceStudio adapter using the documented loopback HTTP API.

    This provider deliberately accepts loopback URLs only. A future remote/VPS
    VoiceStudio integration should use a separate provider with an explicit
    authentication and transport policy.
    """

    PROVIDER_ID = "voicestudio_local"
    DEFAULT_BASE_URL = "http://127.0.0.1:3900"
    DEFAULT_MODEL = "tts-1"  # Alias for the currently active VoiceStudio TTS engine.
    MAX_API_CHARS = 4096
    CHUNK_TARGET = 3800
    # VoiceStudio 0.5.6's KittenTTS adapter validates the raw speaker ids
    # (expr-voice-*) rather than the friendly names exposed by upstream
    # KittenTTS. Keep a stable display-name -> raw-id mapping here so the UI
    # can show Bella/Jasper/... while the API receives the id VoiceStudio
    # actually accepts.
    KITTENTTS_VOICE_MAP = {
        "Bella": "expr-voice-2-f",
        "Jasper": "expr-voice-2-m",
        "Luna": "expr-voice-3-f",
        "Bruno": "expr-voice-3-m",
        "Rosie": "expr-voice-4-f",
        "Hugo": "expr-voice-4-m",
        "Kiki": "expr-voice-5-f",
        "Leo": "expr-voice-5-m",
    }
    KITTENTTS_VOICES = tuple(KITTENTTS_VOICE_MAP.keys())
    KITTENTTS_RAW_IDS = frozenset(KITTENTTS_VOICE_MAP.values())
    KITTENTTS_DEFAULT_RAW_ID = KITTENTTS_VOICE_MAP["Bella"]
    CLONE_CAPABLE_ENGINE_PREFIXES = ("omnivoice", "voxcpm", "cosyvoice", "moss", "gpt-sovits", "indextts", "pockettts", "confucius")

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout_seconds: int = 900,
        connect_timeout_seconds: int = 5,
        default_model: str = DEFAULT_MODEL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._validate_loopback_url(self.base_url)
        self.api_key = (
            api_key
            or os.environ.get("VOICESTUDIO_API_KEY")
            or os.environ.get("OMNIVOICE_API_KEY")
            or ""
        ).strip()
        self.timeout_seconds = int(timeout_seconds)
        self.connect_timeout_seconds = int(connect_timeout_seconds)
        self.default_model = str(default_model or self.DEFAULT_MODEL).strip()

    def set_base_url(self, base_url: str) -> None:
        value = str(base_url or "").rstrip("/")
        self._validate_loopback_url(value)
        self.base_url = value

    @property
    def info(self) -> TTSProviderInfo:
        return TTSProviderInfo(
            provider_id=self.PROVIDER_ID,
            display_name="VoiceStudio Local",
            is_local=True,
            supports_voice_cloning=True,
            supports_preview=True,
        )

    def health_check(self) -> tuple[bool, str]:
        try:
            response = self._request("GET", "/health", timeout_seconds=8)
        except Exception:
            return False, (
                "VoiceStudio Local chưa sẵn sàng tại "
                f"{self.base_url}. Hãy mở VoiceStudio hoặc chờ backend khởi động."
            )

        if response.status_code >= 400:
            return False, self._http_error(response, prefix="VoiceStudio health check thất bại")

        device = None
        version = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                device = payload.get("device") or payload.get("compute_device")
                version = payload.get("version")
        except Exception:
            payload = None

        detail = f"VoiceStudio Local sẵn sàng · {self.base_url}"
        extras = [str(x) for x in (version, device) if x]
        if extras:
            detail += " · " + " · ".join(extras)
        return True, detail

    def list_voices(self) -> Sequence[TTSVoice]:
        return self.list_voices_for_engine(self.default_model)

    def list_voices_for_engine(self, engine_id: str | None = None) -> Sequence[TTSVoice]:
        engine_id = str(engine_id or self.default_model or "tts-1").strip()
        response = self._request("GET", "/v1/audio/voices", timeout_seconds=20)
        if response.status_code >= 400:
            raise TTSProviderUnavailableError(
                self._http_error(response, prefix="Không thể lấy danh sách giọng VoiceStudio")
            )

        try:
            payload = response.json()
        except Exception as exc:
            raise TTSProviderUnavailableError("VoiceStudio trả về danh sách giọng không hợp lệ") from exc

        raw_voices = payload.get("voices", []) if isinstance(payload, dict) else []
        profiles: list[TTSVoice] = []
        for item in raw_voices if isinstance(raw_voices, list) else []:
            if not isinstance(item, dict):
                continue
            voice_type = str(item.get("type") or "profile").strip()
            if voice_type == "openai_alias":
                continue
            voice_id = str(item.get("voice_id") or item.get("id") or "").strip()
            if not voice_id:
                continue
            name = str(item.get("name") or voice_id).strip()
            language = str(item.get("language") or "").strip() or None
            profiles.append(
                TTSVoice(
                    provider_id=self.PROVIDER_ID,
                    voice_id=voice_id,
                    display_name=f"{name} · VoiceStudio profile",
                    language=language,
                    quality="profile",
                )
            )

        # KittenTTS has eight friendly speaker names, but VoiceStudio 0.5.6
        # validates only the underlying expr-voice-* ids. Expose friendly
        # labels while storing the raw id in QComboBox item data.
        if engine_id == "kittentts":
            genders = {
                "Bella": "Nữ",
                "Jasper": "Nam",
                "Luna": "Nữ",
                "Bruno": "Nam",
                "Rosie": "Nữ",
                "Hugo": "Nam",
                "Kiki": "Nữ",
                "Leo": "Nam",
            }
            return tuple(
                TTSVoice(
                    provider_id=self.PROVIDER_ID,
                    # IMPORTANT: VoiceStudio 0.5.6 accepts only expr-voice-*
                    # ids in KittenTTSBackend.PRESET_VOICES. Friendly names
                    # silently fall back to the default speaker.
                    voice_id=raw_id,
                    display_name=f"{name} · {genders[name]} · KittenTTS",
                    language="en",
                    quality="preset",
                )
                for name, raw_id in self.KITTENTTS_VOICE_MAP.items()
            )

        voices: list[TTSVoice] = [
            TTSVoice(
                provider_id=self.PROVIDER_ID,
                voice_id="default",
                display_name="VoiceStudio mặc định",
                language=None,
                quality=engine_id,
            )
        ]
        voices.extend(profiles)
        return tuple(voices)

    def list_engines(self) -> tuple[TTSEngine, ...]:
        models = self.list_models()
        engines: list[TTSEngine] = []
        # Keep the active-engine alias as a convenience, then list actual
        # installed TTS engines returned by VoiceStudio.
        engines.append(
            TTSEngine(
                provider_id=self.PROVIDER_ID,
                engine_id="tts-1",
                display_name="Engine đang chọn trong VoiceStudio",
                supports_voice_cloning=True,
                is_alias=True,
            )
        )
        seen = {"tts-1"}
        for item in models:
            model_id = str(item.get("id") or "").strip()
            meta = item.get("voicestudio") if isinstance(item.get("voicestudio"), dict) else {}
            if not model_id or model_id in seen:
                continue
            if str(meta.get("kind") or "") != "tts":
                continue
            if bool(meta.get("alias_for_active_engine")):
                continue
            seen.add(model_id)
            engines.append(
                TTSEngine(
                    provider_id=self.PROVIDER_ID,
                    engine_id=model_id,
                    display_name=self._engine_display_name(model_id),
                    supports_voice_cloning=self.engine_supports_voice_cloning(model_id),
                    is_alias=False,
                )
            )
        return tuple(engines)

    def engine_supports_voice_cloning(self, engine_id: str | None) -> bool:
        value = str(engine_id or "tts-1").strip().lower()
        if value == "kittentts":
            return False
        if value == "tts-1":
            # Active-engine alias: provider supports cloning, but actual support
            # depends on the engine selected in VoiceStudio. Keep clone UI
            # available so saved profiles remain usable.
            return True
        return value.startswith(self.CLONE_CAPABLE_ENGINE_PREFIXES)

    @staticmethod
    def _engine_display_name(engine_id: str) -> str:
        names = {
            "omnivoice": "OmniVoice · clone giọng",
            "omnivoice-subprocess": "OmniVoice Subprocess · clone giọng",
            "kittentts": "KittenTTS · 8 giọng preset · CPU",
            "voxcpm2": "VoxCPM2 · clone/voice design",
            "cosyvoice": "CosyVoice",
            "moss-tts-nano": "MOSS-TTS Nano",
            "indextts2": "IndexTTS 2.5",
        }
        return names.get(engine_id, engine_id)

    def list_models(self) -> tuple[dict[str, Any], ...]:
        response = self._request("GET", "/v1/models", timeout_seconds=20)
        if response.status_code >= 400:
            raise TTSProviderUnavailableError(
                self._http_error(response, prefix="Không thể lấy danh sách model VoiceStudio")
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise TTSProviderUnavailableError("VoiceStudio trả về danh sách model không hợp lệ") from exc
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return tuple(item for item in data if isinstance(item, dict))

    def list_profiles(self) -> tuple[dict[str, Any], ...]:
        response = self._request("GET", "/profiles", timeout_seconds=20)
        if response.status_code >= 400:
            raise TTSProviderUnavailableError(
                self._http_error(response, prefix="Không thể lấy voice profile VoiceStudio")
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise TTSProviderUnavailableError("VoiceStudio trả về profile không hợp lệ") from exc
        if not isinstance(payload, list):
            return ()
        return tuple(item for item in payload if isinstance(item, dict))

    def clone_voice(self, request: TTSVoiceCloneRequest) -> TTSVoiceCloneResult:
        """Create a local VoiceStudio clone profile through the provider contract.

        The UI/caller must obtain confirmation that the user owns the voice or
        has permission to clone it before this method is called.
        """
        if request.provider_id != self.PROVIDER_ID:
            raise ValueError(f"Request provider mismatch: {request.provider_id!r}")
        clean_name = str(request.name or "").strip()
        if not clean_name:
            raise ValueError("name must not be empty")
        audio_path = Path(request.reference_audio).resolve()
        if not audio_path.is_file():
            raise FileNotFoundError(f"Reference audio not found: {audio_path}")

        allowed = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".oga", ".opus", ".aac", ".webm"}
        if audio_path.suffix.lower() not in allowed:
            raise ValueError("Reference audio must be WAV, MP3, M4A, FLAC, OGG, Opus, AAC, or WebM")

        headers = self._headers()
        data = {
            "name": clean_name,
            "ref_text": str(request.ref_text or ""),
            "instruct": str(request.instruct or ""),
            "language": str(request.language or "Auto"),
            "kind": "clone",
        }
        try:
            with audio_path.open("rb") as stream:
                files = {
                    "ref_audio": (
                        audio_path.name,
                        stream,
                        self._audio_mime(audio_path.suffix.lower()),
                    )
                }
                response = requests.post(
                    f"{self.base_url}/profiles",
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=(self.connect_timeout_seconds, self.timeout_seconds),
                )
        except requests.RequestException as exc:
            raise TTSProviderUnavailableError(
                f"Không thể kết nối VoiceStudio Local tại {self.base_url}."
            ) from exc

        if response.status_code >= 400:
            raise TTSSynthesisError(
                self._http_error(response, prefix="Không thể tạo voice clone VoiceStudio")
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise TTSSynthesisError("VoiceStudio tạo profile nhưng trả về JSON không hợp lệ") from exc
        if not isinstance(payload, dict):
            raise TTSSynthesisError("VoiceStudio tạo profile nhưng response không hợp lệ")

        voice_id = str(payload.get("id") or payload.get("profile_id") or "").strip()
        if not voice_id:
            raise TTSSynthesisError("VoiceStudio đã tạo profile nhưng không trả về profile id")
        display_name = str(payload.get("name") or clean_name).strip() or clean_name
        language = str(payload.get("language") or request.language or "").strip() or None
        return TTSVoiceCloneResult(
            provider_id=self.PROVIDER_ID,
            voice_id=voice_id,
            display_name=display_name,
            language=language,
            raw=payload,
        )

    def create_clone_profile(
        self,
        *,
        name: str,
        reference_audio: str | Path,
        ref_text: str = "",
        language: str = "Auto",
        instruct: str = "",
    ) -> dict[str, Any]:
        """Backward-compatible wrapper for older callers."""
        result = self.clone_voice(
            TTSVoiceCloneRequest(
                provider_id=self.PROVIDER_ID,
                name=name,
                reference_audio=Path(reference_audio),
                ref_text=ref_text,
                language=language,
                instruct=instruct,
            )
        )
        return dict(result.raw or {
            "id": result.voice_id,
            "name": result.display_name,
            "language": result.language,
        })

    def synthesize(self, request: TTSSynthesisRequest) -> TTSSynthesisResult:
        if request.provider_id != self.PROVIDER_ID:
            raise ValueError(f"Request provider mismatch: {request.provider_id!r}")
        if not request.text or not request.text.strip():
            raise ValueError("text must not be empty")
        if not (0.25 <= request.speed <= 4.0):
            raise ValueError("speed must be between 0.25 and 4.0")

        healthy, detail = self.health_check()
        if not healthy:
            raise TTSProviderUnavailableError(detail)

        model_id = str(request.model_id or self.default_model or "tts-1").strip()
        voice_id = self._normalize_voice_id(model_id, request.voice_id)
        output_path = Path(request.output_path).resolve()
        if output_path.suffix.lower() != ".wav":
            raise ValueError("VoiceStudioLocalProvider currently outputs WAV only")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        clean_text = self._sanitize_text(request.text)
        chunks = self._split_text(clean_text)
        if not chunks:
            raise ValueError("text contains no speakable content")

        temp_dir = output_path.parent / f".{output_path.stem}.voicestudio_parts"
        temp_dir.mkdir(parents=True, exist_ok=True)
        part_paths: list[Path] = []

        try:
            for index, chunk in enumerate(chunks, 1):
                part_path = temp_dir / f"part_{index:04d}.wav"
                self._synthesize_chunk(
                    text=chunk,
                    voice_id=voice_id,
                    speed=request.speed,
                    model_id=model_id,
                    output_path=part_path,
                )
                part_paths.append(part_path)

            working = output_path.with_name(output_path.stem + ".tts-working.wav")
            self._merge_wav_parts(part_paths, working)
            if output_path.exists():
                output_path.unlink()
            os.replace(working, output_path)
        finally:
            for part in part_paths:
                try:
                    part.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                temp_dir.rmdir()
            except Exception:
                pass

        duration = self._wav_duration(output_path)
        return TTSSynthesisResult(
            provider_id=self.PROVIDER_ID,
            voice_id=voice_id,
            output_path=output_path,
            duration_seconds=duration,
            byte_count=output_path.stat().st_size,
            model_id=model_id,
        )

    def _synthesize_chunk(
        self,
        *,
        text: str,
        voice_id: str,
        speed: float,
        model_id: str,
        output_path: Path,
    ) -> None:
        payload = {
            "model": model_id or self.default_model,
            "voice": voice_id or "default",
            "input": text,
            "speed": float(speed),
            "response_format": "wav",
        }
        response = self._request(
            "POST",
            "/v1/audio/speech",
            json=payload,
            timeout_seconds=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise TTSSynthesisError(
                self._http_error(response, prefix="VoiceStudio tạo giọng thất bại")
            )
        content = response.content
        if len(content) <= 44:
            raise TTSSynthesisError("VoiceStudio không trả về WAV hợp lệ")

        output_path.write_bytes(content)
        try:
            with wave.open(str(output_path), "rb") as wav_file:
                if wav_file.getnframes() <= 0 or wav_file.getframerate() <= 0:
                    raise TTSSynthesisError("VoiceStudio trả về WAV không có dữ liệu âm thanh")
        except wave.Error as exc:
            raise TTSSynthesisError("VoiceStudio trả về dữ liệu không phải WAV hợp lệ") from exc

    @classmethod
    def _normalize_voice_id(cls, model_id: str, voice_id: str | None) -> str:
        """Return the engine-native voice id used by VoiceStudio.

        VoiceStudio 0.5.6's KittenTTS adapter lists only ``expr-voice-*`` in
        ``PRESET_VOICES``. Sending ``Bella``/``Jasper``/etc. is accepted by the
        OpenAI route but the backend then silently falls back to its default
        speaker. Normalize friendly names here and reject typos instead of
        allowing a misleading successful response with the wrong voice.
        """
        value = str(voice_id or "default").strip()
        if str(model_id or "").strip().lower() != "kittentts":
            return value or "default"

        if not value or value.lower() == "default":
            return cls.KITTENTTS_DEFAULT_RAW_ID
        if value in cls.KITTENTTS_RAW_IDS:
            return value

        for name, raw_id in cls.KITTENTTS_VOICE_MAP.items():
            if value.casefold() == name.casefold():
                return raw_id

        valid = ", ".join(cls.KITTENTTS_VOICES)
        raise ValueError(
            f"Giọng KittenTTS không hợp lệ: {value!r}. Hãy chọn một trong: {valid}."
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: int | None = None,
        **kwargs,
    ) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.update(self._headers())
        try:
            return requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=(
                    self.connect_timeout_seconds,
                    int(timeout_seconds or self.timeout_seconds),
                ),
                **kwargs,
            )
        except requests.RequestException as exc:
            raise TTSProviderUnavailableError(
                f"Không thể kết nối VoiceStudio Local tại {self.base_url}."
            ) from exc

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json, audio/wav"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @classmethod
    def _split_text(cls, text: str) -> list[str]:
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text:
            return []
        if len(text) <= cls.MAX_API_CHARS:
            return [text]

        sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
        chunks: list[str] = []
        current = ""

        def flush() -> None:
            nonlocal current
            if current.strip():
                chunks.append(current.strip())
            current = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) > cls.CHUNK_TARGET:
                flush()
                remainder = sentence
                while len(remainder) > cls.CHUNK_TARGET:
                    cut = remainder.rfind(" ", 0, cls.CHUNK_TARGET)
                    if cut < cls.CHUNK_TARGET // 2:
                        cut = cls.CHUNK_TARGET
                    chunks.append(remainder[:cut].strip())
                    remainder = remainder[cut:].strip()
                if remainder:
                    current = remainder
                continue

            candidate = sentence if not current else f"{current} {sentence}"
            if len(candidate) <= cls.CHUNK_TARGET:
                current = candidate
            else:
                flush()
                current = sentence
        flush()
        return chunks

    @staticmethod
    def _merge_wav_parts(parts: Sequence[Path], output_path: Path) -> None:
        if not parts:
            raise TTSSynthesisError("Không có audio chunk để ghép")

        params = None
        frames: list[bytes] = []
        for path in parts:
            with wave.open(str(path), "rb") as wav_file:
                current = (
                    wav_file.getnchannels(),
                    wav_file.getsampwidth(),
                    wav_file.getframerate(),
                    wav_file.getcomptype(),
                    wav_file.getcompname(),
                )
                if params is None:
                    params = current
                elif current != params:
                    raise TTSSynthesisError(
                        "Các chunk VoiceStudio có định dạng WAV không đồng nhất; không thể ghép an toàn"
                    )
                frames.append(wav_file.readframes(wav_file.getnframes()))

        assert params is not None
        with wave.open(str(output_path), "wb") as out:
            out.setnchannels(params[0])
            out.setsampwidth(params[1])
            out.setframerate(params[2])
            out.setcomptype(params[3], params[4])
            for data in frames:
                out.writeframes(data)

    @staticmethod
    def _wav_duration(path: Path) -> float:
        with wave.open(str(path), "rb") as wav_file:
            rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            return frames / float(rate) if rate > 0 else 0.0

    @staticmethod
    def _sanitize_text(value: str) -> str:
        cleaned = "".join(
            " " if 0xD800 <= ord(char) <= 0xDFFF else char
            for char in str(value)
        )
        return unicodedata.normalize("NFC", cleaned)

    @staticmethod
    def _audio_mime(suffix: str) -> str:
        return {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".flac": "audio/flac",
            ".ogg": "audio/ogg",
            ".opus": "audio/ogg",
            ".aac": "audio/aac",
            ".webm": "audio/webm",
        }.get(suffix, "application/octet-stream")

    @staticmethod
    def _http_error(response: requests.Response, *, prefix: str) -> str:
        message = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    message = str(error.get("message") or "")
                if not message:
                    detail = payload.get("detail")
                    if isinstance(detail, dict):
                        message = str(detail.get("message") or detail.get("detail") or json.dumps(detail, ensure_ascii=False))
                    elif detail is not None:
                        message = str(detail)
        except Exception:
            message = ""
        if not message:
            message = (response.text or "").strip()
        if len(message) > 800:
            message = message[:800].rstrip() + "…"
        suffix = f": {message}" if message else ""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            suffix += f" · thử lại sau {retry_after}s"
        return f"{prefix} (HTTP {response.status_code}){suffix}"

    @staticmethod
    def _validate_loopback_url(base_url: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("VoiceStudio base_url must use http or https")
        host = (parsed.hostname or "").lower()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(
                "VoiceStudioLocalProvider only accepts loopback URLs. "
                "Use a dedicated remote provider for VPS/network access."
            )
