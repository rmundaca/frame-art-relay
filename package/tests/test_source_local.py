import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image as PILImage

from app.core.config import settings
from app.services import source_local


def make_image(path: Path, size=(64, 48)):
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", size, (200, 120, 40)).save(path)


class MediaRootMixin:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name)) / "media"
        self.root.mkdir()
        self.old_roots = settings.setdefault("media", {}).get("roots")
        settings["media"]["roots"] = [str(self.root)]

    def tearDown(self):
        settings["media"]["roots"] = self.old_roots
        self.tmp.cleanup()


class SourceLocalTest(MediaRootMixin, unittest.TestCase):
    def test_rejects_paths_outside_roots(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        for path in (str(outside), str(self.root / ".." / "outside"), "", "/"):
            with self.assertRaises(ValueError):
                source_local.resolve(path)

    def test_scan_filters_and_recurses(self):
        make_image(self.root / "a.jpg")
        make_image(self.root / "sub" / "b.png")
        make_image(self.root / "@eaDir" / "thumb.jpg")
        make_image(self.root / ".hidden.jpg")
        (self.root / "notes.txt").write_text("x")
        flat = [k for k, _, _ in source_local.scan(str(self.root), recursive=False)]
        deep = [k for k, _, _ in source_local.scan(str(self.root), recursive=True)]
        self.assertEqual(flat, ["a.jpg"])
        self.assertEqual(deep, ["a.jpg", "sub/b.png"])

    def test_file_path_blocks_traversal(self):
        make_image(self.root / "a.jpg")
        self.assertTrue(source_local.file_path(str(self.root), "a.jpg").is_file())
        with self.assertRaises(ValueError):
            source_local.file_path(str(self.root), "../outside.jpg")

    def test_browse(self):
        (self.root / "fotos").mkdir()
        make_image(self.root / "a.jpg")
        top = source_local.browse("")
        self.assertEqual([d["path"] for d in top["dirs"]], [str(self.root)])
        inside = source_local.browse(str(self.root))
        self.assertEqual([d["name"] for d in inside["dirs"]], ["fotos"])
        self.assertEqual(inside["images"], 1)
        self.assertEqual(inside["parent"], "")


if __name__ == "__main__":
    unittest.main()
