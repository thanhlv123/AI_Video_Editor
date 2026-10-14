from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PiperProviderIsolationTests(unittest.TestCase):
    def test_piper_worker_import_does_not_require_requests(self):
        code = r'''
import builtins
_real_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "requests" or name.startswith("requests."):
        raise ModuleNotFoundError("blocked requests for Piper isolation test")
    return _real_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
import creator_studio.tts.providers.piper_worker
print("PIPER_WORKER_IMPORT_OK")
'''
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("PIPER_WORKER_IMPORT_OK", completed.stdout)

    def test_piper_provider_import_does_not_require_requests(self):
        code = r'''
import builtins
_real_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "requests" or name.startswith("requests."):
        raise ModuleNotFoundError("blocked requests for Piper isolation test")
    return _real_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
from creator_studio.tts.providers import PiperProcessProvider
print(PiperProcessProvider.PROVIDER_ID)
'''
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("piper_local", completed.stdout)


if __name__ == "__main__":
    unittest.main()
