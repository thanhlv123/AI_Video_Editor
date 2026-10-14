"""M100 GUI diagnostics remote-image runtime marker.

Provider diagnostics M91 validates that KIE runtime metadata includes the
runtime shape required by the M89 remote-image contract. M93 diagnostics
itself never serializes a vision request and never invokes remote-image
resolution; ONLINE mode performs only the M92 authenticated connectivity
probe after M91 readiness succeeds.

This runtime-only object satisfies the M91 dependency-shape boundary without
granting media upload/publishing authority to the GUI diagnostics path.

If it is ever used as an actual M89 image source, resolution fails closed.
"""

from ..provider_specific_vision_adapter import (
    ProviderVisionRemoteImageSource,
)


class ProviderDiagnosticsRemoteImageSource(
    ProviderVisionRemoteImageSource
):
    """Diagnostics-only M89 dependency marker; actual resolution is forbidden."""

    __slots__ = ()

    def resolve(
        self,
        request,
        check,
    ):
        if not callable(
            check
        ):
            raise RuntimeError(
                "provider_diagnostics_remote_image_source_invalid_check"
            )

        check()

        raise RuntimeError(
            "provider_diagnostics_remote_image_resolution_forbidden"
        )

    def __copy__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_remote_image_source_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_diagnostics_remote_image_source_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_remote_image_source_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "ProviderDiagnosticsRemoteImageSource()"
        )
