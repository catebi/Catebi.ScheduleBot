import asyncio
import logging

# Importing app.bot_client configures logging (via setup_logging) and builds the client.
from app.airtable_logger import patch_model_methods
from app.bot_client import bot, bot_token
from app.flows import dispatch  # noqa: F401

# Importing these modules registers their @bot.on / @aiocron.crontab handlers.
from app.handlers import commands, text_input  # noqa: F401
from app.jobs import catflat, medical, scheduling  # noqa: F401
from app.services.schedule_service import update_volunteers


async def main():
    await bot.start(bot_token=bot_token)
    asyncio.Task(update_volunteers("startup"))
    await bot.run_until_disconnected()


def run():
    # Add request logging to the ORM models before any Airtable call happens.
    patch_model_methods()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped (Ctrl+C).")


if __name__ == "__main__":
    run()
