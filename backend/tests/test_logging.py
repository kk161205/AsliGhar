import logging

from app.core.logging import RedactSecretsFilter


def _record(message: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord("test", logging.INFO, __file__, 1, message, args, None)


def test_redacts_api_key_in_an_httpx_style_request_line() -> None:
    record = _record(
        'HTTP Request: GET https://serpapi.com/search?q=rent&api_key=SECRET123&engine=google "HTTP/1.1 200 OK"'
    )
    RedactSecretsFilter().filter(record)
    message = record.getMessage()
    assert "SECRET123" not in message
    assert "api_key=[redacted]" in message
    assert "engine=google" in message


def test_redacts_api_key_inside_a_formatted_exception_message() -> None:
    error = "Client error '429' for url 'https://serpapi.com/search?url=x&api_key=SECRET123'"
    record = _record("google_lens failed for photo %s: %s", 0, error)
    RedactSecretsFilter().filter(record)
    message = record.getMessage()
    assert "SECRET123" not in message
    assert "google_lens failed for photo 0" in message


def test_leaves_unrelated_messages_untouched() -> None:
    record = _record("Scan %s completed: user=%s score=%s", "abc", "u1", 42)
    RedactSecretsFilter().filter(record)
    assert record.getMessage() == "Scan abc completed: user=u1 score=42"
