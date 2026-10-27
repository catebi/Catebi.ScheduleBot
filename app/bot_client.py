"""Shared client instances: the Telethon bot and the raw Airtable API.

The bot is *constructed* here (no network I/O) and *connected* in
``app.main.main()`` via ``bot.start(...)``. Importing this module is therefore
side-effect free apart from setting the process timezone, which lets the rest
of the package be imported for tooling/verification without a live connection.
"""

import asyncio
import logging
import os
import time
from datetime import datetime

from pyairtable import Api
from telethon import TelegramClient

from app.config import (
    AIRTABLE_TIMEOUT,
    SESSION_NAME,
    TIMEZONE,
    airtable_api_key,
    api_hash,
    api_id,
    bot_token,
)
from app.logging_setup import setup_logging

# Configure logging before anything (including the timezone line below) logs.
setup_logging()

# Ensure an event loop exists in this thread before import-time schedulers
# (aiocron.crontab) run. On Python <=3.12 get_event_loop() auto-created one;
# on 3.12+ it can raise, so create one explicitly. run() reuses this same loop.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Set the process timezone before any datetime math runs.
os.environ["TZ"] = TIMEZONE
time.tzset()
logging.info(f"Timezone set to {os.environ['TZ']}, time is {datetime.now()}.")

# Raw Airtable API client for the sterilization base (used outside the ORM).
sterilization_api = Api(api_key=airtable_api_key, timeout=AIRTABLE_TIMEOUT) if airtable_api_key else None

# The Telegram bot client. Connect with ``await bot.start(bot_token=bot_token)``.
bot = TelegramClient(SESSION_NAME, api_id, api_hash)

__all__ = ["bot", "sterilization_api", "bot_token"]
