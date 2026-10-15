import tempfile
import unittest
from pathlib import Path

from creator_studio.project_storage import (
    ProjectStorageError,
    create_project_root,
    finalize_media_asset,
    import_media_asset,
    new_media_asset_target,
    scan_media_assets,
)


class ProjectStorageM106Tests(unittest.TestCase):
    def test_layout_adds_image_and_video_asset_roots(self):
        with tempfile.TemporaryDirectory() as td:
            root = create_project_root(Path(td), "Media Project")
            expected = (
                root / "assets" / "images" / "imported",
                root / "assets" / "images" / "downloaded",
                root / "assets" / "images" / "generated",
                root / "assets" / "videos" / "imported",
                root / "assets" / "videos" / "downloaded",
                root / "assets" / "videos" / "generated",
                root / "assets" / "voice" / "generated",
                root / "assets" / "voice" / "imported",
            )
            for path in expected:
                self.assertTrue(path.is_dir(), path)

    def test_same_image_imported_twice_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = create_project_root(base, "P")
            source = base / "photo.jpg"
            source.write_bytes(b"\xff\xd8\xff" + b"a" * 200)
            a = import_media_asset(root, source, media_type="image")
            b = import_media_asset(root, source, media_type="image")
            self.assertNotEqual(a.asset_id, b.asset_id)
            self.assertNotEqual(a.path, b.path)
            self.assertTrue(Path(a.path).is_file())
            self.assertTrue(Path(b.path).is_file())
            self.assertTrue(Path(a.path + ".asset.json").is_file())
            self.assertTrue(Path(b.path + ".asset.json").is_file())

    def test_same_video_imported_twice_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = create_project_root(base, "P")
            source = base / "clip.mp4"
            source.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"v" * 256)
            a = import_media_asset(root, source, media_type="video")
            b = import_media_asset(root, source, media_type="video")
            self.assertNotEqual(a.path, b.path)
            self.assertEqual(a.media_type, "video")
            self.assertEqual(b.media_type, "video")

    def test_downloaded_and_generated_targets_are_separate_and_catalogued(self):
        with tempfile.TemporaryDirectory() as td:
            root = create_project_root(Path(td), "P")
            downloaded = new_media_asset_target(
                root,
                media_type="image",
                origin="downloaded",
                extension=".png",
                display_name="Pexels Lake",
                provider_id="pexels",
            )
            generated = new_media_asset_target(
                root,
                media_type="image",
                origin="generated",
                extension=".png",
                display_name="AI Lake",
                provider_id="kie",
                model_id="image-model",
            )
            Path(downloaded.path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"d" * 100)
            Path(generated.path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"g" * 100)
            finalize_media_asset(downloaded, width=1280, height=720)
            finalize_media_asset(generated, width=1024, height=1024)
            items = scan_media_assets(root, "image")
            self.assertEqual({item.origin for item in items}, {"downloaded", "generated"})
            self.assertEqual(len(items), 2)

    def test_scan_filter_separates_images_and_videos(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = create_project_root(base, "P")
            image = base / "a.webp"
            video = base / "b.mkv"
            image.write_bytes(b"RIFF" + b"i" * 100)
            video.write_bytes(b"\x1aE\xdf\xa3" + b"v" * 100)
            import_media_asset(root, image)
            import_media_asset(root, video)
            self.assertEqual(len(scan_media_assets(root)), 2)
            self.assertEqual(len(scan_media_assets(root, "image")), 1)
            self.assertEqual(len(scan_media_assets(root, "video")), 1)

    def test_unsupported_extension_is_rejected_without_copy(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = create_project_root(base, "P")
            source = base / "notes.txt"
            source.write_text("not media", encoding="utf-8")
            with self.assertRaises(ProjectStorageError):
                import_media_asset(root, source)
            self.assertEqual(scan_media_assets(root), [])


if __name__ == "__main__":
    unittest.main()
