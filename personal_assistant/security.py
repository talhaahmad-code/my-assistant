from collections import deque
import time


def authorized(message: dict, allowed_users: frozenset[int]) -> bool:
    sender = message.get("from")
    chat = message.get("chat")
    if not isinstance(sender, dict) or not isinstance(chat, dict):
        return False
    if chat.get("type") != "private":
        return False
    user_id = sender.get("id")
    chat_id = chat.get("id")
    return (
        type(user_id) is int
        and user_id in allowed_users
        and type(chat_id) is int
        and chat_id == user_id
    )


class RateLimiter:
    def __init__(self, limit=10, clock=time.monotonic):
        self.limit = limit
        self.clock = clock
        self.requests = {}

    def allow(self, user: int) -> bool:
        now = self.clock()
        history = self.requests.setdefault(user, deque())
        while history and history[0] <= now - 60:
            history.popleft()
        if len(history) >= self.limit:
            return False
        history.append(now)
        return True


def validate_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "Please send a text message."
    if len(value) > limit:
        return f"Please keep messages within {limit} characters."
    return None
