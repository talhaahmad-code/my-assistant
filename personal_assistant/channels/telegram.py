import logging
import time
import uuid
from personal_assistant.http_client import ServiceError
from personal_assistant.logging_setup import event, failure
from personal_assistant.security import RateLimiter, authorized, validate_text


class TelegramChannel:
    def __init__(self, client, agent, settings, clock=time.time, sleep=time.sleep):
        self.client = client
        self.agent = agent
        self.settings = settings
        self.clock = clock
        self.sleep = sleep
        self.limiter = RateLimiter(settings.rate_limit)
        self.offset = None

    def api(self, method: str, payload: dict) -> object:
        result = self.client.request(
            f"https://api.telegram.org/bot{self.settings.telegram_token}/{method}",
            payload, timeout=self.settings.external_timeout)
        if not isinstance(result, dict) or result.get("ok") is not True or "result" not in result:
            raise ServiceError("telegram_api_error")
        return result["result"]

    def send(self, chat_id: int, text: str) -> None:
        # Telegram counts UTF-16 code units; also leave space below its limit.
        text = text.encode("utf-16-le")[:8000].decode("utf-16-le", errors="ignore")
        self.api("sendMessage", {"chat_id": chat_id, "text": text})

    def handle(self, update: dict, received_at: float | None = None) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return
        if not authorized(message, self.settings.allowed_users):
            event("authorization_failed", logging.WARNING)
            return
        stamp = message.get("date")
        if received_at is None:
            received_at = self.clock()
        valid_date = (
            type(stamp) in (int, float)
            and 0 <= received_at - stamp <= self.settings.max_message_age
        )
        if not valid_date:
            event("message_ignored", reason="stale_or_invalid_date")
            return
        user = message["from"]["id"]
        if not self.limiter.allow(user):
            # Stay silent to avoid an outbound reply flood.
            event("rate_limit_rejected", logging.WARNING)
            return
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        event("request_received", request_id=request_id)
        try:
            text = message.get("text")
            error = validate_text(text, self.settings.max_message_length)
            if error:
                event("input_rejected", request_id=request_id)
                answer = error
            elif text.split()[0] == "/start":
                answer = "Hello! Ask me about the weather."
            elif text.startswith("/"):
                answer = "Unknown command. Send a question, or use /start."
            else:
                try:
                    answer = self.agent.respond(text)
                except ServiceError as error:
                    failure("request_service_failed", error, logging.WARNING, request_id=request_id)
                    answer = "A required service is unavailable or timed out. Please try again."
                except Exception as error:
                    failure("request_failed", error, request_id=request_id)
                    answer = "Something went wrong. Please try again."
            self.send(message["chat"]["id"], answer)
        finally:
            event("request_finished", request_id=request_id,
                  duration_ms=round((time.monotonic()-started)*1000))

    def poll_once(self) -> None:
        """Process a bounded batch; acknowledge its offsets on the next poll."""
        updates = self.api("getUpdates", {
            "offset": self.offset,
            "timeout": 25,
            "limit": self.settings.poll_limit,
            "allowed_updates": ["message"],
        })
        # Freeze freshness before slow inference can age later entries in this batch.
        received_at = self.clock()
        if not isinstance(updates, list) or len(updates) > self.settings.poll_limit:
            raise ServiceError("invalid_telegram_batch")
        for update in updates:
            if not isinstance(update, dict) or type(update.get("update_id")) is not int:
                raise ServiceError("invalid_telegram_update")
            if self.offset is not None and update["update_id"] < self.offset:
                continue
            self.offset = update["update_id"] + 1
            try:
                self.handle(update, received_at=received_at)
            except Exception as error:
                # Do not retry a potentially delivered response or re-run inference.
                failure("update_failed", error)

    def run(self) -> None:
        event("assistant_started")
        try:
            while True:
                try:
                    self.poll_once()
                except Exception as error:
                    failure("poll_failed", error)
                    self.sleep(5)
        except KeyboardInterrupt:
            event("assistant_stopped")
