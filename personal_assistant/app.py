from pathlib import Path
from personal_assistant.agent import Agent
from personal_assistant.channels.telegram import TelegramChannel
from personal_assistant.config import ConfigurationError, load_settings
from personal_assistant.http_client import JsonClient
from personal_assistant.logging_setup import configure_logging, event
from personal_assistant.ollama import OllamaClient
from personal_assistant.tools.registry import ToolRegistry
from personal_assistant.tools.weather import WeatherTool


def main() -> int:
    configure_logging()
    try:
        settings = load_settings(Path(__file__).resolve().parent.parent)
    except (ConfigurationError, ImportError):
        event("startup_failed", reason="check_configuration_and_dependencies")
        return 1
    client = JsonClient(settings.connect_timeout)
    weather = WeatherTool(client, settings.timezone, settings.external_timeout)
    agent = Agent(OllamaClient(client, settings), ToolRegistry(weather), settings)
    TelegramChannel(client, agent, settings).run()
    return 0
