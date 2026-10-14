import tempfile
import unittest
from pathlib import Path

from creator_studio.project_storage import (
    create_project_root,
    create_voice_work_run,
    finalize_voice_asset,
    import_voice_asset,
    new_generated_voice_target,
    scan_voice_assets,
)


class ProjectStorageM105Tests(unittest.TestCase):
    def test_project_root_is_user_selected_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root = create_project_root(parent, "My Project")
            self.assertEqual(root.parent, parent.resolve())
            self.assertTrue((root / "assets" / "voice" / "generated").is_dir())
            self.assertTrue((root / "assets" / "voice" / "imported").is_dir())
            self.assertTrue((root / "work" / "voice").is_dir())
            with self.assertRaises(FileExistsError):
                create_project_root(parent, "My Project")

    def test_generated_voice_targets_are_unique_and_catalogued(self):
        with tempfile.TemporaryDirectory() as td:
            root = create_project_root(Path(td), "P")
            a = new_generated_voice_target(
                root, provider_id="piper_local", model_id=None, voice_id="amy"
            )
            b = new_generated_voice_target(
                root, provider_id="piper_local", model_id=None, voice_id="amy"
            )
            self.assertNotEqual(a.path, b.path)
            Path(a.path).write_bytes(b"RIFF" + b"x" * 200)
            finalized = finalize_voice_asset(a, language="en", speed=1.0, duration_seconds=2.0)
            items = scan_voice_assets(root)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].asset_id, finalized.asset_id)

    def test_imported_voice_is_copied_into_project(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = create_project_root(base, "P")
            source = base / "source.wav"
            source.write_bytes(b"RIFF" + b"a" * 128)
            record = import_voice_asset(root, source)
            self.assertTrue(Path(record.path).is_file())
            self.assertNotEqual(Path(record.path), source)
            self.assertEqual(record.kind, "imported")

    def test_voice_work_runs_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = create_project_root(Path(td), "P")
            a = create_voice_work_run(root, "voice_abc")
            b = create_voice_work_run(root, "voice_abc")
            self.assertNotEqual(a, b)
            self.assertTrue(a.is_dir())
            self.assertTrue(b.is_dir())


if __name__ == "__main__":
    unittest.main()
