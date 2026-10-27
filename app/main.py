import asyncio
import inspect
import logging

# Importing app.bot_client configures logging (via setup_logging) and builds the client.
from app import alerts
from app.airtable_logger import patch_model_methods
from app.bot_client import bot, bot_token
from app.data.airtable_async import shutdown_executor
from app.data.airtable_timeout import install_airtable_timeout
from app.flows import dispatch  # noqa: F401

# Importing these modules registers their @bot.on / @aiocron.crontab handlers.
from app.handlers import commands, text_input  # noqa: F401
from app.jobs import catflat, medical, scheduling  # noqa: F401
from app.services.schedule_service import update_volunteers


async def main():
    await bot.start(bot_token=bot_token)
    # Let the log-alert handler send onto this loop, and restore the saved topic.
    alerts.set_loop(asyncio.get_running_loop())
    await alerts.load_alert_topic()
    asyncio.Task(update_volunteers("startup"))
    await bot.run_until_disconnected()


def run():
    # Mirror WARNING/ERROR logs to the Telegram alert topic (no-op until set).
    alerts.install()
    # Add request logging to the ORM models before any Airtable call happens.
    patch_model_methods()
    # Enforce AIRTABLE_TIMEOUT, which pyairtable itself silently ignores.
    install_airtable_timeout()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped (Ctrl+C).")
    finally:
        try:
            result = bot.disconnect()
            if inspect.isawaitable(result):
                loop.run_until_complete(result)
        except Exception:
            logging.warning("Error while disconnecting the bot on shutdown.", exc_info=True)
        shutdown_executor()


if __name__ == "__main__":
    run()
