"""Exercise the wired channel, agent, model, registry and weather without I/O."""
import unittest
from unittest.mock import Mock, patch
from personal_assistant.agent import Agent
from personal_assistant.channels.telegram import TelegramChannel
from personal_assistant.config import Settings
from personal_assistant.ollama import OllamaClient
from personal_assistant.tools.registry import ToolRegistry
from personal_assistant.tools.weather import WeatherTool


class IntegrationTests(unittest.TestCase):
    def test_weather_round_trip(self):
        settings = Settings("placeholder", frozenset({42}))
        client = Mock()
        daily = {"time": ["2026-10-26"], "temperature_2m_max": [10], "temperature_2m_min": [2],
                 "precipitation_sum": [0], "precipitation_probability_max": [20], "weather_code": [3]}
        client.request.side_effect = [
            {"ok": True, "result": [{"update_id": 1, "message": {
                "from": {"id": 42}, "chat": {"id": 42, "type": "private"},
                "text": "weather", "date": 1000}}]},
            {"message": {"role": "assistant", "tool_calls": [
                {"function": {"name": "get_weather", "arguments": {}}}]}},
            {"daily": daily},
            {"message": {"role": "assistant", "content": "High 10°C."}},
            {"ok": True, "result": {}},
        ]
        agent = Agent(OllamaClient(client, settings),
                      ToolRegistry(WeatherTool(client, settings.timezone, 45)), settings)
        channel = TelegramChannel(client, agent, settings, clock=lambda: 1000)
        channel.poll_once()
        self.assertEqual(client.request.call_count, 5)
        self.assertEqual(client.request.call_args.args[1]["text"], "High 10°C.")
        self.assertEqual(channel.offset, 2)

    def test_import_does_not_load_settings(self):
        import importlib
        with patch("personal_assistant.config.load_settings", side_effect=AssertionError("No credentials")):
            import assistant
            importlib.reload(assistant)

    def test_unicode_response_is_bounded(self):
        channel = TelegramChannel(Mock(), Mock(), Settings("placeholder", frozenset({42})))
        channel.api = Mock()
        channel.send(42, "😀" * 4000)
        text = channel.api.call_args.args[1]["text"]
        self.assertLessEqual(len(text.encode("utf-16-le")), 8000)

    def test_invalid_model_text_gets_safe_reply(self):
        settings = Settings("placeholder", frozenset({42}))
        for text in ["\ud800", "\udfff", "", " \n\t"]:
            with self.subTest(text=repr(text)):
                client = Mock()
                client.request.return_value = {"message": {"role": "assistant", "content": text}}
                agent = Agent(OllamaClient(client, settings), ToolRegistry(Mock()), settings)
                channel = TelegramChannel(Mock(), agent, settings, clock=lambda: 1000)
                channel.api = Mock()
                channel.handle({"message": {
                    "from": {"id": 42}, "chat": {"id": 42, "type": "private"},
                    "date": 1000, "text": "hello",
                }})
                reply = channel.api.call_args.args[1]["text"]
                self.assertTrue(reply.strip())
                reply.encode("utf-8")
                self.assertNotIn("invalid_model_response", reply)
