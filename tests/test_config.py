import unittest
from personal_assistant.config import Settings, ConfigurationError, validate_ollama_url

class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        settings = Settings.from_mapping({"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_ALLOWED_USER_ID": "42"})
        self.assertEqual(settings.allowed_users, {42})
        self.assertNotIn("test-token", repr(settings))

    def test_invalid_settings(self):
        base = {"TELEGRAM_BOT_TOKEN": "placeholder", "TELEGRAM_ALLOWED_USER_ID": "42"}
        for key, value in [("TELEGRAM_ALLOWED_USER_ID", "0"), ("TIMEZONE", "invalid"),
                           ("POLL_LIMIT", "101"), ("INFERENCE_TIMEOUT", "nan"),
                           ("MAX_TOOL_CALLS", "0"), ("OLLAMA_MODEL", "model:cloud")]:
            with self.subTest(key=key), self.assertRaises(ConfigurationError):
                Settings.from_mapping(dict(base, **{key: value}))

    def test_local_endpoints_only(self):
        for url in ["http://example.com/api/chat", "http://127.0.0.1.evil/api/chat",
                    "http://user@localhost/api/chat", "http://localhost/api/chat?x=1",
                    "https://localhost/api/chat", "http://0.0.0.0/api/chat"]:
            with self.subTest(url=url), self.assertRaises(ConfigurationError):
                validate_ollama_url(url)
        self.assertEqual(validate_ollama_url("http://localhost:11434/api/chat"),
                         "http://127.0.0.1:11434/api/chat")
        validate_ollama_url("http://[::1]:11434/api/chat")
