import sys
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

from scripts.image_output import (
    ImageResponseError,
    OutputPathError,
    decode_base64_image,
    download_image_bytes,
    validate_download_url,
    validate_output_path,
)


class OutputPathTests(unittest.TestCase):
    def test_cli_rejects_non_object_batch_item(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "tasks.json"
            batch.write_text("[42]", encoding="utf-8")
            for command in ("gen", "edit"):
                with self.subTest(command=command):
                    result = subprocess.run(
                        [sys.executable, str(root / "scripts" / f"{command}.py"),
                         "--batch", str(batch), "--api-key", "unused",
                         "--base-url", "http://127.0.0.1:1/v1"],
                        capture_output=True, text=True, encoding="utf-8", timeout=10,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("任务 #1 必须是 JSON 对象", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

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

    def test_accepts_macos_user_temp_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            if sys.platform != "darwin" or not parent.is_relative_to("/var/folders"):
                self.skipTest("requires a macOS temporary directory under /var/folders")
            self.assertEqual(
                validate_output_path(parent / "output.png").parent,
                parent.resolve(strict=True),
            )

    def test_rejects_malformed_download_url_without_printing_it(self):
        with self.assertRaisesRegex(ImageResponseError, "地址格式无效") as error:
            validate_download_url("https://[bad.example/?ticket=placeholder")
        self.assertNotIn("placeholder", str(error.exception))

    def test_rejects_internal_ip_and_localhost_download_urls_without_leaking(self):
        for url in (
            "https://127.0.0.1/a.png?sig=secret123",
            "https://169.254.169.254/latest/meta-data?sig=secret123",
            "https://10.0.0.1/a.png?sig=secret123",
            "https://localhost/a.png?sig=secret123",
            "https://localhost./a.png?sig=secret123",
            "https://[::ffff:127.0.0.1]/a.png?sig=secret123",
        ):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ImageResponseError, "拒绝") as error:
                    validate_download_url(url)
                self.assertNotIn("secret123", str(error.exception))

    def test_download_blocks_redirect_to_internal_or_http_before_request(self):
        import httpx

        for redirect_target in (
            "http://127.0.0.1:8080/internal.png",
            "https://169.254.169.254/latest/meta-data",
            "http://cdn.example.com/downgraded.png",
        ):
            seen_urls = []

            def handler(request: httpx.Request) -> httpx.Response:
                seen_urls.append(str(request.url))
                return httpx.Response(302, headers={"Location": redirect_target})

            transport = httpx.MockTransport(handler)
            with self.subTest(target=redirect_target), self.assertRaises(ImageResponseError):
                download_image_bytes(
                    "https://cdn.example.com/start.png",
                    client_factory=lambda: httpx.Client(transport=transport, follow_redirects=False),
                )
            self.assertEqual(seen_urls, ["https://cdn.example.com/start.png"])

    def test_decode_base64_image_enforces_limit_before_decode(self):
        with self.assertRaisesRegex(ImageResponseError, "过大"):
            decode_base64_image("A" * 100, max_bytes=16)

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
