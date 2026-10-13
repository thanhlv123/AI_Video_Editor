"""M96 provider diagnostics view-model contract.

This module defines the final detached provider diagnostics view model intended
for GUI and CLI rendering.

The view model deliberately contains only presentation-oriented data:

- provider label;
- status text;
- detail text;
- view severity;
- recommended view action;
- action button/menu text;
- ready state.

It deliberately does not contain:

- ProviderRuntimeConfig;
- credential values;
- credential objects;
- credential environment variable fields;
- Authorization headers;
- API keys;
- diagnostic reports;
- HTTP status codes;
- provider response codes;
- runtime check callables;
- remote image sources;
- network or execution authority.

This module performs:

- no environment lookup;
- no credential resolution;
- no DNS resolution;
- no network access;
- no provider API request;
- no M91/M92/M93/M94/M95 execution.
"""

from dataclasses import dataclass, fields
from enum import Enum


PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION = 1

MAX_PROVIDER_DIAGNOSTICS_VIEW_PROVIDER_LABEL_LENGTH = 40

MAX_PROVIDER_DIAGNOSTICS_VIEW_STATUS_TEXT_LENGTH = 80

MAX_PROVIDER_DIAGNOSTICS_VIEW_DETAIL_TEXT_LENGTH = 320

MAX_PROVIDER_DIAGNOSTICS_VIEW_ACTION_TEXT_LENGTH = 120


class ProviderDiagnosticsViewSeverity(
    str,
    Enum,
):
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ProviderDiagnosticsViewAction(
    str,
    Enum,
):
    NONE = "NONE"
    REVIEW_CONFIGURATION = "REVIEW_CONFIGURATION"
    CONFIGURE_CREDENTIAL = "CONFIGURE_CREDENTIAL"
    CHECK_CREDENTIAL = "CHECK_CREDENTIAL"
    ADD_REMOTE_SOURCE = "ADD_REMOTE_SOURCE"
    RETRY = "RETRY"
    CHECK_NETWORK = "CHECK_NETWORK"


@dataclass(frozen=True)
class ProviderDiagnosticsViewModel:
    """Detached GUI/CLI-safe provider diagnostics view model."""

    schema_version: int
    provider_label: str
    status_text: str
    detail_text: str
    severity: ProviderDiagnosticsViewSeverity
    action: ProviderDiagnosticsViewAction
    action_text: str
    is_ready: bool


def _validate_exact_shape(
    value,
    expected_type,
):
    if type(value) is not expected_type:
        raise ValueError()

    members = object.__getattribute__(
        value,
        "__dict__",
    )

    names = {
        field.name
        for field in fields(
            expected_type
        )
    }

    if (
        type(members) is not dict
        or len(members) != len(names)
        or any(
            type(key) is not str
            for key in members
        )
        or set(members) != names
    ):
        raise ValueError()


def _validate_text(
    value,
    maximum_length,
):
    if type(value) is not str:
        raise ValueError()

    if (
        not value
        or value != value.strip()
        or len(value) > maximum_length
    ):
        raise ValueError()

    for character in value:
        if not character.isprintable():
            raise ValueError()


def _validate_ready_semantics(
    view_model,
):
    if view_model.is_ready:
        if (
            view_model.severity
            is not ProviderDiagnosticsViewSeverity
            .SUCCESS
        ):
            raise ValueError()

        if (
            view_model.action
            is not ProviderDiagnosticsViewAction
            .NONE
        ):
            raise ValueError()

        return

    if (
        view_model.severity
        is ProviderDiagnosticsViewSeverity
        .SUCCESS
    ):
        raise ValueError()

    if (
        view_model.action
        is ProviderDiagnosticsViewAction
        .NONE
    ):
        raise ValueError()


def validate_provider_diagnostics_view_model(
    view_model,
):
    """Validate one detached M96 provider diagnostics view model."""
    try:
        _validate_exact_shape(
            view_model,
            ProviderDiagnosticsViewModel,
        )

        if (
            type(view_model.schema_version)
            is not int
            or view_model.schema_version
            != PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(view_model.severity)
            is not ProviderDiagnosticsViewSeverity
        ):
            raise ValueError()

        if (
            type(view_model.action)
            is not ProviderDiagnosticsViewAction
        ):
            raise ValueError()

        if (
            type(view_model.is_ready)
            is not bool
        ):
            raise ValueError()

        _validate_text(
            view_model.provider_label,
            MAX_PROVIDER_DIAGNOSTICS_VIEW_PROVIDER_LABEL_LENGTH,
        )

        _validate_text(
            view_model.status_text,
            MAX_PROVIDER_DIAGNOSTICS_VIEW_STATUS_TEXT_LENGTH,
        )

        _validate_text(
            view_model.detail_text,
            MAX_PROVIDER_DIAGNOSTICS_VIEW_DETAIL_TEXT_LENGTH,
        )

        _validate_text(
            view_model.action_text,
            MAX_PROVIDER_DIAGNOSTICS_VIEW_ACTION_TEXT_LENGTH,
        )

        _validate_ready_semantics(
            view_model
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_diagnostics_view_model_invalid"
        ) from None

    return view_model