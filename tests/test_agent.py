import unittest
from unittest.mock import Mock
from personal_assistant.agent import Agent
from personal_assistant.config import Settings
from personal_assistant.tools.registry import ToolRegistry
from personal_assistant.http_client import ServiceError

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.weather = Mock(return_value={"high_c": 10})
        self.model = Mock()
        self.agent = Agent(self.model, ToolRegistry(self.weather), Settings("placeholder", frozenset({42})))
        self.call = {"function": {"name": "get_weather", "arguments": {}}}

    def test_plain_answer(self):
        self.model.chat.return_value = {"content": "Hello"}
        self.assertEqual(self.agent.respond("hi"), "Hello")
        self.weather.assert_not_called()

    def test_weather_lifecycle(self):
        self.model.chat.side_effect = [{"tool_calls": [self.call]}, {"content": "Cool today"}]
        self.assertEqual(self.agent.respond("weather"), "Cool today")
        self.weather.assert_called_once()
        self.assertEqual(self.model.chat.call_args.args[1], [])

    def test_tool_limit_and_malformed_calls(self):
        for calls in [[self.call]*3, [None], [{"function": {"name": "get_weather"}}]]:
            self.model.chat.return_value = {"tool_calls": calls}
            self.agent.respond("weather")
        self.weather.assert_not_called()

    def test_tool_validation_and_failure(self):
        registry = self.agent.registry
        for name, args in [("shell", {}), ("get_weather", {"path": "/"}), ("get_weather", "{}")]:
            self.assertIn("error", registry.execute(name, args))
        self.weather.assert_not_called()
        self.weather.side_effect = RuntimeError("sensitive")
        self.assertEqual(registry.execute("get_weather", {}), {"error": "Weather service unavailable"})

    def test_deadline(self):
        self.agent.clock = Mock(side_effect=[0, 401])
        with self.assertRaises(ServiceError):
            self.agent.respond("hi")
        self.model.chat.assert_not_called()
