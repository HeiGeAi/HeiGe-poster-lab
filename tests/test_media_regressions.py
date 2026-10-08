import base64
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import httpx
from scripts import gen, edit


def png(value=0):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes([0, value, 0, 0]))) + chunk(b"IEND", b""))


class BatchRegressionTests(unittest.TestCase):
    def test_duplicate_and_aliased_outputs_make_no_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alias").symlink_to(root, target_is_directory=True)
            for second in (root / "out.png", root / "alias/out.png", root / "sub/../out.png"):
                for module, batch in ((gen, gen.generate_batch), (edit, edit.edit_batch)):
                    with self.subTest(second=second, module=module.__name__):
                        tasks = [{"prompt": "p", "input": "unused.png", "output": str(path)}
                                 for path in (root / "out.png", second)]
                        with patch.object(module, "_request_once") as request:
                            results = batch(tasks, "fake", "https://example.test/v1", "fake", max_retries=0)
                        request.assert_not_called()
                        self.assertEqual(len(results), 2)
                        self.assertTrue(all(not r["success"] for r in results))
                        self.assertFalse((root / "out.png").exists())

    def test_invalid_later_output_prevents_entire_batch(self):
        for module, batch in ((gen, gen.generate_batch), (edit, edit.edit_batch)):
            with tempfile.TemporaryDirectory() as tmp, patch.object(module, "_request_once") as request:
                tasks = [{"prompt": "p", "input": "unused.png", "output": str(Path(tmp) / name)}
                         for name in ("ok.png", "bad.jpg")]
                results = batch(tasks, "fake", "https://example.test", "fake")
                request.assert_not_called()
                self.assertTrue(all(not r["success"] for r in results))

    def test_distinct_outputs_preserve_both_images(self):
        for module, batch in ((gen, gen.generate_batch), (edit, edit.edit_batch)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "source.png"
                source.write_bytes(png())
                tasks = [{"prompt": "p", "input": str(source), "output": str(root / f"{i}.png")} for i in range(2)]
                responses = [httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png(i)).decode()}]})
                             for i in range(2)]
                with patch.object(module, "_request_once", side_effect=responses) as request:
                    results = batch(tasks, "fake", "https://example.test/v1", "fake", workers=1, max_retries=0)
                self.assertEqual(request.call_count, 2)
                self.assertTrue(all(r["success"] for r in results), results)
                self.assertEqual([Path(r["path"]).read_bytes() for r in results], [png(0), png(1)])


