from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import unicodedata
import wave
from pathlib import Path
from typing import Sequence

from ..models import (
    TTSProviderInfo,
    TTSProviderUnavailableError,
    TTSSynthesisError,
    TTSSynthesisRequest,
    TTSSynthesisResult,
    TTSVoice,
)


class PiperProcessProvider:
    """Piper adapter executed in a dedicated Python runtime/process.

    The Creator Studio process never imports Piper itself. This keeps the
    provider replaceable and makes a later VPS worker/container migration
    straightforward.
    """

    PROVIDER_ID = "piper_local"

    def __init__(
        self,
        *,
        python_executable: str | Path,
        voices_root: str | Path,
        worker_module: str = "creator_studio.tts.providers.piper_worker",
        project_root: str | Path | None = None,
        timeout_seconds: int = 900,
        max_text_characters: int = 500_000,
    ) -> None:
        self.python_executable = Path(python_executable).resolve()
        self.voices_root = Path(voices_root).resolve()
        self.worker_module = worker_module
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[3]
        )
        self.timeout_seconds = int(timeout_seconds)
        self.max_text_characters = int(max_text_characters)

    @property
    def info(self) -> TTSProviderInfo:
        return TTSProviderInfo(
            provider_id=self.PROVIDER_ID,
            display_name="Piper Local",
            is_local=True,
            supports_voice_cloning=False,
            supports_preview=True,
        )

    def health_check(self) -> tuple[bool, str]:
        if not self.python_executable.is_file():
            return False, f"Không tìm thấy Piper Python: {self.python_executable}"

        if not self.voices_root.is_dir():
            return False, f"Chưa có thư mục giọng Piper: {self.voices_root}"

        voices = self.list_voices()
        if not voices:
            return False, "Chưa cài giọng Piper nào."

        check = subprocess.run(
            [
                str(self.python_executable),
                "-c",
                (
                    "import importlib.util; "
                    "raise SystemExit(0 if importlib.util.find_spec('piper') else 2)"
                ),
            ],
            cwd=str(self.project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
        if check.returncode != 0:
            return False, "Runtime Piper chưa cài package piper-tts."

        return True, f"Sẵn sàng · {len(voices)} giọng Piper"

    def list_voices(self) -> Sequence[TTSVoice]:
        if not self.voices_root.exists():
            return ()

        voices: list[TTSVoice] = []
        for model_path in sorted(self.voices_root.rglob("*.onnx")):
            config_path = Path(str(model_path) + ".json")
            if not config_path.is_file():
                continue

            voice_id = model_path.stem
            language = self._language_from_voice_id(voice_id)
            quality = self._quality_from_voice_id(voice_id)
            display_name = voice_id

            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                dataset = data.get("dataset")
                if isinstance(dataset, str) and dataset.strip():
                    display_name = f"{voice_id} · {dataset.strip()}"
                language_data = data.get("language")
                if isinstance(language_data, dict):
                    code = language_data.get("code")
                    if isinstance(code, str) and code.strip():
                        language = code.strip()
            except Exception:
                pass

            voices.append(
                TTSVoice(
                    provider_id=self.PROVIDER_ID,
                    voice_id=voice_id,
                    display_name=display_name,
                    language=language,
                    quality=quality,
                    model_path=str(model_path),
                    config_path=str(config_path),
                )
            )

        return tuple(voices)

    def synthesize(self, request: TTSSynthesisRequest) -> TTSSynthesisResult:
        if request.provider_id != self.PROVIDER_ID:
            raise ValueError(
                f"Request provider mismatch: {request.provider_id!r}"
            )

        text = self._sanitize_text(request.text)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must not be empty")
        if len(text) > self.max_text_characters:
            raise ValueError(
                f"text exceeds Piper limit of {self.max_text_characters} characters"
            )
        if not (0.25 <= request.speed <= 4.0):
            raise ValueError("speed must be between 0.25 and 4.0")
        if not (0.05 <= request.volume <= 4.0):
            raise ValueError("volume must be between 0.05 and 4.0")

        healthy, detail = self.health_check()
        if not healthy:
            raise TTSProviderUnavailableError(detail)

        voice = next(
            (item for item in self.list_voices() if item.voice_id == request.voice_id),
            None,
        )
        if voice is None or voice.model_path is None:
            raise ValueError(f"Unknown Piper voice: {request.voice_id}")

        output_path = Path(request.output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() != ".wav":
            raise ValueError("PiperProcessProvider currently outputs WAV only")

        temp_path = output_path.with_name(
            output_path.stem + ".tts-working.wav"
        )
        if temp_path.exists():
            temp_path.unlink()

        command = [
            str(self.python_executable),
            "-m",
            self.worker_module,
            "--model",
            voice.model_path,
            "--config",
            voice.config_path or "",
            "--output",
            str(temp_path),
            "--speed",
            str(request.speed),
            "--volume",
            str(request.volume),
        ]
        if request.speaker_id is not None:
            command.extend(["--speaker-id", str(request.speaker_id)])

        try:
            completed = subprocess.run(
                command,
                input=text,
                text=True,
                encoding="utf-8",
                cwd=str(self.project_root),
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self._safe_unlink(temp_path)
            raise TTSSynthesisError(
                f"Piper synthesis timed out after {self.timeout_seconds} seconds"
            ) from exc
        except OSError as exc:
            self._safe_unlink(temp_path)
            raise TTSSynthesisError("Could not start Piper worker") from exc

        if completed.returncode != 0:
            self._safe_unlink(temp_path)
            detail = self._safe_error_text(completed.stderr)
            raise TTSSynthesisError(
                f"Piper synthesis failed (code {completed.returncode})"
                + (f": {detail}" if detail else "")
            )

        if not temp_path.is_file() or temp_path.stat().st_size <= 44:
            self._safe_unlink(temp_path)
            raise TTSSynthesisError("Piper returned no valid WAV output")

        duration = self._wav_duration(temp_path)
        os.replace(temp_path, output_path)

        return TTSSynthesisResult(
            provider_id=self.PROVIDER_ID,
            voice_id=request.voice_id,
            output_path=output_path,
            duration_seconds=duration,
            byte_count=output_path.stat().st_size,
        )

    @staticmethod
    def _language_from_voice_id(voice_id: str) -> str | None:
        parts = voice_id.split("-")
        if not parts:
            return None
        prefix = parts[0]
        return prefix if "_" in prefix else None

    @staticmethod
    def _quality_from_voice_id(voice_id: str) -> str | None:
        for value in ("x_low", "low", "medium", "high"):
            if voice_id.endswith("-" + value):
                return value
        return None

    @staticmethod
    def _wav_duration(path: Path) -> float:
        with wave.open(str(path), "rb") as wav_file:
            rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            if rate <= 0:
                return 0.0
            return frames / float(rate)

    @staticmethod
    def _sanitize_text(value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("text must be a string")

        # QTextEdit may preserve a lone UTF-16 surrogate pasted from a damaged
        # source. Python's UTF-8 encoder rejects these code points before Piper
        # can synthesize the text. Replace only invalid surrogate code points;
        # keep normal Unicode punctuation and multilingual text unchanged.
        cleaned = "".join(
            " " if 0xD800 <= ord(char) <= 0xDFFF else char
            for char in value
        )
        return unicodedata.normalize("NFC", cleaned)

    @staticmethod
    def _safe_error_text(value: str | None) -> str:
        if not value:
            return ""

        lines = [line.strip() for line in value.splitlines() if line.strip()]
        # Prefer the actual exception summary instead of dumping a full Windows
        # traceback into a QMessageBox. The detailed stderr is still available
        # to the caller if needed during development.
        for line in reversed(lines):
            lowered = line.lower()
            if (
                "error:" in lowered
                or "exception:" in lowered
                or "valueerror:" in lowered
                or "runtimeerror:" in lowered
                or "unicode" in lowered
            ):
                return line[-900:]

        return (" ".join(lines))[-900:]

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
