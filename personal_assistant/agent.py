"""A bounded, two-call model/tool conversation for each user request."""
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from personal_assistant.http_client import ServiceError


def valid_tool_call(call: object) -> bool:
    """Check the envelope; the registry validates names and arguments."""
    if not isinstance(call, dict):
        return False
    function = call.get("function")
    if not isinstance(function, dict):
        return False
    return isinstance(function.get("name"), str) and "arguments" in function


class Agent:
    def __init__(self, model, registry, settings, clock=time.monotonic):
        self.model = model
        self.registry = registry
        self.settings = settings
        self.clock = clock

    def respond(self, text: str) -> str:
        """Ask once for tools, then once for an answer; never loop indefinitely."""
        deadline = self.clock() + self.settings.request_budget

        def remaining():
            # This bounds subsequent operations, not an already-running tool.
            value = deadline - self.clock()
            if value <= 0:
                raise ServiceError("request_budget_exceeded")
            return value

        now = datetime.now(ZoneInfo(self.settings.timezone)).isoformat()
        system_prompt = (
            "You are a concise personal AI assistant. "
            f"The current local time is {now}. "
            "Use tools for live data. Never invent weather observations. "
            "Weather precipitation probability is the maximum hourly probability, not all-day probability. "
            "Acknowledge tool failures and missing weather values."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        response = self.model.chat(messages, self.registry.schemas, timeout=remaining())
        calls = response.get("tool_calls", [])
        if not calls:
            return response.get("content") or "I couldn't answer that."
        if len(calls) > self.settings.max_tool_calls:
            return "The model requested too many tools. Please try a simpler request."

        # Validate the whole batch before executing any tools.
        if not all(valid_tool_call(call) for call in calls):
            return "The model returned an invalid tool request. Please try again."

        messages.append(response)
        for call in calls:
            remaining()
            function = call["function"]
            result = self.registry.execute(function["name"], function["arguments"])
            messages.append({
                "role": "tool",
                "tool_name": function["name"],
                "content": json.dumps(result),
            })

        final = self.model.chat(messages, [], timeout=remaining())
        if final.get("tool_calls"):
            return "The model requested more tools than this request allows. Please try again."
        return final.get("content") or "No response generated."
