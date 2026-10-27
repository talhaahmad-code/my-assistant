import time
import logging
from personal_assistant.config import validate_ollama_url
from personal_assistant.http_client import ServiceError
from personal_assistant.logging_setup import event, failure


class OllamaClient:
    def __init__(self, client, settings):
        self.client = client
        self.settings = settings
        self.url = validate_ollama_url(settings.ollama_url)

    def chat(self, messages: list[dict], tools: list[dict], timeout: float | None = None) -> dict:
        started = time.monotonic()
        read_timeout = self.settings.inference_timeout
        if timeout is not None:
            read_timeout = min(timeout, read_timeout)
        try:
            result = self.client.request(self.url, {
                "model": self.settings.model,
                "messages": messages,
                "tools": tools,
                "think": False,
                "stream": False,
            }, timeout=read_timeout)
            message = result.get("message") if isinstance(result, dict) else None
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise ServiceError("invalid_model_response")
            content = message.get("content", "")
            calls = message.get("tool_calls", [])
            if not isinstance(content, str) or not isinstance(calls, list):
                raise ServiceError("invalid_model_response")
            # JSON can contain escaped lone surrogates that cannot be sent as text.
            try:
                content.encode("utf-8")
            except UnicodeEncodeError:
                raise ServiceError("invalid_model_response") from None
            # Tool-selection replies may legitimately contain no prose.
            if not calls and not content.strip():
                raise ServiceError("invalid_model_response")
            return {"role": "assistant", "content": content, "tool_calls": calls}
        except Exception as error:
            failure("inference_failed", error, logging.WARNING)
            raise
        finally:
            event("inference_finished", duration_ms=round((time.monotonic()-started)*1000))
