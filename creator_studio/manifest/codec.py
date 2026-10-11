"""Strict recursive JSON contracts; unknown fields are never silently discarded."""
from dataclasses import fields, is_dataclass
from enum import Enum
import math
from types import UnionType
from typing import get_args, get_origin, get_type_hints


def normalize_float_fields(value):
    for name, annotation in get_type_hints(type(value)).items():
        if annotation is float or float in get_args(annotation):
            item = getattr(value, name)
            if item is None and type(None) in get_args(annotation):
                continue
            setattr(value, name, decode(float, item, name))


def check_typed(cls, value, path="manifest"):
    """Check the actual object graph without reconstructing or mutating it."""
    origin, args = get_origin(cls), get_args(cls)
    if origin is UnionType:
        for option in args:
            try:
                check_typed(option, value, path)
                return
            except ValueError:
                pass
        raise ValueError(f"{path}: invalid optional value")
    if origin is list:
        if type(value) is not list:
            raise ValueError(f"{path}: expected list")
        for i, item in enumerate(value):
            check_typed(args[0], item, f"{path}[{i}]")
        return
    if is_dataclass(cls):
        if type(value) is not cls:
            raise ValueError(f"{path}: expected {cls.__name__}")
        for name, annotation in get_type_hints(cls).items():
            if not hasattr(value, name):
                raise ValueError(f"{path}.{name}: missing field")
            check_typed(annotation, getattr(value, name), f"{path}.{name}")
        return
    if cls is float:
        decode(float, value, path)
        return
    if type(value) is not cls:
        raise ValueError(f"{path}: invalid field type")


def to_data(value):
    if is_dataclass(value):
        check_typed(type(value), value)
        hints = get_type_hints(type(value))
        return {f.name: to_data(decode(float, getattr(value, f.name), f.name)
                               if (hints[f.name] is float or float in get_args(hints[f.name]))
                               and getattr(value, f.name) is not None
                               else getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [to_data(v) for v in value]
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise ValueError("Object keys must be strings")
        return {k: to_data(v) for k, v in value.items()}
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("Unsupported or non-finite structured value")


def decode(cls, value, path="manifest"):
    origin, args = get_origin(cls), get_args(cls)
    if origin is UnionType:
        for option in args:
            try:
                return decode(option, value, path)
            except ValueError:
                pass
        raise ValueError(f"{path}: invalid optional value")
    if origin is list:
        if type(value) is not list:
            raise ValueError(f"{path}: expected array")
        return [decode(args[0], v, f"{path}[{i}]") for i, v in enumerate(value)]
    if isinstance(cls, type) and issubclass(cls, Enum):
        try:
            return cls(value)
        except (ValueError, TypeError):
            raise ValueError(f"{path}: unsupported enum value") from None
    if is_dataclass(cls):
        if type(value) is not dict:
            raise ValueError(f"{path}: expected object")
        hints = get_type_hints(cls)
        # Persisted contracts require all fields, including IDs. Never mint IDs on load.
        if set(value) != set(hints):
            raise ValueError(f"{path}: missing or unknown fields")
        return cls(**{k: decode(hints[k], v, f"{path}.{k}") for k, v in value.items()})
    if cls is float and type(value) in (int, float):
        try:
            number = float(value)
            if math.isfinite(number):
                return number
        except OverflowError:
            pass
    if cls is not float and type(value) is cls:
        return value
    raise ValueError(f"{path}: invalid field type")
