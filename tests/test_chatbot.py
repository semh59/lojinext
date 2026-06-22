import asyncio
import logging
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_chatbot")

from app.core.ai.groq_service import get_groq_service


async def test_direct_chat():
    logger.info("Initializing Groq chatbot...")
    chatbot = get_groq_service()

    if not chatbot.client:
        logger.error("Groq client not initialized (check API key)")
        return

    logger.info("Sending 'merhaba' to chatbot...")
    try:
        # We'll use a timeout here to avoid infinite hang in test
        response = await asyncio.wait_for(chatbot.chat("merhaba"), timeout=60)
        logger.info(f"Response received: {response}")
    except asyncio.TimeoutError:
        logger.error("Chatbot generation timed out (60s)")
    except Exception as e:
        logger.error(f"Caught Exception: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_direct_chat())
