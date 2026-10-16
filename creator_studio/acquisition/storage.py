"""Managed digest-only storage, bounded streaming and atomic no-clobber publication."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
from ..manifest.acquisition import MAX_TRANSFER_CHUNK, MaterializedAsset, object_key
from .models import AcquisitionError


def regular(path, directory=False):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise AcquisitionError("acquisition_storage_failed")


class RunBudget:
    def __init__(self, limit):
        self.limit, self.used = limit, 0


class BoundedSink:
    __slots__ = ("__stream", "__control", "__limit", "__budget", "__failure", "count", "digest")

    def __init__(self, stream, control, limit, budget):
        self.__stream, self.__control = stream, control
        self.__limit, self.__budget = limit, budget
        self.__failure = None
        self.count, self.digest = 0, hashlib.sha256()

    def write(self, chunk):
        self.__control.check()
        if self.__failure:
            raise AcquisitionError(self.__failure)
        if type(chunk) is not bytes or not 0 < len(chunk) <= MAX_TRANSFER_CHUNK:
            self.__failure = "acquisition_limit_exceeded"
            raise AcquisitionError("acquisition_limit_exceeded")
        if self.count + len(chunk) > self.__limit or self.__budget.used + len(chunk) > self.__budget.limit:
            self.__failure = "acquisition_limit_exceeded"
            raise AcquisitionError("acquisition_limit_exceeded")
        try:
            written = self.__stream.write(chunk)
            if written != len(chunk):
                raise OSError()
        except Exception:
            self.__failure = "acquisition_storage_failed"
            raise AcquisitionError("acquisition_storage_failed") from None
        self.count += written
        self.__budget.used += written
        self.digest.update(chunk)
        self.__control.check()
        return written

    @property
    def failure_code(self):
        return self.__failure

    def finish(self):
        self.__stream.flush()
        os.fsync(self.__stream.fileno())
        self.__stream.close()


class ManagedStorage:
    """Root is trusted runtime configuration, never a persistent identity field.

    The managed tree must not be concurrently modified by untrusted local actors.
    Object publication races between cooperating acquisition workers are supported.
    """
    def __init__(self, root):
        self.root = Path(os.path.abspath(root))

    def _check(self, path, *, final=False):
        try:
            # The configured managed root is the trust boundary. Inspect the
            # root and descendants only; parents outside the root belong to the
            # host/runtime and may legitimately use Windows aliases or reparse
            # points (for example GitHub Actions temporary directories).
            relative = path.relative_to(self.root)
            chain = [self.root]
            current = self.root
            for part_name in relative.parts:
                current = current / part_name
                chain.append(current)

            for part in chain:
                if part.exists() or part.is_symlink():
                    regular(part, directory=(part != path or not final))

            # Resolve both sides to reject traversal and any descendant reparse
            # point that escapes the managed root.
            path.resolve().relative_to(self.root.resolve())
        except Exception:
            raise AcquisitionError("acquisition_storage_failed") from None

    def _directory(self, path):
        self._check(path)
        path.mkdir(parents=True, exist_ok=True)
        self._check(path)

    def resolve(self, key):
        if type(key) is not str or not re.fullmatch(r"objects/sha256/[0-9a-f]{2}/[0-9a-f]{64}\.blob", key):
            raise AcquisitionError("acquisition_storage_failed")
        digest = key.rsplit("/", 1)[1][:-5]
        if key != object_key(digest):
            raise AcquisitionError("acquisition_storage_failed")
        path = self.root.joinpath(*key.split("/"))
        self._check(path, final=True)
        return path

    @contextmanager
    def staging(self, control, limit, budget):
        control.check()
        staging = self.root / "staging"
        self._directory(staging)
        path = None
        try:
            descriptor, name = tempfile.mkstemp(prefix="attempt-", suffix=".part", dir=staging)
            path = Path(name)
            with os.fdopen(descriptor, "wb") as stream:
                sink = BoundedSink(stream, control, limit, budget)
                yield path, sink
                if not stream.closed:
                    stream.flush()
                    os.fsync(stream.fileno())
        finally:
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    def hash_file(self, path, control, limit):
        self._check(path, final=True)
        regular(path)
        digest, count = hashlib.sha256(), 0
        with path.open("rb") as stream:
            while True:
                control.check()
                chunk = stream.read(MAX_TRANSFER_CHUNK)
                if not chunk:
                    break
                count += len(chunk)
                if count > limit:
                    raise AcquisitionError("acquisition_limit_exceeded")
                digest.update(chunk)
        control.check()
        if not count:
            raise AcquisitionError("acquisition_validation_failed")
        return digest.hexdigest(), count

    def verify(self, asset, control):
        path = self.resolve(asset.object_key)
        digest, count = self.hash_file(path, control, asset.byte_count)
        if (digest, count) != (asset.sha256, asset.byte_count):
            raise AcquisitionError("acquisition_storage_failed")
        return path

    def finalize(self, staging, digest, count, control):
        control.check()
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or count <= 0:
            raise AcquisitionError("acquisition_validation_failed")
        asset = MaterializedAsset("asset:sha256:" + digest, digest, count, object_key(digest))
        target = self.resolve(asset.object_key)
        self._directory(target.parent)
        if self.hash_file(staging, control, count) != (digest, count):
            raise AcquisitionError("acquisition_storage_failed")
        control.check()
        try:
            # Hard-link installation is atomic and fails if the destination exists.
            # Both paths are on the managed volume; no overwrite fallback is allowed.
            os.link(staging, target)
        except FileExistsError:
            self.verify(asset, control)
        except OSError:
            raise AcquisitionError("acquisition_storage_failed") from None
        self.verify(asset, control)
        control.check()
        return asset
