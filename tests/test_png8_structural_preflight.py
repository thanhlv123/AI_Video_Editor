"""Independent synthetic envelopes, executed through the public runtime."""
import hashlib
import io
import struct
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from creator_studio.acquisition.storage import ManagedStorage
from creator_studio.source_snapshot import SourceSnapshotRuntime, SourceSnapshotRequest
from creator_studio.source_observation import SourceByteIdentity
from creator_studio.png8_observer import PNG8PreflightRuntime, PNG8PreflightOutcome
from tests.test_source_snapshot_contract import spec

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def chunk(kind, payload=b""):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)


def ihdr(w=2, h=3, depth=8, color=2, compression=0, filtering=0, interlace=0):
    return chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, depth, color, compression, filtering, interlace))


def phys(x=7, y=7, unit=0):
    return chunk(b"pHYs", struct.pack(">IIB", x, y, unit))


def png(header=None, density=None, ids=None, ending=None):
    return SIGNATURE + (ihdr() if header is None else header) + (phys() if density is None else density) + (chunk(b"IDAT", b"compressed garbage") if ids is None else ids) + (chunk(b"IEND") if ending is None else ending)


def capture(data):
    # M77's existing stream-patching pattern, without creating source files.
    runtime = SourceSnapshotRuntime(str(Path.cwd()))
    digest = hashlib.sha256(data).hexdigest()
    request = SourceSnapshotRequest(SourceByteIdentity("asset:sha256:" + digest, digest, len(data)))
    with patch.object(ManagedStorage, "resolve", return_value=Path("in-memory")), patch.object(Path, "open", return_value=io.BytesIO(data)):
        result, snapshot = runtime.capture(spec(), request)
    if snapshot is None:
        raise AssertionError(result.failure_code)
    return runtime, snapshot


class StructuralTests(unittest.TestCase):
    def run_data(self, data, expected=None):
        runtime, snapshot = capture(data)
        result = PNG8PreflightRuntime().preflight(runtime, snapshot)
        if expected is None:
            self.assertIs(result.outcome, PNG8PreflightOutcome.SUCCESS)
        else:
            self.assertEqual(result.failure_code.value, expected)
            self.assertIsNone(result.descriptor)
            self.assertIsNone(result.profile)
        runtime.release(snapshot)
        return result

    def invalid(self, data):
        return self.run_data(data, "STRUCTURAL_INVALID")

    def test_modes_and_exact_profile(self):
        for color in (0, 2, 4, 6):
            with self.subTest(color=color):
                result = self.run_data(png(header=ihdr(color=color)))
                self.assertEqual(tuple(vars(result.profile).values()), (2, 3, 8, color, 0, 0, 0, 7, 7, 0))
                self.assertEqual(set(vars(result)), {"outcome", "descriptor", "profile", "failure_code"})

    def test_signature(self):
        self.run_data(b"wrong!!!" + png()[8:], "UNSUPPORTED_FORMAT")

    def test_truncations(self):
        for suffix in (b"\0", b"\0\0\0\x01I", b"\0\0\0\x0dIHDRabc", ihdr()[:-1], b"\xff\xff\xff\xffIHDRabcd"):
            with self.subTest(suffix=suffix):
                self.invalid(SIGNATURE + suffix)

    def test_every_crc(self):
        parts = [ihdr(), phys(), chunk(b"IDAT", b"x"), chunk(b"IEND")]
        for i in range(4):
            bad = parts.copy()
            bad[i] = bad[i][:-1] + bytes([bad[i][-1] ^ 1])
            with self.subTest(chunk=i):
                self.invalid(SIGNATURE + b"".join(bad))

    def test_order_and_lengths(self):
        cases = [png(header=phys()), png(density=ihdr() + phys()),
                 png(header=chunk(b"IHDR", b"x")), png(density=b""),
                 png(density=phys() * 2), png(ids=chunk(b"IDAT", b"x") + phys()),
                 png(density=chunk(b"pHYs", b"x")), png(ids=b""),
                 png(ids=chunk(b"IDAT", b"x") + chunk(b"tEXt") + chunk(b"IDAT", b"y")),
                 png(ending=chunk(b"IEND", b"x")), png(ending=b""), png() + b"x"]
        for i, data in enumerate(cases):
            with self.subTest(case=i):
                self.invalid(data)

    def test_phys_semantics(self):
        for args in ((0, 7, 0), (7, 0, 0), (7, 8, 0), (7, 7, 1)):
            with self.subTest(args=args):
                self.invalid(png(density=phys(*args)))

    def test_idat_aggregate(self):
        for payloads in ((b"x",), (b"x", b"y"), (b"", b"x"), (b"x", b"")):
            with self.subTest(payloads=payloads):
                self.run_data(png(ids=b"".join(chunk(b"IDAT", p) for p in payloads)))
        self.invalid(png(ids=chunk(b"IDAT") * 2))

    def test_nonallowlist(self):
        for kind in (b"tRNS", b"PLTE", b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"iCCP", b"gAMA", b"cHRM", b"sRGB", b"acTL", b"fcTL", b"fdAT", b"DDAT", b"zzZZ"):
            with self.subTest(kind=kind):
                self.invalid(png(ids=chunk(kind) + chunk(b"IDAT", b"x")))

    def test_dimensions(self):
        for w, h in ((0, 1), (1, 0)):
            self.invalid(png(header=ihdr(w, h)))
        for w, h in ((4096, 1), (1, 4096), (2000, 2000)):
            self.run_data(png(header=ihdr(w, h)))
        for w, h in ((4097, 1), (1, 4097), (2000, 2001)):
            self.run_data(png(header=ihdr(w, h)), "RESOURCE_LIMIT_EXCEEDED")

    def test_unsupported_encoding(self):
        for depth in (1, 2, 4, 16):
            self.invalid(png(header=ihdr(depth=depth)))
        for color in (1, 3, 5, 7, 255):
            self.invalid(png(header=ihdr(color=color)))
        for key in ("compression", "filtering", "interlace"):
            self.invalid(png(header=ihdr(**{key: 1})))

    def test_precedence(self):
        # Wrong fixed length wins before CRC and dimensions win before encoding.
        self.invalid(png(header=chunk(b"IHDR", b"x")[:-1] + b"x"))
        self.run_data(png(header=ihdr(4097, 1, depth=16)), "RESOURCE_LIMIT_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
