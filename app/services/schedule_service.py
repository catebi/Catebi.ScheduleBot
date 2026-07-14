"""Schedule aggregation and the pinned topic-message refresh.

``update_volunteers`` rebuilds the cached "today" and "other dates" lists and
keeps the pinned schedule messages in the group topics up to date.
"""

import asyncio
import logging
from datetime import datetime

from pyairtable.formulas import match
from telethon import errors

from app import state
from app.airtable_logger import airtable_context
from app.bot_client import bot
from app.constants import SUPERGROUP_ID_PREFIX, TYPE_STERIL_ACCEPTANCE
from app.data.coerce import to_local
from app.data.settings_repo import load_settings, resolve_topic_entity
from app.models import Schedule, Settings
from app.text.labels import NBSP, build_label
from app.translations import general_schedule, loading_text


async def show_loading_state(event, user_language: str):
    """Show a loading message and remove buttons to prevent double-presses."""
    try:
        await event.edit(loading_text[user_language], buttons=None)
    except Exception as err:
        logging.error(f"Error showing loading state: {err}")


def _schedule_entry(shift):
    """Build a ``build_label`` entry, appending the time for non-acceptance shifts."""
    entry = build_label(shift.type, shift.volunteer.telegram)
    if shift.type != TYPE_STERIL_ACCEPTANCE:
        entry += f"{NBSP}({shift.date.strftime('%H:%M')})"
    return entry


@airtable_context("update_volunteers")
async def update_volunteers(step: str):
    """Refresh cached schedule views and the pinned topic messages."""
    state.scheduled_dates = Schedule.all(
        fields=["date", "volunteer", "telegram", "type"],
        sort=["date"],
        formula=match(
            {
                # Zero out the time so all of today's schedules are included.
                "date": (
                    ">=",
                    datetime.today().replace(
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                        tzinfo=datetime.now().astimezone().tzinfo,
                    ),
                )
            }
        ),
    )

    state.today_volunteers_list = []
    state.dates_list = []
    today = datetime.now().date().strftime("%d.%m")
    for shift in state.scheduled_dates:
        shift.date = to_local(shift.date)
        # Today's volunteers go in a separate list.
        if shift.date.date() == datetime.now().date():
            state.today_volunteers_list.append(_schedule_entry(shift))
            continue
        # Aggregate multiple volunteers scheduled on the same future date.
        same_date = [d for d in state.dates_list if d.startswith(shift.date.strftime("%d.%m"))]
        if same_date:
            state.dates_list.remove(same_date[0])
            new_entry = _schedule_entry(shift)
            state.dates_list.append(f"{shift.date.strftime('%d.%m, %A')}: {same_date[0].split(': ')[1]}, {new_entry}")
        else:
            state.dates_list.append(f"{shift.date.strftime('%d.%m, %A')}: {_schedule_entry(shift)}")

    logging.info(f"<{step}> Volunteers list and schedule updated.")

    # Update pinned messages in the group topics.
    settings_dict = load_settings()

    if not settings_dict.get("topic_chat_id"):
        logging.error(f"<{step}> Topic chat ID is not set, please set it in the settings.")
        return

    topic_chat_id = settings_dict.get("topic_chat_id")
    state.cleaning_topic_id = settings_dict.get("cleaning_topic_id")
    state.medical_topic_id = settings_dict.get("medical_topic_id")
    state.steril_cat_topic_id = settings_dict.get("steril_cat_topic_id")

    messages = [
        (settings_dict.get("last_pinned_general_message_id"), "last_pinned_general_message_id", None),
        (
            settings_dict.get("last_pinned_cleaning_message_id"),
            "last_pinned_cleaning_message_id",
            state.cleaning_topic_id,
        ),
        (settings_dict.get("last_pinned_medical_message_id"), "last_pinned_medical_message_id", state.medical_topic_id),
        (
            settings_dict.get("last_pinned_steril_message_id"),
            "last_pinned_steril_message_id",
            state.steril_cat_topic_id,
        ),
    ]

    try:
        marked_topic_chat_id = int(SUPERGROUP_ID_PREFIX + str(topic_chat_id))
        state.topic_input_entity = await resolve_topic_entity(topic_chat_id)
    except ValueError as err:
        logging.error(
            f"<{step}> Error getting topic chat entity, check if the chat ID is correct and bot is in the chat:\n"
            f"marked_topic_chat_id: {marked_topic_chat_id}\n{err}"
        )
        return

    def _general_text():
        return general_schedule["ru"].format(
            today,
            ", ".join(state.today_volunteers_list) if state.today_volunteers_list else "😿",
            "\n".join(state.dates_list),
        )

    # Create pinned messages for any topic that doesn't have one yet.
    for message_id, setting_key, topic in messages:
        if not message_id:
            logging.info(f"<{step}> Message ID is not set, creating a new message.")
            pin_message = await bot.send_message(state.topic_input_entity, _general_text(), reply_to=topic)
            await bot.pin_message(state.topic_input_entity, pin_message.id)
            setting = Settings.first(formula=match({"key": setting_key})) or Settings(key=setting_key)
            setting.value = pin_message.id
            setting.save()

    # Edit existing pinned messages (skip on startup).
    if step != "startup":
        for message_id, _setting_key, topic in messages:
            try:
                await bot.edit_message(state.topic_input_entity, message_id, _general_text())
            except errors.MessageNotModifiedError:
                logging.info(f"<{step}> Message {message_id} in topic {topic} is already up to date, skipping edit.")
            await asyncio.sleep(0.5)  # avoid flood limits

    # Re-pin messages once a day.
    if step == "daily":
        for message_id, setting_key, topic in messages:
            if topic:
                logging.info(f"<{step}> Re-pinning message {message_id} in topic {topic}")
                await bot.pin_message(state.topic_input_entity, message_id)
                setting = Settings.first(formula=match({"key": setting_key})) or Settings(key=setting_key)
                setting.value = message_id
                setting.save()

    logging.info(f"<{step}> Messages in topics updated.")
