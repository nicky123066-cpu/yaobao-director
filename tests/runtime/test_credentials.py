import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from credentials import CredentialStore,read_key,supported
from gateway import api_key,profiles,auto_settings


@unittest.skipUnless(supported(),"Windows DPAPI required")
class CredentialTests(unittest.TestCase):
    def test_roundtrip_persists_only_ciphertext(self):
        with tempfile.TemporaryDirectory() as root:
            vault=CredentialStore(root);vault.set("MANJU_API_KEY","test-local-secret-1234")
            self.assertNotIn(b"test-local-secret-1234",vault.path.read_bytes())
            self.assertEqual(CredentialStore(root).get("MANJU_API_KEY"),"test-local-secret-1234")

    def test_updating_one_provider_preserves_another(self):
        with tempfile.TemporaryDirectory() as root:
            vault=CredentialStore(root);vault.set("OPENAI_API_KEY","test-openai-key");vault.set("DEEPSEEK_API_KEY","test-deepseek-key")
            vault.set("OPENAI_API_KEY","test-openai-new-key")
            self.assertEqual(vault.get("DEEPSEEK_API_KEY"),"test-deepseek-key")
            self.assertEqual(vault.get("OPENAI_API_KEY"),"test-openai-new-key")

    def test_bad_storage_does_not_expose_or_overwrite_content(self):
        with tempfile.TemporaryDirectory() as root:
            vault=CredentialStore(root);vault.path.write_bytes(b"unreadable-cipher")
            self.assertIsNone(read_key(root,"MANJU_API_KEY"))
            with self.assertRaises(ValueError):vault.set("MANJU_API_KEY","test-valid-value")
            self.assertEqual(vault.path.read_bytes(),b"unreadable-cipher")

    def test_secret_available_to_gateway_but_absent_from_profiles(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{},clear=True):
            CredentialStore(root).set("DEEPSEEK_API_KEY","test-deepseek-secret")
            profile=next(p for p in profiles(root) if p["id"]=="deepseek")
            self.assertTrue(profile["key_available"]);self.assertEqual(profile["key_source"],"encrypted")
            self.assertNotIn("test-deepseek-secret",str(profiles(root)))
            config,_=auto_settings({"provider":"deepseek"},root)
            self.assertEqual(api_key(config,root),"test-deepseek-secret")
            self.assertIsNone(api_key({"key_env":"OPENAI_API_KEY"},root))

    def test_explicitly_selected_provider_wins_auto_detection(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{"MANJU_API_KEY":"another-configured-key"},clear=True):
            CredentialStore(root).set("DEEPSEEK_API_KEY","test-deepseek-secret")
            config,_=auto_settings({"provider":"deepseek"},root)
            self.assertEqual(config["provider"],"deepseek")

    def test_header_injection_is_rejected_before_storage(self):
        with tempfile.TemporaryDirectory() as root:
            vault=CredentialStore(root)
            for secret in ["short","test-key\r\nAuthorization: anything","contains spaces"]:
                with self.assertRaises(ValueError):vault.set("MANJU_API_KEY",secret)
            self.assertFalse(vault.path.exists())
