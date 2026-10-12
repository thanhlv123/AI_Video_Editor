"""Offline managed filesystem adversaries, race and cancellation coverage."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch

from creator_studio.acquisition.storage import ManagedStorage, RunBudget, BoundedSink
from creator_studio.acquisition.models import AcquisitionError
from creator_studio.orchestrator.contracts import CancellationToken, Cancelled
from creator_studio.manifest.acquisition import *
from creator_studio.manifest import validate
from tests import test_media_acquisition as fixtures


class AcquisitionStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = ManagedStorage(Path(self.temp.name) / "managed")
        self.control = CancellationToken()
        self.data = b"offline synthetic object"

    def install(self, data=None, barrier=None):
        data = self.data if data is None else data
        with self.storage.staging(self.control, 10000, RunBudget(10000)) as (path, sink):
            self.assertEqual(path.parent, self.storage.root / "staging")
            sink.write(data)
            sink.finish()
            digest, count = self.storage.hash_file(path, self.control, 10000)
            if barrier:
                barrier.wait(timeout=5)
            return self.storage.finalize(path, digest, count, self.control)

    def test_success_no_clobber(self):
        first = self.install()
        path = self.storage.resolve(first.object_key)
        before = path.stat()
        second = self.install()
        self.assertEqual(first, second)
        self.assertEqual(path.read_bytes(), self.data)
        self.assertEqual(before.st_ino, path.stat().st_ino)
        self.assertFalse(list((self.storage.root / "staging").glob("*")))

    def test_corrupt_existing_never_overwritten(self):
        asset = self.install()
        path = self.storage.resolve(asset.object_key)
        path.write_bytes(b"corrupt")
        with self.assertRaises(AcquisitionError):
            self.install()
        self.assertEqual(path.read_bytes(), b"corrupt")

    def test_same_size_corrupt_existing_rejected(self):
        asset = self.install()
        path = self.storage.resolve(asset.object_key)
        path.write_bytes(b"x" * len(self.data))
        with self.assertRaises(AcquisitionError):
            self.storage.verify(asset, self.control)

    def test_directory_object_rejected(self):
        digest = hashlib.sha256(self.data).hexdigest()
        path = self.storage.root / object_key(digest)
        path.mkdir(parents=True)
        with self.assertRaises(AcquisitionError):
            self.install()

    def test_symlink_object_rejected(self):
        digest = hashlib.sha256(self.data).hexdigest()
        path = self.storage.root / object_key(digest)
        path.parent.mkdir(parents=True)
        target = Path(self.temp.name) / "outside"
        target.write_bytes(self.data)
        try:
            path.symlink_to(target)
        except OSError:
            self.skipTest("Windows symlink privilege unavailable; reparse flag test still runs")
        with self.assertRaises(AcquisitionError):
            self.install()
        self.assertEqual(target.read_bytes(), self.data)

    def test_reparse_attribute_rejected(self):
        from creator_studio.acquisition.storage import regular
        class FakeStat:
            st_mode = 0o100644
            st_file_attributes = 0x400
        with patch.object(Path, "lstat", return_value=FakeStat()):
            with self.assertRaises(AcquisitionError):
                regular(Path("unused"))

    def test_symlink_parent_rejected(self):
        self.storage.root.mkdir()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        try:
            (self.storage.root / "objects").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Windows symlink privilege unavailable")
        with self.assertRaises(AcquisitionError):
            self.install()

    def test_concurrent_identical_installation(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.install(barrier=barrier), range(2)))
        self.assertEqual(results[0], results[1])
        self.storage.verify(results[0], self.control)
        self.assertEqual(len(list(self.storage.root.glob("objects/sha256/*/*.blob"))), 1)

    def test_loser_verifies_winner(self):
        self.install()
        with patch.object(self.storage, "verify", wraps=self.storage.verify) as verify:
            self.install()
            self.assertGreaterEqual(verify.call_count, 2)

    def test_corrupt_race_winner_not_overwritten(self):
        real_link = os.link
        def corrupt_link(source, target):
            Path(target).write_bytes(b"bad winner")
            raise FileExistsError()
        with patch("creator_studio.acquisition.storage.os.link", side_effect=corrupt_link):
            with self.assertRaises(AcquisitionError):
                self.install()
        objects = list(self.storage.root.glob("objects/sha256/*/*.blob"))
        self.assertEqual(objects[0].read_bytes(), b"bad winner")

    def test_cancellation_stream_cleans_temp(self):
        with self.assertRaises(Cancelled):
            with self.storage.staging(self.control, 10000, RunBudget(10000)) as (path, sink):
                self.control.cancel()
                sink.write(self.data)
        self.assertFalse(list((self.storage.root / "staging").glob("*")))

    def test_cancel_before_staging_no_tree(self):
        self.control.cancel()
        with self.assertRaises(Cancelled):
            self.install()
        self.assertFalse(self.storage.root.exists())

    def test_cancel_hash(self):
        asset = self.install()
        self.control.cancel()
        with self.assertRaises(Cancelled):
            self.storage.verify(asset, self.control)

    def test_empty_asset(self):
        with self.storage.staging(self.control, 10000, RunBudget(10000)) as (path, sink):
            sink.finish()
            with self.assertRaises(AcquisitionError):
                self.storage.hash_file(path, self.control, 10000)

    def test_short_write_fails(self):
        class ShortWriter:
            def write(self, chunk):
                return len(chunk) - 1
        sink = BoundedSink(ShortWriter(), self.control, 10000, RunBudget(10000))
        with self.assertRaises(AcquisitionError):
            sink.write(self.data)

    def test_disk_failure_sanitized(self):
        class BrokenWriter:
            def write(self, chunk):
                raise OSError("private filesystem path")
        sink = BoundedSink(BrokenWriter(), self.control, 10000, RunBudget(10000))
        with self.assertRaises(AcquisitionError) as caught:
            sink.write(self.data)
        self.assertEqual(str(caught.exception), "acquisition_storage_failed")

    def test_asset_byte_limit(self):
        with self.storage.staging(self.control, 1, RunBudget(10000)) as (_, sink):
            with self.assertRaises(AcquisitionError):
                sink.write(self.data)

    def test_aggregate_byte_limit(self):
        budget = RunBudget(len(self.data))
        with self.storage.staging(self.control, 10000, budget) as (_, sink):
            sink.write(self.data)
        with self.storage.staging(self.control, 10000, budget) as (_, sink):
            with self.assertRaises(AcquisitionError):
                sink.write(b"x")

    def test_chunk_bound(self):
        with self.storage.staging(self.control, MAX_ASSET_BYTES, RunBudget(MAX_ASSET_BYTES)) as (_, sink):
            with self.assertRaises(AcquisitionError):
                sink.write(b"x" * (MAX_TRANSFER_CHUNK + 1))

    def test_sink_no_destination_api(self):
        with self.storage.staging(self.control, 10000, RunBudget(10000)) as (_, sink):
            for name in ("path", "name", "destination", "fileno"):
                self.assertFalse(hasattr(sink, name))

    def test_unrelated_and_inactive_objects_never_gc(self):
        first = self.install()
        other = self.install(b"other bytes")
        unknown = self.storage.root / "unknown.data"
        unknown.write_bytes(b"leave alone")
        foreign_temp = self.storage.root / "staging" / "foreign.part"
        foreign_temp.write_bytes(b"leave alone")
        self.install()
        self.assertTrue(self.storage.resolve(first.object_key).exists())
        self.assertTrue(self.storage.resolve(other.object_key).exists())
        self.assertTrue(unknown.exists())
        self.assertTrue(foreign_temp.exists())

    def test_hash_full_bytes_not_mtime(self):
        asset = self.install()
        path = self.storage.resolve(asset.object_key)
        metadata = path.stat()
        path.write_bytes(b"x" * asset.byte_count)
        os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        with self.assertRaises(AcquisitionError):
            self.storage.verify(asset, self.control)


def invalid_key_test(key):
    def test(self):
        with self.assertRaises(AcquisitionError):
            self.storage.resolve(key)
        self.assertFalse(self.storage.root.exists())
    return test


for _i, _key in enumerate(("../escape", "..\\escape", "C:\\escape", "C:escape", "\\\\server\\share",
    "\\\\?\\C:\\escape", "/absolute/path", "filename:stream", "CON", "PRN", "AUX", "NUL",
    "COM1", "COM9", "LPT1", "LPT9", "file.", "file ", "objects\\sha256\\aa\\file.blob",
    "objects/sha256/aa/" + "a" * 64 + ".blob/extra", "objects/sha256/ab/" + "a" * 64 + ".blob",
    "objects/sha256/AA/" + "A" * 64 + ".blob", "objects\u2215sha256\u2215aa\u2215bad")):
    setattr(AcquisitionStorageTests, f"test_reject_key_{_i:02d}", invalid_key_test(_key))


class MutationUsabilityTests(fixtures.MediaAcquisitionTests):
    """Only mutation-specific cases are inherited below via explicit construction."""
    def test_deleted_history_valid_current_false(self):
        m = self.build()
        self.storage.resolve(m.acquisition.assets[0].object_key).unlink()
        self.assertFalse(validate(m))
        self.assertFalse(self.usable(m))

    def test_truncated_history_valid_current_false(self):
        m = self.build()
        self.storage.resolve(m.acquisition.assets[0].object_key).write_bytes(b"x")
        self.assertFalse(validate(m))
        self.assertFalse(self.usable(m))

    def test_overwritten_history_valid_current_false(self):
        m = self.build()
        self.storage.resolve(m.acquisition.assets[0].object_key).write_bytes(b"x" * m.acquisition.assets[0].byte_count)
        self.assertFalse(validate(m))
        self.assertFalse(self.usable(m))


# Share fixture helpers without rerunning the domain suite in this module.
for _name in dir(fixtures.MediaAcquisitionTests):
    if _name.startswith("test_") and _name not in MutationUsabilityTests.__dict__:
        setattr(MutationUsabilityTests, _name, None)


if __name__ == "__main__":
    unittest.main()