class ProviderRegressionTests(unittest.TestCase):
    def test_explicit_endpoint_wins_even_when_equal_to_default(self):
        import os
        for module in (gen, edit):
            with patch.dict(os.environ, {"HEIGE_IMAGE_BASE_URL": "https://fallback.test/v1"}, clear=True), patch.object(module, "_load_fallback_config", return_value={}):
                for url in (module.DEFAULT_BASE_URL, module.DEFAULT_BASE_URL + "/"):
                    self.assertEqual(module.resolve_base_url(url, {}), module.DEFAULT_BASE_URL)
                    self.assertEqual(module.resolve_base_url(None, {"base_url": url}), module.DEFAULT_BASE_URL)
                self.assertEqual(module.resolve_base_url(None, {}), "https://fallback.test/v1")

    def test_provider_family_never_borrows_another_key(self):
        import os
        for module in (gen, edit):
            with patch.dict(os.environ, {"HEIGE_IMAGE_BASE_URL": "https://fallback.test/v1", "HEIGE_IMAGE_API_KEY": "fallback-key", "HEIGE_IMAGE_MODEL": "fallback-model"}, clear=True), patch.object(module, "_load_fallback_config", return_value={}):
                self.assertEqual(module.resolve_provider(config={}), ("https://fallback.test/v1", "fallback-key", "fallback-model"))
                with self.assertRaises(SystemExit):
                    module.resolve_provider(cli_base=module.DEFAULT_BASE_URL, config={})
                self.assertEqual(module.resolve_provider(cli_base=module.DEFAULT_BASE_URL + "/", cli_key="chosen-key", config={}),
                                 (module.DEFAULT_BASE_URL, "chosen-key", module.DEFAULT_MODEL))

    def test_own_environment_and_config_precedence(self):
        import os
        for module in (gen, edit):
            with patch.dict(os.environ, {"HEIGE_POSTER_LAB_BASE_URL": "https://own.test/v1/", "HEIGE_POSTER_LAB_API_KEY": "own-key", "HEIGE_IMAGE_BASE_URL": "https://fallback.test/v1"}, clear=True), patch.object(module, "_load_fallback_config", side_effect=AssertionError("must not read fallback")):
                self.assertEqual(module.resolve_provider(config={"base_url": "https://config.test/v1", "api_key": "config-key"}),
                                 ("https://own.test/v1", "own-key", module.DEFAULT_MODEL))
                self.assertEqual(module.resolve_provider(cli_base=module.DEFAULT_BASE_URL, cli_key="cli-key", config={}),
                                 (module.DEFAULT_BASE_URL, "cli-key", module.DEFAULT_MODEL))
            with patch.dict(os.environ, {}, clear=True), patch.object(module, "_load_fallback_config", return_value={"base_url": "https://fallback.test/v1/", "api_key": "fallback-key", "model": "fallback-model"}):
                self.assertEqual(module.resolve_provider(config={}), ("https://fallback.test/v1", "fallback-key", "fallback-model"))
                self.assertEqual(module.resolve_provider(config={"base_url": module.DEFAULT_BASE_URL, "api_key": "config-key"}),
                                 (module.DEFAULT_BASE_URL, "config-key", module.DEFAULT_MODEL))

    def test_fake_transport_receives_selected_host(self):
        import os
        with patch.dict(os.environ, {"HEIGE_IMAGE_BASE_URL": "https://fallback.test/v1"}, clear=True):
            base, key, model = gen.resolve_provider(gen.DEFAULT_BASE_URL, "chosen-key", config={})
        response = httpx.Response(200, json={"data": []})
        with patch.object(gen.httpx, "Client") as client:
            client.return_value.__enter__.return_value.post.return_value = response
            gen._request_once({"model": model}, 1, key, base)
            args, kwargs = client.return_value.__enter__.return_value.post.call_args
            self.assertEqual(args[0], gen.DEFAULT_BASE_URL + "/images/generations")
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer chosen-key")


class ResponseRegressionTests(unittest.TestCase):
    def test_malformed_success_returns_failure(self):
        payloads = [None, [], {"data": []}, {"data": None}, {"data": [1]}, {"data": [{"url": 12}]}, {"data": [{"b64_json": {"x": 1}}]}]
        responses = [httpx.Response(200, json=p) for p in payloads] + [httpx.Response(200, text="not json")]
        for module, core in ((gen, gen._generate_core), (edit, edit._edit_core)):
            with tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "source.png"
                source.write_bytes(png())
                target = Path(tmp) / "out.png"
                target.write_bytes(png(5))
                kwargs = {"prompt": "p", "api_key": "fake", "base_url": "https://example.test", "model": "fake", "output_path": str(target), "max_retries": 0}
                if module is edit:
                    kwargs["input_image"] = str(source)
                for response in responses:
                    with self.subTest(module=module.__name__, response=response.text), patch.object(module, "_request_once", return_value=response):
                        self.assertFalse(core(**kwargs)["success"])
                        self.assertEqual(target.read_bytes(), png(5))
                with patch.object(module, "_request_once", side_effect=httpx.RemoteProtocolError("bad response")):
                    self.assertFalse(core(**kwargs)["success"])

    def test_worker_exception_keeps_complete_batch_summary(self):
        for module, core_name, batch in ((gen, "_generate_core", gen.generate_batch), (edit, "_edit_core", edit.edit_batch)):
            with tempfile.TemporaryDirectory() as tmp:
                tasks = [{"prompt": "p", "input": "unused.png", "output": str(Path(tmp) / f"{i}.png")} for i in range(2)]
                with patch.object(module, core_name, side_effect=[RuntimeError("bad worker"), {"success": True, "path": "ok.png"}]):
                    results = batch(tasks, "fake", "https://example.test", "fake", workers=1)
                self.assertEqual([r["success"] for r in results], [False, True])
                self.assertEqual([r["index"] for r in results], [0, 1])
