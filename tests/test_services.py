import unittest
from unittest.mock import Mock
from personal_assistant.config import Settings
from personal_assistant.ollama import OllamaClient
from personal_assistant.tools.weather import WeatherTool
from personal_assistant.http_client import ServiceError

class ServiceTests(unittest.TestCase):
    def test_model_responses(self):
        client = Mock()
        model = OllamaClient(client, Settings("placeholder", frozenset({42})))
        for result in [None, {}, {"message": []}, {"message": {"role": "user"}},
                       {"message": {"role": "assistant", "content": 123}},
                       {"message": {"role": "assistant", "tool_calls": {}}}]:
            client.request.return_value = result
            with self.subTest(result=result), self.assertRaises(ServiceError):
                model.chat([], [])
        client.request.return_value = {"message": {"role": "assistant", "content": "ok"}}
        self.assertEqual(model.chat([], [])["content"], "ok")
        client.request.side_effect = ServiceError("timeout")
        with self.assertRaises(ServiceError):
            model.chat([], [])

    def test_weather(self):
        client = Mock()
        tool = WeatherTool(client, "America/Toronto", 45)
        daily = {"time": ["2026-10-26"], "temperature_2m_max": [10], "temperature_2m_min": [2],
                 "precipitation_sum": [0], "precipitation_probability_max": [None], "weather_code": [3]}
        client.request.return_value = {"daily": daily}
        self.assertEqual(tool()["high_c"], 10)
        self.assertIsNone(tool()["peak_hourly_rain_or_snow_probability_pct"])
        for value in [{}, {"daily": {}}, {"daily": {**daily, "time": []}},
                      {"daily": {**daily, "temperature_2m_max": ["bad"]}}]:
            client.request.return_value = value
            with self.assertRaises(ServiceError):
                tool()
