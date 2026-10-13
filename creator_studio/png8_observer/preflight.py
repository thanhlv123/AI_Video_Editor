"""Private bounded PNG envelope parser. No raster interpretation."""
import struct
import zlib
from ..still_image_observation_method import (
    EncodedStillImageProfile, MAX_CODED_AXIS, MAX_DECODED_PIXELS,
)
from .models import PNG8PreflightFailureCode as Failure


class _PreflightFailure(Exception):
    def __init__(self, code):
        self.code = code


def _parse(data, check):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise _PreflightFailure(Failure.UNSUPPORTED_FORMAT)
    offset, state, aggregate = 8, 0, 0
    header = phys = None
    view = memoryview(data)
    region = None
    try:
        check()
        while offset < len(data):
            check()
            remaining = len(data) - offset
            if remaining < 12:
                raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
            length = int.from_bytes(data[offset:offset + 4], "big")
            if length > remaining - 12:
                raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
            start = offset + 8
            end = start + length
            next_offset = end + 4
            kind = data[offset + 4:start]
            legal = ((state == 0 and kind == b"IHDR")
                     or (state == 1 and kind == b"pHYs")
                     or (state == 2 and kind == b"IDAT")
                     or (state == 3 and kind in (b"IDAT", b"IEND")))
            if not legal:
                raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
            fixed = {b"IHDR": 13, b"pHYs": 9, b"IEND": 0}
            if kind in fixed and length != fixed[kind]:
                raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
            check()
            region = view[offset + 4:end]
            crc = zlib.crc32(region) & 0xFFFFFFFF
            region.release()
            region = None
            check()
            if crc != int.from_bytes(data[end:next_offset], "big"):
                raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
            if kind == b"IHDR":
                header = struct.unpack_from(">IIBBBBB", data, start)
                w, h, depth, color, compression, filtering, interlace = header
                if w == 0 or h == 0:
                    raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
                if w > MAX_CODED_AXIS or h > MAX_CODED_AXIS or w * h > MAX_DECODED_PIXELS:
                    raise _PreflightFailure(Failure.RESOURCE_LIMIT_EXCEEDED)
                if depth != 8 or color not in (0, 2, 4, 6) or (compression, filtering, interlace) != (0, 0, 0):
                    raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
                state = 1
            elif kind == b"pHYs":
                phys = struct.unpack_from(">IIB", data, start)
                x, y, unit = phys
                if x == 0 or y == 0 or x != y or unit != 0:
                    raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
                state = 2
            elif kind == b"IDAT":
                # Each bounded payload belongs to the input, so this sum cannot
                # exceed its length; no payload copying or concatenation.
                aggregate += length
                state = 3
            else:
                if next_offset != len(data):
                    raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
                state = 4
            offset = next_offset
        if state != 4 or aggregate == 0:
            raise _PreflightFailure(Failure.STRUCTURAL_INVALID)
        return EncodedStillImageProfile(*header, *phys)
    finally:
        if region is not None:
            region.release()
        view.release()
