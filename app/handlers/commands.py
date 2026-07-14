"""Slash-command handlers: /start, /help, /settings, /schedule, topic setup, overview."""

import logging
from datetime import datetime

from pyairtable.formulas import match
from telethon import Button, events

from app import state
from app.airtable_logger import airtable_context
from app.bot_client import bot
from app.config import version
from app.constants import (
    DUTY_ADMIN_CURATOR,
    DUTY_CLEANING,
    DUTY_MEDICAL,
    DUTY_SHORT_CLEANING,
    DUTY_SHORT_MEDICAL,
    DUTY_STERIL,
    TYPE_STERIL_ACCEPTANCE,
    TYPE_STERIL_RELEASE,
)
from app.data.airtable_async import run_airtable
from app.logging_setup import logger
from app.models import Settings, Volunteer
from app.services.catflat_service import build_cat_flat_overview
from app.translations import (
    button_change_language,
    button_change_view,
    button_general_schedule,
    button_my_schedule,
    button_new_schedule,
    button_notifications,
    button_notifications_steril,
    catflat_overview_empty,
    error_not_admin,
    error_not_registered,
    general_schedule,
    help_message,
    language_selection,
    languages,
    main_menu_header,
    settings_overview,
    settings_view,
    todays_volunteers,
)


@bot.on(events.NewMessage(pattern="/start", func=lambda e: e.is_private))  # private chat only
@logger
@airtable_context("start_handler")
async def start_handler(event, check_user: bool = False, language: str = "en"):
    if not event.is_private:
        return

    # Show the language selection menu on first launch.
    if not check_user:
        buttons = [[Button.inline(languages[lang], data=f"language:{lang}")] for lang in languages]
        await event.edit(language_selection[language], buttons=buttons)
        return

    user = await run_airtable(Volunteer.first, formula=match({"telegram_chat_id": event.sender.id}))
    if not user:
        await event.edit(error_not_registered[language])
        return

    user.language = language
    await run_airtable(user.save)

    await schedule_handler(event, language, update=True)


@bot.on(events.NewMessage(pattern="/help"))
@logger
@airtable_context("help_handler")
async def help_handler(event):
    user = await run_airtable(Volunteer.first, formula=match({"telegram_chat_id": event.sender.id}))
    language = user.language if user else "en"
    version_info = f"🤖 Bot Version: `{version}`"

    if not user:
        await event.respond(f"{error_not_registered[language]}\n\n{version_info}")
        return

    await event.respond(f"{help_message[language]}\n\n{version_info}")


@bot.on(events.NewMessage(pattern="/settings", func=lambda e: e.is_private))  # private chat only
@logger
async def settings_handler(event, edit: bool = False):
    user = await run_airtable(Volunteer.first, formula=match({"telegram_chat_id": event.sender.id}))
    if not user:
        await event.respond(error_not_registered["en"])
        return

    current_settings = {"language": user.language, "view": user.schedule_view}

    buttons = [
        [Button.inline(button_change_language[current_settings["language"]], data="change_language")],
        [
            Button.inline(
                button_change_view[current_settings["language"]], data=f"change_view;{current_settings['view']}"
            )
        ],
    ]

    text = settings_overview[current_settings["language"]].format(
        languages[current_settings["language"]],
        settings_view[current_settings["view"]][current_settings["language"]],
    )
    if edit:
        await event.edit(text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons)


@bot.on(events.NewMessage(pattern="/set_cleaning_topic|/set_medical_topic|/set_steril_cat_topic"))
@logger
async def set_topic_handler(event):
    user = await run_airtable(Volunteer.first, formula=match({"telegram_chat_id": event.sender.id}))
    if not user:
        await event.respond(error_not_registered["en"])
        return

    if DUTY_ADMIN_CURATOR not in user.duties:
        await event.respond(error_not_admin[user.language])
        return

    command = event.pattern_match.group(0)
    topic_type = (
        "cleaning"
        if command == "/set_cleaning_topic"
        else "medical"
        if command == "/set_medical_topic"
        else "steril_cat"
    )

    topic_chat_setting = await run_airtable(Settings.first, formula=match({"key": "topic_chat_id"})) or Settings(
        key="topic_chat_id"
    )
    if not topic_chat_setting.value:
        topic_chat_setting.value = event.chat.id
        await run_airtable(topic_chat_setting.save)

    # Store this topic's id (the message replied to). Create the row if needed.
    topic_setting = await run_airtable(Settings.first, formula=match({"key": f"{topic_type}_topic_id"})) or Settings(
        key=f"{topic_type}_topic_id"
    )
    topic_setting.value = event.message.reply_to_msg_id
    await run_airtable(topic_setting.save)

    await bot.send_message(event.sender.id, f"{topic_type.capitalize()} topic set successfully.")


def _duties_code(user) -> str:
    """Pack the volunteer's duties into the ``new_schedule`` callback code."""
    duties_set = []
    if DUTY_CLEANING in user.duties:
        duties_set.append(DUTY_SHORT_CLEANING)
    if DUTY_MEDICAL in user.duties:
        duties_set.append(DUTY_SHORT_MEDICAL)
    if DUTY_STERIL in user.duties:
        duties_set.append(TYPE_STERIL_ACCEPTANCE)
        duties_set.append(TYPE_STERIL_RELEASE)
    return "none" if not duties_set else "+".join(duties_set)


@bot.on(events.NewMessage(pattern="/schedule"))
@logger
@airtable_context("schedule_handler")
async def schedule_handler(event, language: str = "en", update: bool = False, view: str = "today"):
    today = datetime.now().date().strftime("%d.%m")

    user = await run_airtable(Volunteer.first, formula=match({"telegram_chat_id": event.sender.id}))
    if not user:
        await event.respond(error_not_registered[language])
        return

    # In group chats just reply with the general schedule (handles topics correctly).
    if not event.is_private:
        await event.reply(
            general_schedule[language].format(
                today,
                ", ".join(state.today_volunteers_list) if state.today_volunteers_list else "😿",
                "\n".join(state.dates_list),
            )
        )
        return

    language = user.language if user else "en"
    view = user.schedule_view
    admin_flag = DUTY_ADMIN_CURATOR in user.duties

    buttons = [
        [Button.inline(button_new_schedule[language], data=f"new_schedule;{_duties_code(user)}")],
        [Button.inline(button_my_schedule[language], data="my_schedule")],
    ]
    if view == "today":
        buttons.append([Button.inline(button_general_schedule[language], data="general_schedule")])
    if admin_flag:
        buttons.append([Button.inline(button_notifications[language], data="notifications;;")])
        buttons.append([Button.inline(button_notifications_steril[language], data="notifications_steril;;")])

    todays = ", ".join(state.today_volunteers_list) if state.today_volunteers_list else "😿"
    if view == "today":
        text = main_menu_header[language] + "\n\n" + todays_volunteers[language].format(today, todays)
    else:
        text = general_schedule[language].format(today, todays, "\n".join(state.dates_list))

    if update:
        await event.edit(text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons)


@bot.on(events.NewMessage(pattern="/catflat_overview"))
@logger
@airtable_context("catflat_overview_command")
async def catflat_overview_handler(event):
    try:
        message, _state_data = await build_cat_flat_overview()
        if not message:
            message = catflat_overview_empty["ru"]
        # Reply to keep topic thread context in groups with topics.
        await event.reply(message, parse_mode="html", link_preview=False)
    except Exception as err:
        logging.error(f"Error handling /catflat_overview: {err}", exc_info=True)
