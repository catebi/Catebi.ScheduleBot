"""Mirror WARNING/ERROR logs into a Telegram supergroup topic.

A logging handler forwards warnings and errors to a dedicated "alerts" topic so
the team sees failures immediately, with zero external infrastructure. The
destination is configured at runtime with ``/set_alert_topic`` (see
``app.handlers.commands``) and persisted in the settings table, so it survives
restarts. Pairs well with an error tracker (Sentry/GlitchTip): the tracker keeps
history and grouping, this gives an instant ping.
"""

import asyncio
import logging

from app import state
from app.bot_client import bot

_loop = None

# Cache the resolved chat entity so every alert doesn't hit get_entity.
_entity = None
_entity_chat_id = None

# Keep messages under Telegram's 4096-char limit (tracebacks can be long).
MAX_ALERT_LEN = 3500


def set_loop(loop):
    """Record the running bot loop; called once from ``app.main`` after start."""
    global _loop
    _loop = loop


async def load_alert_topic():
    """Populate the in-memory alert destination from persisted settings."""
    from app.data.settings_repo import load_settings

    settings = await load_settings()
    if settings.get("alert_chat_id"):
        state.alert_chat_id = settings.get("alert_chat_id")
        state.alert_topic_id = settings.get("alert_topic_id")


async def _resolve_entity(chat_id):
    global _entity, _entity_chat_id
    if _entity is None or _entity_chat_id != chat_id:
        from app.data.settings_repo import resolve_topic_entity

        _entity = await resolve_topic_entity(chat_id)
        _entity_chat_id = chat_id
    return _entity


async def _send(text, chat_id, topic_id):
    try:
        entity = await _resolve_entity(chat_id)
        # parse_mode=None: tracebacks contain _, *, ` which would break markdown.
        await bot.send_message(entity, text, reply_to=topic_id, parse_mode=None, link_preview=False)
    except Exception:
        # Never raise or log from here: an alert-delivery failure that logged an
        # error would feed straight back into this handler and could loop.
        pass


class TelegramAlertHandler(logging.Handler):
    """Forward WARNING+ log records to the configured Telegram alert topic."""

    def emit(self, record):
        # Telethon logs network hiccups (including ones from our own send) under
        # its own namespace; skipping it prevents an error -> send -> error loop.
        if record.name.startswith("telethon"):
            return

        chat_id = state.alert_chat_id
        if chat_id is None:
            return
        if _loop is None or not _loop.is_running():
            return

        try:
            text = self.format(record)
        except Exception:
            return
        if len(text) > MAX_ALERT_LEN:
            text = text[:MAX_ALERT_LEN] + "\n…(truncated)"

        coro = _send(text, chat_id, state.alert_topic_id)
        try:
            asyncio.run_coroutine_threadsafe(coro, _loop)
        except Exception:
            coro.close()


def install():
    """Attach the alert handler to the root logger (idempotent)."""
    root = logging.getLogger()
    if any(isinstance(h, TelegramAlertHandler) for h in root.handlers):
        return
    handler = TelegramAlertHandler(level=logging.WARNING)
    handler.setFormatter(logging.Formatter("%(levelname)s — %(name)s\n%(message)s"))
    root.addHandler(handler)
