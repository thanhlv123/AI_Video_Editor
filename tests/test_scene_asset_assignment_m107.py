import json
import tempfile
import unittest
from pathlib import Path

from creator_studio.project_storage import (
    create_voice_work_run,
    import_media_asset,
    initialize_project_layout,
)
from creator_studio.scene_assets import (
    assign_media_asset,
    latest_voice_scenes_path,
    load_scene_assignment_state,
    load_voice_scenes,
    remove_scene_assignment,
    scene_assignment_state_path,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"x" * 32
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"x" * 32


class SceneAssetAssignmentM107Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        initialize_project_layout(self.root)
        self.voice_asset_id = "voice_test123"
        self.run = create_voice_work_run(self.root, self.voice_asset_id)
        self.scenes_path = self.run / "voice_scenes.json"
        self.scenes = [
            {"id": "scene_001", "start": 0.0, "end": 4.0, "duration": 4.0, "text": "One", "scene_type": "speech"},
            {"id": "scene_002", "start": 4.0, "end": 9.0, "duration": 5.0, "text": "Two", "scene_type": "speech"},
        ]
        self.scenes_path.write_text(json.dumps(self.scenes), encoding="utf-8")

        img = Path(self.temp.name) / "a.png"
        img.write_bytes(PNG_BYTES)
        vid = Path(self.temp.name) / "b.mp4"
        vid.write_bytes(MP4_BYTES)
        self.image = import_media_asset(self.root, img, media_type="image")
        self.video = import_media_asset(self.root, vid, media_type="video")

    def tearDown(self):
        self.temp.cleanup()

    def test_latest_voice_scenes_path_finds_current_run(self):
        self.assertEqual(latest_voice_scenes_path(self.root, self.voice_asset_id), self.scenes_path.resolve())

    def test_load_voice_scenes_strictly_reads_scene_ids(self):
        scenes = load_voice_scenes(self.scenes_path)
        self.assertEqual([s["id"] for s in scenes], ["scene_001", "scene_002"])

    def test_assignments_are_saved_by_asset_id_without_mutating_media(self):
        image_before = self.image.media_path.read_bytes()
        state = assign_media_asset(
            self.root,
            self.voice_asset_id,
            self.scenes_path,
            "scene_001",
            self.image.asset_id,
        )
        self.assertEqual(state.assignment_map()["scene_001"].asset_id, self.image.asset_id)
        self.assertEqual(self.image.media_path.read_bytes(), image_before)
        state_path = scene_assignment_state_path(self.root, self.voice_asset_id, self.scenes_path)
        self.assertTrue(state_path.is_file())

    def test_reassign_scene_replaces_only_mapping_not_asset(self):
        assign_media_asset(self.root, self.voice_asset_id, self.scenes_path, "scene_001", self.image.asset_id)
        state = assign_media_asset(self.root, self.voice_asset_id, self.scenes_path, "scene_001", self.video.asset_id)
        self.assertEqual(len(state.assignments), 1)
        self.assertEqual(state.assignment_map()["scene_001"].asset_id, self.video.asset_id)
        self.assertTrue(self.image.media_path.is_file())
        self.assertTrue(self.video.media_path.is_file())

    def test_remove_assignment_keeps_media_asset(self):
        assign_media_asset(self.root, self.voice_asset_id, self.scenes_path, "scene_002", self.video.asset_id)
        state = remove_scene_assignment(self.root, self.voice_asset_id, self.scenes_path, "scene_002")
        self.assertEqual(state.assignments, ())
        self.assertTrue(self.video.media_path.is_file())

    def test_new_voice_pipeline_run_gets_separate_assignment_file(self):
        first = assign_media_asset(
            self.root, self.voice_asset_id, self.scenes_path, "scene_001", self.image.asset_id
        )
        first_path = scene_assignment_state_path(self.root, self.voice_asset_id, self.scenes_path)

        run2 = create_voice_work_run(self.root, self.voice_asset_id)
        scenes2 = run2 / "voice_scenes.json"
        scenes2.write_text(json.dumps([
            {"id": "scene_001", "start": 0.0, "end": 2.0, "duration": 2.0, "text": "Changed", "scene_type": "speech"}
        ]), encoding="utf-8")
        second = assign_media_asset(
            self.root, self.voice_asset_id, scenes2, "scene_001", self.video.asset_id
        )
        second_path = scene_assignment_state_path(self.root, self.voice_asset_id, scenes2)

        self.assertNotEqual(first_path, second_path)
        self.assertEqual(first.assignment_map()["scene_001"].asset_id, self.image.asset_id)
        self.assertEqual(second.assignment_map()["scene_001"].asset_id, self.video.asset_id)
        self.assertTrue(first_path.is_file())
        self.assertTrue(second_path.is_file())

    def test_unknown_asset_id_is_rejected(self):
        with self.assertRaises(Exception):
            assign_media_asset(
                self.root, self.voice_asset_id, self.scenes_path, "scene_001", "image_missing"
            )

    def test_persisted_state_is_bound_to_exact_scene_file_hash(self):
        assign_media_asset(self.root, self.voice_asset_id, self.scenes_path, "scene_001", self.image.asset_id)
        self.scenes[0]["text"] = "Mutated after assignment"
        self.scenes_path.write_text(json.dumps(self.scenes), encoding="utf-8")
        # Hash change intentionally maps to a new assignment state path rather than
        # silently reusing the old scene/media decisions.
        state = load_scene_assignment_state(self.root, self.voice_asset_id, self.scenes_path)
        self.assertEqual(state.assignments, ())


if __name__ == "__main__":
    unittest.main()
