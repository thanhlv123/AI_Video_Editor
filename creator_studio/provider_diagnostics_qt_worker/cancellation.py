"""M98 thread-safe Qt diagnostics cancellation token.

The cancellation token is a runtime-only synchronization object.

It intentionally contains no:

- provider runtime configuration;
- API credential;
- environment variable value;
- HTTP request or response;
- provider response;
- diagnostic result;
- GUI view model;
- QObject;
- QThread.

The token uses ``threading.Event`` so cancellation may be requested safely
from the GUI/main thread even while the Qt worker thread is busy executing a
long-running diagnostic operation.

``check`` raises the M97 runtime-only cancellation signal when cancellation
has been requested.
"""

import threading

from ..provider_diagnostics_gui_controller.public_api import (
    ProviderDiagnosticsGuiControllerCancelled,
)


class ProviderDiagnosticsQtCancellationToken:
    """One-shot, thread-safe M98 cancellation token."""

    __slots__ = (
        "_event",
    )

    def __init__(
        self,
    ):
        self._event = threading.Event()

    @property
    def is_cancelled(
        self,
    ):
        return self._event.is_set()

    def cancel(
        self,
    ):
        self._event.set()

    def check(
        self,
    ):
        if self._event.is_set():
            raise ProviderDiagnosticsGuiControllerCancelled()

    def __copy__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_qt_cancellation_token_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_diagnostics_qt_cancellation_token_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_qt_cancellation_token_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "ProviderDiagnosticsQtCancellationToken("
            f"is_cancelled={self.is_cancelled!r}"
            ")"
        )