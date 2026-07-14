"""Free-text input handler for the 'set custom notification text' flow.

Only fires when the sender has an active entry in ``state.custom_text_setting``
(set by the notifications settings flow), acting as a small per-user FSM.
"""

import logging

from pyairtable.formulas import match
from telethon import Button, events

from app import state
from app.bot_client import bot
from app.data.notification_repo import get_or_create_notification
from app.logging_setup import logger
from app.models import Volunteer
from app.translations import (
    button_back,
    error_custom_text,
    notifications_settings_text_success,
)


@bot.on(events.NewMessage(func=lambda e: e.is_private and e.sender.id in state.custom_text_setting))
@logger
async def custom_notifications_handler(event):
    logging.info(f"Custom text setting: {event.sender.id}, {event.message.message}")

    volunteer = Volunteer.first(formula=match({"telegram_chat_id": event.sender.id}))
    admin = get_or_create_notification(event.sender.id, volunteer=volunteer, admin_curator=event.sender.username)

    custom_text = str(event.message.message)
    if custom_text.startswith("/"):
        await event.respond(error_custom_text[admin.volunteer.language])
        raise events.StopPropagation

    # Normalize any {placeholder} to an empty {} for later .format() insertion.
    if "{" in custom_text and "}" in custom_text:
        pre_curly, _, _ = custom_text.partition("{")
        _, _, post_curly = custom_text.partition("}")
        custom_text = pre_curly + r"{}" + post_curly

    pending = state.custom_text_setting[event.sender.id]
    if pending["type"] == "cleaning":
        admin.custom_text_cleaning = custom_text
    elif pending["type"] == "medical":
        admin.custom_text_medical = custom_text
    admin.save()

    prompt = pending["prompt"]
    await prompt.edit(prompt.message, buttons=None)  # remove buttons to avoid repeat clicks
    await event.respond(
        notifications_settings_text_success[admin.volunteer.language],
        buttons=[Button.inline(button_back[admin.volunteer.language], data="notifications;;")],
    )

    state.custom_text_setting.pop(event.sender.id)
