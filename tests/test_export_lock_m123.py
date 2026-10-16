from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from creator_studio.export_lock import ProjectExportBusy, project_export_lock


class ProjectExportLockM123Tests(unittest.TestCase):
    def test_second_handle_cannot_acquire_project_lock(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with project_export_lock(root):
                with self.assertRaises(ProjectExportBusy):
                    with project_export_lock(root):
                        self.fail("Second export unexpectedly acquired lock.")
            with project_export_lock(root):
                pass

    def test_lock_is_released_after_exception(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                with project_export_lock(root):
                    raise RuntimeError("simulated failure")
            with project_export_lock(root):
                pass

    def test_second_process_cannot_acquire_project_lock(self):
        script = (
            "import sys\n"
            "from pathlib import Path\n"
            "from creator_studio.export_lock import project_export_lock, ProjectExportBusy\n"
            "try:\n"
            "    with project_export_lock(Path(sys.argv[1])): sys.exit(0)\n"
            "except ProjectExportBusy: sys.exit(7)\n"
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with project_export_lock(root):
                result = subprocess.run(
                    [sys.executable, "-c", script, str(root)],
                    cwd=Path(__file__).resolve().parents[1],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    7,
                    f"Unexpected subprocess result: {result.stdout} {result.stderr}",
                )
            result = subprocess.run(
                [sys.executable, "-c", script, str(root)],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
