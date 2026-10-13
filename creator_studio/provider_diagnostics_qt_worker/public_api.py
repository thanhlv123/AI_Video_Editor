"""M98 public API for provider diagnostics Qt execution.

M98 is the Qt runtime boundary above the framework-neutral M97 diagnostics
GUI controller.

The public surface intentionally exposes only:

- the M98 public API version;
- the thread-safe cancellation token;
- the one-shot QObject worker;
- the reusable QThread lifecycle bridge.

No credential, provider transport response, HTTP response, environment value,
M95 application result, M93 report or raw exception is added to this public
surface.
"""

from .bridge import (
    ProviderDiagnosticsQtThreadBridge,
)
from .cancellation import (
    ProviderDiagnosticsQtCancellationToken,
)
from .worker import (
    ProviderDiagnosticsQtWorker,
)


PROVIDER_DIAGNOSTICS_QT_WORKER_PUBLIC_API_VERSION = 1


__all__ = (
    "PROVIDER_DIAGNOSTICS_QT_WORKER_PUBLIC_API_VERSION",
    "ProviderDiagnosticsQtCancellationToken",
    "ProviderDiagnosticsQtThreadBridge",
    "ProviderDiagnosticsQtWorker",
)