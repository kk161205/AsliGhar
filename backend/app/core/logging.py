import logging
import re

# SerpApi authenticates through an `api_key` query parameter. httpx logs every
# request URL at INFO, and its raise_for_status errors embed the URL too, so
# without this the key lands in the log stream in plaintext — in production,
# that's a log platform everyone with dashboard access can read.
_API_KEY_PATTERN = re.compile(r"(api_key=)[^&\s'\"]+", re.IGNORECASE)


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _API_KEY_PATTERN.sub(r"\1[redacted]", message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Filters on a logger don't apply to records propagated from other
    # loggers (httpx's, for one), so attach to the handlers, which see everything.
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactSecretsFilter())
