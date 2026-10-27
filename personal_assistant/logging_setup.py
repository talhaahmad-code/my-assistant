"""Only explicitly supplied, non-sensitive event fields are logged."""
import json
import logging

logger = logging.getLogger("personal_assistant")


def event(name, level=logging.INFO, **fields):
    logger.log(level, json.dumps({"event": name, **fields}, sort_keys=True))


def failure(name, error: Exception, level=logging.ERROR, **fields):
    """Log controlled categories, never exception strings or response bodies."""
    from personal_assistant.http_client import ServiceError

    if isinstance(error, ServiceError):
        fields["error_code"] = error.code
        if error.status is not None:
            fields["http_status"] = error.status
    else:
        fields["error_code"] = "unexpected_error"
    event(name, level, **fields)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
