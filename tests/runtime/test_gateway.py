import io
import os
import unittest
import tempfile
from pathlib import Path
import urllib.error
from unittest.mock import MagicMock, patch
from gateway import api_key, auto_settings, probe
from store import DEFAULT_SETTINGS
import app


class GatewayTests(unittest.TestCase):
    def test_no_keys_uses_local_without_network(self):
        with patch.dict(os.environ,{},clear=True),patch("gateway.urllib.request.urlopen") as network:
            config,result=auto_settings(DEFAULT_SETTINGS)
            self.assertFalse(config["remote_enabled"]);self.assertEqual(result["mode"],"local");network.assert_not_called()

    def test_provider_detection_does_not_cross_wire_credentials(self):
        with patch.dict(os.environ,{"DEEPSEEK_API_KEY":"test-token"},clear=True):
            config,result=auto_settings(DEFAULT_SETTINGS)
            self.assertEqual(config["provider"],"deepseek")
            self.assertEqual(config["provider_url"],"https://api.deepseek.com/v1")
            self.assertEqual(api_key(config),"test-token")
            self.assertIsNone(api_key({"key_env":"OPENAI_API_KEY"}))

    def test_catalog_success_contains_no_secret(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"data":[{"id":"example-text-model"}]}'
        with patch.dict(os.environ,{"MANJU_API_KEY":"test-token"}),patch("gateway.urllib.request.urlopen",return_value=response) as network:
            result=probe(DEFAULT_SETTINGS)
            self.assertTrue(result["connected"]);self.assertEqual(result["models"],["example-text-model"])
            self.assertNotIn("test-token",str(result));self.assertTrue(network.call_args.args[0].full_url.endswith("/v1/models"))

    def test_unauthorized_is_actionable_without_paid_retry(self):
        error=urllib.error.HTTPError("https://example.test/models",401,"unauthorized",{},io.BytesIO(b""))
        with patch.dict(os.environ,{"MANJU_API_KEY":"test-token"}),patch("gateway.urllib.request.urlopen",side_effect=error) as network:
            result=probe(DEFAULT_SETTINGS)
            self.assertFalse(result["connected"]);self.assertIn("401",result["message"]);self.assertEqual(network.call_count,1)

    def test_malformed_catalog_is_not_marked_connected(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"error":"invalid key"}'
        with patch.dict(os.environ,{"MANJU_API_KEY":"test-token"}),patch("gateway.urllib.request.urlopen",return_value=response):
            self.assertFalse(probe(DEFAULT_SETTINGS)["connected"])

    def test_dotenv_can_be_reloaded_without_server_restart(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{},clear=True),patch("app.APP_ROOT",Path(root)),patch("app._DOTENV_KEYS",set()):
            path=Path(root)/".env";path.write_text("MANJU_API_KEY=test-first",encoding="utf-8")
            app.read_env();self.assertEqual(os.environ["MANJU_API_KEY"],"test-first")
            path.write_text("MANJU_API_KEY=test-second",encoding="utf-8")
            app.read_env();self.assertEqual(os.environ["MANJU_API_KEY"],"test-second")

    def test_dotenv_preserves_explicit_process_environment(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{"MANJU_API_KEY":"process-value"},clear=True),patch("app.APP_ROOT",Path(root)),patch("app._DOTENV_KEYS",set()):
            (Path(root)/".env").write_text("MANJU_API_KEY=file-value",encoding="utf-8")
            app.read_env();self.assertEqual(os.environ["MANJU_API_KEY"],"process-value")
