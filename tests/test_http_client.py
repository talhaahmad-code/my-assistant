import unittest
from unittest.mock import patch
from personal_assistant.http_client import JsonClient, ServiceError

class HttpTests(unittest.TestCase):
    @patch("personal_assistant.http_client.http.client.HTTPSConnection")
    def test_tls_and_bounded_read(self, factory):
        connection = factory.return_value
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = b'{"ok": true}'
        self.assertEqual(JsonClient().request("https://example.test/api"), {"ok": True})
        self.assertTrue(factory.call_args.kwargs["context"].check_hostname)
        response.read.assert_called_once_with(1_000_001)
        connection.close.assert_called_once()

    @patch("personal_assistant.http_client.http.client.HTTPConnection")
    def test_failures(self, factory):
        connection = factory.return_value
        response = connection.getresponse.return_value
        for status, body in [(302, b'{}'), (500, b'secret'), (200, b'invalid'), (200, b'x' * 11)]:
            response.status, response.read.return_value = status, body
            with self.subTest(status=status, body=body), self.assertRaises(ServiceError):
                JsonClient(max_bytes=10).request("http://127.0.0.1/api/chat")
        connection.connect.side_effect = TimeoutError("secret")
        with self.assertRaisesRegex(ServiceError, "timeout"):
            JsonClient().request("http://127.0.0.1/api/chat")

    @patch("personal_assistant.http_client.http.client.HTTPConnection")
    def test_distinct_safe_failure_codes(self, factory):
        import ssl
        connection = factory.return_value
        for error, code in [
            (TimeoutError("private URL"), "timeout"),
            (ssl.SSLError("private URL"), "tls_error"),
            (ConnectionRefusedError("private URL"), "connection_error"),
        ]:
            connection.connect.side_effect = error
            with self.subTest(code=code), self.assertRaises(ServiceError) as caught:
                JsonClient().request("http://127.0.0.1/api/chat")
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("private", str(caught.exception))
        connection.connect.side_effect = None
        response = connection.getresponse.return_value
        response.status = 401
        with self.assertRaises(ServiceError) as caught:
            JsonClient().request("http://127.0.0.1/api/chat")
        self.assertEqual(caught.exception.status, 401)
        response.status = 200
        response.read.return_value = b'not JSON'
        with self.assertRaises(ServiceError) as caught:
            JsonClient().request("http://127.0.0.1/api/chat")
        self.assertEqual(caught.exception.code, "invalid_json")

    def test_logs_never_include_arbitrary_error_text(self):
        from personal_assistant.logging_setup import failure
        for error in [ServiceError("secret-token"), RuntimeError("secret-token")]:
            with self.assertLogs("personal_assistant") as logs:
                failure("test_failure", error)
            self.assertNotIn("secret-token", str(logs.output))
