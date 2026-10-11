"""Shared rights vocabulary; discovery hints do not establish permission."""
from enum import Enum


class Rights(str, Enum):
    OWNED = "OWNED"
    LICENSED = "LICENSED"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    UNKNOWN = "UNKNOWN"
