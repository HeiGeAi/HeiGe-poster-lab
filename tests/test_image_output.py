import tempfile
import unittest
import uuid
from pathlib import Path

from scripts.image_output import OutputPathError, validate_output_path


class OutputPathTests(unittest.TestCase):
    def test_accepts_macos_tmp_alias(self):
        requested = Path("/tmp") / f"heige-poster-{uuid.uuid4().hex}.png"

        output = validate_output_path(requested)

        self.assertEqual(output.parent, Path("/tmp").resolve(strict=True))
        self.assertEqual(output.name, requested.name)

    def test_accepts_macos_var_tmp_alias(self):
        requested = Path("/var/tmp") / f"heige-poster-{uuid.uuid4().hex}.png"

        output = validate_output_path(requested)

        self.assertEqual(output.parent, Path("/var/tmp").resolve(strict=True))
        self.assertEqual(output.name, requested.name)

    def test_rejects_final_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp).resolve()
            target = parent / "target.png"
            target.write_bytes(b"original")
            output = parent / "output.png"
            output.symlink_to(target)

            with self.assertRaisesRegex(OutputPathError, "符号链接"):
                validate_output_path(output)

            self.assertEqual(target.read_bytes(), b"original")

    def test_rejects_user_created_parent_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            outside = root / "outside"
            outside.mkdir()
            linked_parent = root / "linked"
            linked_parent.symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(OutputPathError, "符号链接"):
                validate_output_path(linked_parent / "output.png")

            self.assertFalse((outside / "output.png").exists())


if __name__ == "__main__":
    unittest.main()
