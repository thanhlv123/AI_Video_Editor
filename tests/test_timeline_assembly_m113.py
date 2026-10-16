import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creator_studio.timeline_assembly import (
    AutomaticTimelineAssemblyService,
    TIMELINE_FILENAME,
    TimelineAssemblyError,
)


class TimelineAssemblyM113Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run_dir = self.root / "work" / "automation" / "run_test"
        self.run_dir.mkdir(parents=True)
        self.scenes_path = self.root / "work" / "voice" / "voice_scenes.json"
        self.scenes_path.parent.mkdir(parents=True)
        self.voice_path = self.root / "assets" / "voice" / "generated" / "voice.wav"
        self.voice_path.parent.mkdir(parents=True)
        self.voice_path.write_bytes(b"RIFFfake")
        self.video1 = self.root / "assets" / "video" / "downloaded" / "v1.mp4"
        self.video2 = self.root / "assets" / "video" / "downloaded" / "v2.mp4"
        self.image1 = self.root / "assets" / "image" / "downloaded" / "i1.jpg"
        for p in (self.video1, self.video2, self.image1):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"asset")
        self.music = self.root / "assets" / "music" / "imported" / "calm.mp3"
        self.music.parent.mkdir(parents=True)
        self.music.write_bytes(b"music")
        self.final_path = self.run_dir / "final_renderable_assets.json"
        self.music_path = self.run_dir / "music_selection_manifest.json"

    def _write_scenes(self, scenes=None):
        scenes = scenes or [
            {"id": "scene_001", "start": 0.0, "end": 4.0, "duration": 4.0, "text": "one"},
            {"id": "scene_002", "start": 4.0, "end": 9.0, "duration": 5.0, "text": "two"},
        ]
        self.scenes_path.write_text(json.dumps(scenes), encoding="utf-8")
        return scenes

    def _write_final(self, scenes=None, second_type="video", second_duration=8.0, unresolved=0):
        scenes = scenes or self._write_scenes()
        items = []
        for idx, scene in enumerate(scenes):
            is_second = idx == 1
            media_type = second_type if is_second else "video"
            path = self.image1 if (is_second and second_type == "image") else (self.video2 if is_second else self.video1)
            duration = None if media_type == "image" else (second_duration if is_second else 10.0)
            items.append({
                "scene_id": scene["id"],
                "timing": {"start": scene["start"], "end": scene["end"], "duration": scene["end"]-scene["start"]},
                "assignment": {"asset_id": f"asset_{idx+1}", "media_type": media_type},
                "asset": {
                    "asset_id": f"asset_{idx+1}", "display_name": path.stem,
                    "media_type": media_type, "origin": "downloaded",
                    "path": path.relative_to(self.root).as_posix(),
                    "duration_seconds": duration, "width": 1920, "height": 1080,
                },
                "selection": {"score": 0.7, "source": "stock"},
                "render_eligible": unresolved == 0,
                "issues": [] if unresolved == 0 else ["test"],
            })
        payload = {
            "format": "creator_studio_final_renderable_m110_6",
            "scene_count": len(scenes),
            "summary": {"ready_count": len(scenes)-unresolved, "unresolved_count": unresolved},
            "scenes": items,
        }
        self.final_path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_music(self, status="selected", duration=20.0):
        selected = None
        mix = {
            "music_gain_db": -22.0, "fade_in_seconds": 1.5, "fade_out_seconds": 2.0,
            "ducking_enabled": True, "ducking_reduction_db": 6.0,
            "start_seconds": 0.0, "target_duration_seconds": 9.0,
        }
        if status == "selected":
            selected = {
                "asset_id": "music_1", "path": self.music.relative_to(self.root).as_posix(),
                "duration_seconds": duration,
            }
        self.music_path.write_text(json.dumps({"status": status, "selected": selected, "mix": mix}), encoding="utf-8")

    def _service(self):
        return AutomaticTimelineAssemblyService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            voice_asset_id="voice_1",
            final_renderable_manifest_path=self.final_path,
            music_selection_manifest_path=self.music_path,
        )

    def _run(self):
        voice = SimpleNamespace(asset_id="voice_1", audio_path=self.voice_path, duration_seconds=9.0)
        with patch("creator_studio.timeline_assembly.scan_voice_assets", return_value=[voice]):
            return self._service().run()

    def test_builds_voice_authoritative_visual_timeline(self):
        self._write_scenes(); self._write_final(); self._write_music()
        report = self._run()
        self.assertEqual(report.status, "ready")
        data = json.loads((self.run_dir / TIMELINE_FILENAME).read_text(encoding="utf-8"))
        self.assertEqual(data["duration_seconds"], 9.0)
        clips = [x for x in data["tracks"]["visuals"] if x["kind"] == "scene"]
        self.assertEqual([(x["start_seconds"], x["end_seconds"]) for x in clips], [(0.0,4.0),(4.0,9.0)])
        self.assertFalse(clips[0]["operation"]["loop"])
        self.assertFalse(clips[0]["operation"]["speed_change"])
        self.assertEqual(clips[0]["operation"]["source_out_seconds"], 4.0)

    def test_image_scene_becomes_still_hold(self):
        self._write_scenes(); self._write_final(second_type="image"); self._write_music()
        self._run()
        data = json.loads((self.run_dir / TIMELINE_FILENAME).read_text(encoding="utf-8"))
        scene2 = [x for x in data["tracks"]["visuals"] if x.get("scene_id") == "scene_002"][0]
        self.assertEqual(scene2["operation"]["mode"], "still")
        self.assertEqual(scene2["operation"]["hold_seconds"], 5.0)

    def test_long_music_is_trimmed_to_voice_timeline(self):
        self._write_scenes(); self._write_final(); self._write_music(duration=20.0)
        self._run()
        music = json.loads((self.run_dir / TIMELINE_FILENAME).read_text(encoding="utf-8"))["tracks"]["music"]
        self.assertTrue(music["operation"]["trim_to_target"])
        self.assertFalse(music["operation"]["loop_required"])
        self.assertEqual(music["target_duration_seconds"], 9.0)

    def test_short_music_marks_loop_but_scene_video_never_loops(self):
        self._write_scenes(); self._write_final(); self._write_music(duration=3.0)
        self._run()
        data = json.loads((self.run_dir / TIMELINE_FILENAME).read_text(encoding="utf-8"))
        self.assertTrue(data["tracks"]["music"]["operation"]["loop_required"])
        for clip in data["tracks"]["visuals"]:
            self.assertFalse(clip["operation"].get("loop", False))

    def test_skipped_music_is_nonfatal(self):
        self._write_scenes(); self._write_final(); self._write_music(status="skipped_no_music")
        report = self._run()
        self.assertFalse(report.music_included)
        data = json.loads((self.run_dir / TIMELINE_FILENAME).read_text(encoding="utf-8"))
        self.assertIsNone(data["tracks"]["music"])
        self.assertEqual(data["music_state"]["status"], "skipped_no_music")

    def test_gap_between_voice_scenes_gets_deterministic_freeze_fill(self):
        scenes = [
            {"id":"scene_001","start":0.0,"end":3.0,"duration":3.0,"text":"a"},
            {"id":"scene_002","start":4.0,"end":8.0,"duration":4.0,"text":"b"},
        ]
        self._write_scenes(scenes); self._write_final(scenes=scenes); self._write_music(duration=10.0)
        report = self._run()
        self.assertEqual(report.gap_fill_count, 1)
        data = json.loads((self.run_dir / TIMELINE_FILENAME).read_text(encoding="utf-8"))
        gap = [x for x in data["tracks"]["visuals"] if x["kind"] == "gap_fill"][0]
        self.assertEqual((gap["start_seconds"],gap["end_seconds"]),(3.0,4.0))
        self.assertEqual(gap["operation"]["mode"], "freeze_frame")

    def test_unresolved_final_media_blocks_timeline(self):
        self._write_scenes(); self._write_final(unresolved=1); self._write_music()
        with self.assertRaises(TimelineAssemblyError):
            self._run()

    def test_short_video_blocks_timeline_even_if_manifest_claims_ready(self):
        self._write_scenes(); self._write_final(second_duration=2.0); self._write_music()
        with self.assertRaises(TimelineAssemblyError):
            self._run()

    def test_overlapping_voice_scenes_are_rejected(self):
        scenes = [
            {"id":"scene_001","start":0.0,"end":4.0,"duration":4.0,"text":"a"},
            {"id":"scene_002","start":3.0,"end":7.0,"duration":4.0,"text":"b"},
        ]
        self._write_scenes(scenes); self._write_final(scenes=scenes); self._write_music()
        with self.assertRaises(TimelineAssemblyError):
            self._run()


if __name__ == "__main__":
    unittest.main()
