import unittest
from unittest.mock import Mock
from personal_assistant.channels.telegram import TelegramChannel
from personal_assistant.config import Settings
from personal_assistant.http_client import ServiceError
from personal_assistant.security import RateLimiter, validate_text

class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.client, self.agent = Mock(), Mock()
        self.channel = TelegramChannel(self.client, self.agent, Settings("private-token", frozenset({42})), clock=lambda: 1000)
        self.channel.send = Mock()
        self.message = {"from": {"id": 42}, "chat": {"type": "private", "id": 42}, "date": 999, "text": "hello"}
        self.agent.respond.return_value = "hi"

    def handle(self, **changes):
        self.channel.handle({"message": {**self.message, **changes}})

    def test_authorization_before_commands(self):
        for text in ["hello", "/start", "/id"]:
            self.handle(text=text, **{"from": {"id": 7}})
            self.handle(text=text, chat={"type": "group", "id": 42})
        self.handle(chat={"type": "private", "id": 7})
        self.agent.respond.assert_not_called()
        self.channel.send.assert_not_called()

    def test_supported_and_invalid_messages(self):
        self.handle()
        self.agent.respond.assert_called_once_with("hello")
        self.agent.reset_mock()
        for text in [None, "", " ", "a" * 2001, "/start", "/id"]:
            self.handle(text=text)
        self.agent.respond.assert_not_called()

    def test_stale_and_rate_limit(self):
        self.handle(date=1)
        self.agent.respond.assert_not_called()
        for _ in range(11):
            self.handle()
        self.assertEqual(self.agent.respond.call_count, 10)

    def test_errors_are_private(self):
        for error in [ServiceError("secret"), RuntimeError("secret")]:
            self.agent.respond.side_effect = error
            with self.assertLogs("personal_assistant", level="INFO") as logs:
                self.handle(text="private-prompt")
            self.assertNotIn("secret", self.channel.send.call_args.args[1])
            self.assertNotIn("private-prompt", str(logs.output))
            self.assertNotIn("private-token", str(logs.output))

    def test_poll_bounds_and_offsets(self):
        self.channel.api = Mock(return_value=[{"update_id": 10, "message": self.message}])
        self.channel.poll_once()
        self.assertEqual(self.channel.offset, 11)
        self.channel.poll_once()
        self.assertEqual(self.agent.respond.call_count, 1)
        self.channel.api.return_value = [{}] * 11
        with self.assertRaises(ServiceError):
            self.channel.poll_once()

    def test_shutdown(self):
        self.channel.poll_once = Mock(side_effect=KeyboardInterrupt)
        self.channel.run()

class SecurityTests(unittest.TestCase):
    def test_rate_window_and_user_isolation(self):
        clock = Mock(return_value=0)
        limiter = RateLimiter(2, clock)
        self.assertTrue(limiter.allow(1))
        self.assertTrue(limiter.allow(1))
        self.assertFalse(limiter.allow(1))
        self.assertTrue(limiter.allow(2))
        clock.return_value = 60
        self.assertTrue(limiter.allow(1))

    def test_input_boundaries(self):
        self.assertIsNone(validate_text("abc", 3))
        self.assertIsNotNone(validate_text("abcd", 3))
        self.assertIsNotNone(validate_text([], 3))

class BatchTimingTests(unittest.TestCase):
    def test_slow_first_request_does_not_expire_fresh_batch(self):
        clock = Mock(return_value=1000)
        agent = Mock()

        def slow_reply(text):
            clock.return_value += 301
            return "answer"

        agent.respond.side_effect = slow_reply
        channel = TelegramChannel(Mock(), agent, Settings("placeholder", frozenset({42})), clock=clock)
        channel.api = Mock(return_value=[
            {"update_id": index, "message": {
                "from": {"id": 42}, "chat": {"id": 42, "type": "private"},
                "date": stamp, "text": "hello",
            }}
            for index, stamp in [(1, 1000), (2, 1000), (3, 699)]
        ])
        channel.send = Mock()
        channel.poll_once()
        self.assertEqual(agent.respond.call_count, 2)
        self.assertEqual(channel.send.call_count, 2)
        self.assertEqual(channel.offset, 4)

    def test_poll_logs_safe_status_and_recovers(self):
        channel = TelegramChannel(Mock(), Mock(), Settings("placeholder", frozenset({42})))
        channel.poll_once = Mock(side_effect=[ServiceError("http_error", status=401), KeyboardInterrupt])
        channel.sleep = Mock()
        with self.assertLogs("personal_assistant", level="INFO") as logs:
            channel.run()
        self.assertIn('"http_status": 401', str(logs.output))
        self.assertIn('"error_code": "http_error"', str(logs.output))
        channel.sleep.assert_called_once_with(5)
