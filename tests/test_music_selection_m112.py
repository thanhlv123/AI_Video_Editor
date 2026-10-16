import json
import tempfile
import unittest
import wave
from pathlib import Path

from creator_studio.music_selection import (
    MUSIC_SELECTION_FILENAME,
    BackgroundMusicSelectionService,
    import_music_asset,
    music_origin_root,
)


class MusicSelectionM112Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.run_dir = self.root / "work" / "automation" / "run_test"
        self.run_dir.mkdir(parents=True)
        self.scenes_path = self.root / "work" / "voice" / "voice_test" / "run_test" / "voice_scenes.json"
        self.scenes_path.parent.mkdir(parents=True)
        self.final_path = self.run_dir / "final_renderable_assets.json"
        self.final_path.write_text(json.dumps({
            "format": "creator_studio_final_renderable_assets_m110_6",
            "summary": {"ready_count": 2, "unresolved_count": 0},
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _write_scenes(self, *, duration=12.0, text="A quiet family memory in old Havana."):
        payload = [
            {"id": "scene_001", "start": 0.0, "end": duration / 2, "duration": duration / 2, "text": text},
            {"id": "scene_002", "start": duration / 2, "end": duration, "duration": duration / 2, "text": text},
        ]
        self.scenes_path.write_text(json.dumps(payload), encoding="utf-8")

    def _wav(self, path: Path, seconds: float):
        path.parent.mkdir(parents=True, exist_ok=True)
        rate = 8000
        frames = int(rate * seconds)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            handle.writeframes(b"\x00\x00" * frames)
        return path

    def test_no_music_is_nonfatal_skip(self):
        self._write_scenes()
        report = BackgroundMusicSelectionService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            final_renderable_manifest_path=self.final_path,
        ).run()
        self.assertEqual(report.status, "skipped_no_music")
        payload = json.loads((self.run_dir / MUSIC_SELECTION_FILENAME).read_text(encoding="utf-8"))
        self.assertIsNone(payload["selected"])
        self.assertTrue(payload["policy"]["no_music_is_nonfatal"])

    def test_disabled_music_writes_skipped_manifest(self):
        self._write_scenes()
        report = BackgroundMusicSelectionService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            final_renderable_manifest_path=self.final_path,
            enabled=False,
        ).run()
        self.assertEqual(report.status, "skipped_disabled")

    def test_selects_mood_matching_project_local_track(self):
        self._write_scenes(text="An elderly grandmother remembers family leaving Cuba and says goodbye.")
        src = self._wav(self.root / "source_reflective.wav", 20.0)
        warm = import_music_asset(
            self.root,
            src,
            display_name="Reflective Documentary Piano",
            mood="reflective",
            genre="cinematic",
            energy="low",
            tags=["piano", "memory", "documentary"],
        )
        src2 = self._wav(self.root / "source_upbeat.wav", 20.0)
        import_music_asset(
            self.root,
            src2,
            display_name="Upbeat Travel",
            mood="uplifting",
            genre="pop",
            energy="high",
            tags=["travel", "happy"],
        )
        report = BackgroundMusicSelectionService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            final_renderable_manifest_path=self.final_path,
        ).run()
        self.assertEqual(report.status, "selected")
        self.assertEqual(report.selected_asset_id, warm.asset_id)
        payload = json.loads((self.run_dir / MUSIC_SELECTION_FILENAME).read_text(encoding="utf-8"))
        self.assertEqual(payload["selected"]["asset_id"], warm.asset_id)
        self.assertFalse(Path(payload["selected"]["path"]).is_absolute())
        self.assertTrue(payload["mix"]["voice_is_primary"])
        self.assertTrue(payload["mix"]["ducking_enabled"])

    def test_short_music_sets_loop_required_using_voice_duration_authority(self):
        self._write_scenes(duration=12.0)
        source = self._wav(self.root / "short.wav", 4.0)
        import_music_asset(self.root, source, display_name="Calm Ambient", mood="calm", energy="low")
        report = BackgroundMusicSelectionService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            final_renderable_manifest_path=self.final_path,
        ).run()
        self.assertTrue(report.loop_required)
        self.assertAlmostEqual(report.project_duration_seconds, 12.0, places=2)

    def test_long_music_is_trimmed_not_looped(self):
        self._write_scenes(duration=8.0)
        source = self._wav(self.root / "long.wav", 20.0)
        import_music_asset(self.root, source, display_name="Neutral Background", mood="neutral", energy="low")
        report = BackgroundMusicSelectionService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            final_renderable_manifest_path=self.final_path,
        ).run()
        self.assertFalse(report.loop_required)
        payload = json.loads((self.run_dir / MUSIC_SELECTION_FILENAME).read_text(encoding="utf-8"))
        self.assertTrue(payload["mix"]["trim_to_target"])

    def test_unresolved_final_media_blocks_music_stage(self):
        self._write_scenes()
        self.final_path.write_text(json.dumps({"summary": {"ready_count": 1, "unresolved_count": 1}}), encoding="utf-8")
        with self.assertRaises(Exception):
            BackgroundMusicSelectionService(
                project_root=self.root,
                run_dir=self.run_dir,
                source_scenes_path=self.scenes_path,
                final_renderable_manifest_path=self.final_path,
            ).run()


if __name__ == "__main__":
    unittest.main()
