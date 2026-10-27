import logging
import time
from personal_assistant.logging_setup import event, failure

WEATHER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "Get today's weather forecast for Kanata, Ottawa, "
            "for weather, clothing or umbrella questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
}


class ToolRegistry:
    def __init__(self, weather):
        self.weather = weather
        self.schemas = [WEATHER_SCHEMA]

    def execute(self, name: str, arguments: object) -> dict:
        if name != "get_weather":
            event("tool_rejected", reason="unknown_tool")
            return {"error": "Unknown or unauthorized tool"}
        if not isinstance(arguments, dict) or arguments:
            event("tool_rejected", reason="invalid_arguments")
            return {"error": "get_weather requires an empty argument object"}
        started = time.monotonic()
        event("tool_selected", tool="get_weather")
        try:
            return self.weather()
        except Exception as error:
            failure("tool_failed", error, logging.WARNING, tool="get_weather")
            return {"error": "Weather service unavailable"}
        finally:
            event("tool_finished", tool="get_weather", duration_ms=round((time.monotonic()-started)*1000))
