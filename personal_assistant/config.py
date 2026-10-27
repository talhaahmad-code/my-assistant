"""Configuration is loaded explicitly at startup, never on import."""
from dataclasses import dataclass, field
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import math


class ConfigurationError(ValueError):
    pass


def validate_ollama_url(value: str) -> str:
    try:
        url = urlsplit(value)
        host = url.hostname
        local = host == "localhost" or (host is not None and ip_address(host).is_loopback)
        port = url.port
        if (url.scheme != "http" or not local or url.username or url.password
                or url.path != "/api/chat" or url.query or url.fragment
                or port == 0):
            raise ValueError
    except ValueError:
        raise ConfigurationError("OLLAMA_URL must be a loopback HTTP /api/chat endpoint") from None
    # Avoid DNS resolution even when configuration uses localhost.
    if host == "localhost":
        return f"http://127.0.0.1:{port or 80}/api/chat"
    return value


@dataclass(frozen=True)
class Settings:
    telegram_token: str = field(repr=False)
    allowed_users: frozenset[int] = field(repr=False)
    ollama_url: str = "http://127.0.0.1:11434/api/chat"
    model: str = "qwen3.5:4b"
    timezone: str = "America/Toronto"
    rate_limit: int = 10
    max_message_length: int = 2000
    max_tool_calls: int = 2
    poll_limit: int = 10
    max_message_age: float = 300
    connect_timeout: float = 10
    inference_timeout: float = 180
    external_timeout: float = 45
    request_budget: float = 400

    @classmethod
    def from_mapping(cls, values: dict[str, str]) -> "Settings":
        try:
            token = values.get("TELEGRAM_BOT_TOKEN", "").strip()
            user = int(values.get("TELEGRAM_ALLOWED_USER_ID", "0"))
            if not token or user <= 0:
                raise ConfigurationError("Set a bot token and a positive allowed user ID")
            timezone = values.get("TIMEZONE", "America/Toronto")
            ZoneInfo(timezone)
            model = values.get("OLLAMA_MODEL", "qwen3.5:4b").strip()
            if not model or "cloud" in model.lower() or "://" in model:
                raise ConfigurationError("Choose an installed local Ollama model")
            options = {}
            for name in ("rate_limit", "max_message_length", "max_tool_calls", "poll_limit"):
                options[name] = int(values.get(name.upper(), getattr(cls, name)))
                if options[name] <= 0:
                    raise ValueError
            if options["poll_limit"] > 100 or options["max_message_length"] > 4096:
                raise ValueError
            for name in ("max_message_age", "connect_timeout", "inference_timeout",
                         "external_timeout", "request_budget"):
                options[name] = float(values.get(name.upper(), getattr(cls, name)))
                if not math.isfinite(options[name]) or options[name] <= 0:
                    raise ValueError
            if options["external_timeout"] <= 25:
                raise ConfigurationError("EXTERNAL_TIMEOUT must exceed the 25 second long poll")
            return cls(token, frozenset({user}),
                       validate_ollama_url(values.get("OLLAMA_URL", cls.ollama_url)),
                       model, timezone, **options)
        except ConfigurationError:
            raise
        except (ValueError, TypeError, ZoneInfoNotFoundError):
            raise ConfigurationError("Invalid configuration: check numeric limits and timezone") from None


def load_settings(root: Path) -> Settings:
    import os
    from dotenv import load_dotenv
    load_dotenv(root / ".env")
    return Settings.from_mapping(os.environ)
