import asyncio
import logging

from app.services import groq_client, serpapi_client

logger = logging.getLogger(__name__)


async def check_dependencies() -> dict[str, bool]:
    """Live-verify both external API keys concurrently. Cheap: neither call spends quota."""
    serpapi_ok, groq_ok = await asyncio.gather(
        serpapi_client.verify_key(), groq_client.verify_key()
    )
    status = {"serpapi": serpapi_ok, "groq": groq_ok}
    if all(status.values()):
        logger.info("Dependency verification passed: %s", status)
    else:
        logger.error("Dependency verification FAILED: %s", status)
    return status
