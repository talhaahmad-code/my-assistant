"""Small JSON transport: no redirects/proxies, verified TLS, bounded bodies."""
import http.client
import json
import ssl
from urllib.parse import urlsplit


class ServiceError(Exception):
    """Carry only allowlisted codes and an optional numeric HTTP status."""

    CODES = frozenset({
        "invalid_endpoint", "http_error", "response_too_large", "timeout",
        "tls_error", "connection_error", "protocol_error", "invalid_json",
        "invalid_request", "invalid_model_response", "invalid_weather_response",
        "request_budget_exceeded", "telegram_api_error", "invalid_telegram_batch",
        "invalid_telegram_update",
    })

    def __init__(self, code: str, status: int | None = None):
        self.code = code if code in self.CODES else "service_error"
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        super().__init__(self.code)


class JsonClient:
    def __init__(self, connect_timeout=10, max_bytes=1_000_000):
        self.connect_timeout = connect_timeout
        self.max_bytes = max_bytes

    def request(self, url: str, payload: dict | None = None, timeout: float = 45) -> object:
        """Use separate connect/read timeouts, not a hard wall-clock deadline."""
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or parts.username or parts.password:
            raise ServiceError("invalid_endpoint")
        if parts.scheme == "https":
            connection_type = http.client.HTTPSConnection
        else:
            connection_type = http.client.HTTPConnection
        kwargs = {"timeout": min(self.connect_timeout, timeout)}
        if parts.scheme == "https":
            kwargs["context"] = ssl.create_default_context()
        connection = connection_type(parts.hostname, parts.port, **kwargs)
        try:
            body = json.dumps(payload).encode() if payload is not None else None
            connection.connect()
            connection.sock.settimeout(timeout)
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection.request("POST" if body is not None else "GET", path, body,
                               {"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                raise ServiceError("http_error", status=response.status)
            data = response.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                raise ServiceError("response_too_large")
            return json.loads(data)
        except ServiceError:
            raise
        except TimeoutError:
            raise ServiceError("timeout") from None
        except ssl.SSLError:
            raise ServiceError("tls_error") from None
        except OSError:
            raise ServiceError("connection_error") from None
        except http.client.HTTPException:
            raise ServiceError("protocol_error") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ServiceError("invalid_json") from None
        except (ValueError, UnicodeEncodeError):
            raise ServiceError("invalid_request") from None
        finally:
            connection.close()
