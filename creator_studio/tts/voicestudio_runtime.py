from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlparse

import requests


class VoiceStudioLocalRuntimeManager:
    """Discover/start the locally installed VoiceStudio Electron runtime.

    VoiceStudio 0.5.6 can move its managed backend away from port 3900 when
    Windows reserves or blocks that port. Electron tries fallback loopback ports
    in +1000 increments. This manager mirrors that discovery behaviour instead
    of assuming 3900 forever.
    """

    DEFAULT_PORT = 3900
    FALLBACK_COUNT = 16

    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        launcher: Callable[[Path], None] | None = None,
        min_restart_interval_seconds: float = 15.0,
    ) -> None:
        self._env = dict(environment or os.environ)
        self._launcher = launcher or self._default_launcher
        self._min_restart_interval_seconds = float(min_restart_interval_seconds)
        self._last_launch_at = 0.0
        self._last_executable: Path | None = None
        self._last_backend_url: str | None = None

    @property
    def last_executable(self) -> Path | None:
        return self._last_executable

    @property
    def last_backend_url(self) -> str | None:
        return self._last_backend_url

    def candidate_backend_urls(self) -> tuple[str, ...]:
        values: list[str] = []

        explicit_url = str(
            self._env.get("VOICESTUDIO_URL")
            or self._env.get("OMNIVOICE_API_URL")
            or ""
        ).strip().rstrip("/")
        if explicit_url and self._is_loopback_url(explicit_url):
            values.append(explicit_url)

        explicit_port = str(self._env.get("OMNIVOICE_PORT") or "").strip()
        if explicit_port.isdigit():
            port = int(explicit_port)
            if 1 <= port <= 65535:
                values.append(f"http://127.0.0.1:{port}")

        # VoiceStudio Electron uses 3900 first, then +1000 fallback ports.
        for index in range(self.FALLBACK_COUNT + 1):
            port = self.DEFAULT_PORT + (index * 1000)
            if port <= 65535:
                values.append(f"http://127.0.0.1:{port}")

        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return tuple(result)

    def discover_backend_url(self, *, timeout_seconds: float = 0.55) -> str | None:
        # Fast path: reuse last proven endpoint.
        if self._last_backend_url and self._probe_backend(
            self._last_backend_url, timeout_seconds=timeout_seconds
        ):
            return self._last_backend_url

        for base_url in self.candidate_backend_urls():
            if self._probe_backend(base_url, timeout_seconds=timeout_seconds):
                self._last_backend_url = base_url
                return base_url
        return None

    def discover_executable(self) -> Path | None:
        override = str(self._env.get("VOICESTUDIO_EXE", "") or "").strip().strip('"')
        if override:
            path = Path(override).expanduser()
            if path.is_file():
                return path.resolve()

        registry_path = self._discover_from_windows_registry()
        if registry_path is not None:
            return registry_path

        for candidate in self._common_candidates():
            if candidate.is_file():
                return candidate.resolve()

        return None

    def start(self) -> tuple[bool, str]:
        existing = self.discover_backend_url(timeout_seconds=0.35)
        if existing:
            return True, f"VoiceStudio backend đã chạy · {existing}"

        executable = self.discover_executable()
        if executable is None:
            return False, (
                "Không tìm thấy VoiceStudio đã cài trên máy. Hãy mở VoiceStudio thủ công "
                "hoặc đặt biến môi trường VOICESTUDIO_EXE trỏ tới VoiceStudio.exe."
            )

        now = time.monotonic()
        if now - self._last_launch_at < self._min_restart_interval_seconds:
            return True, f"Đang chờ VoiceStudio khởi động · {executable}"

        try:
            self._launcher(executable)
        except Exception as exc:
            return False, f"Không thể khởi động VoiceStudio: {type(exc).__name__}: {exc}"

        self._last_launch_at = now
        self._last_executable = executable
        return True, f"Đã yêu cầu khởi động VoiceStudio · {executable}"

    def _probe_backend(self, base_url: str, *, timeout_seconds: float) -> bool:
        # Prefer VoiceStudio's explicit discovery document. It is cheap and
        # prevents attaching to an unrelated service that happens to expose
        # /health on one of the fallback ports.
        try:
            response = requests.get(
                f"{base_url}/.well-known/voicestudio-speech",
                timeout=(timeout_seconds, timeout_seconds),
            )
            if response.status_code == 200:
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                if self._looks_like_voicestudio_discovery(payload):
                    return True
        except requests.RequestException:
            pass

        # Compatibility fallback for builds where the discovery document is
        # unavailable but the OpenAI-compatible voice route is present.
        try:
            response = requests.get(
                f"{base_url}/v1/audio/voices",
                timeout=(timeout_seconds, timeout_seconds),
            )
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, dict) and "voices" in payload and "engines" in payload:
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _looks_like_voicestudio_discovery(payload) -> bool:
        if isinstance(payload, dict):
            text = " ".join(str(v) for v in payload.values()).lower()
            if "voicestudio.speech.v1" in text:
                return True
            # Some builds expose the protocol in nested structures.
            try:
                import json
                return "voicestudio.speech.v1" in json.dumps(payload).lower()
            except Exception:
                return False
        return False

    @staticmethod
    def _is_loopback_url(value: str) -> bool:
        try:
            parsed = urlparse(value)
        except Exception:
            return False
        return parsed.scheme in {"http", "https"} and parsed.hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
        }

    def _common_candidates(self) -> tuple[Path, ...]:
        local = Path(self._env.get("LOCALAPPDATA", "")) if self._env.get("LOCALAPPDATA") else None
        program_files = Path(self._env.get("ProgramFiles", "")) if self._env.get("ProgramFiles") else None
        program_files_x86 = Path(self._env.get("ProgramFiles(x86)", "")) if self._env.get("ProgramFiles(x86)") else None

        roots = [root for root in (local, program_files, program_files_x86) if root]
        candidates: list[Path] = []
        for root in roots:
            if local is not None and root == local:
                programs = root / "Programs"
                bases = (
                    programs / "VoiceStudio",
                    programs / "Voice Studio",
                    programs / "voicestudio",
                    programs / "VoiceStudio Electron",
                )
            else:
                bases = (
                    root / "VoiceStudio",
                    root / "Voice Studio",
                    root / "VoiceStudio Electron",
                )

            for base in bases:
                candidates.extend(
                    [
                        base / "VoiceStudio.exe",
                        base / "Voice Studio.exe",
                        base / "VoiceStudio Electron.exe",
                    ]
                )

        return tuple(candidates)

    def _discover_from_windows_registry(self) -> Path | None:
        if sys.platform != "win32":
            return None

        try:
            import winreg
        except Exception:
            return None

        uninstall_paths = (
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        )
        roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)

        for root in roots:
            for uninstall_path in uninstall_paths:
                try:
                    with winreg.OpenKey(root, uninstall_path) as parent:
                        index = 0
                        while True:
                            try:
                                sub_name = winreg.EnumKey(parent, index)
                            except OSError:
                                break
                            index += 1
                            try:
                                with winreg.OpenKey(parent, sub_name) as sub:
                                    display_name = self._read_reg_value(winreg, sub, "DisplayName")
                                    if "voicestudio" not in display_name.lower().replace(" ", ""):
                                        continue

                                    display_icon = self._read_reg_value(winreg, sub, "DisplayIcon")
                                    icon_path = self._path_from_display_icon(display_icon)
                                    if icon_path is not None and icon_path.is_file():
                                        return icon_path.resolve()

                                    install_location = self._read_reg_value(winreg, sub, "InstallLocation")
                                    if install_location:
                                        base = Path(install_location.strip().strip('"'))
                                        for name in (
                                            "VoiceStudio.exe",
                                            "Voice Studio.exe",
                                            "VoiceStudio Electron.exe",
                                        ):
                                            candidate = base / name
                                            if candidate.is_file():
                                                return candidate.resolve()
                            except OSError:
                                continue
                except OSError:
                    continue

        return None

    @staticmethod
    def _read_reg_value(winreg, key, name: str) -> str:
        try:
            value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            return ""
        return str(value or "")

    @staticmethod
    def _path_from_display_icon(value: str) -> Path | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.startswith('"'):
            closing = text.find('"', 1)
            raw = text[1:closing] if closing > 1 else text.strip('"')
        else:
            raw = text.split(",", 1)[0]
        raw = raw.strip().strip('"')
        return Path(raw) if raw else None

    @staticmethod
    def _default_launcher(executable: Path) -> None:
        if sys.platform != "win32" or not hasattr(os, "startfile"):
            raise RuntimeError("Tự khởi động VoiceStudio hiện chỉ hỗ trợ Windows desktop")
        os.startfile(str(executable))
