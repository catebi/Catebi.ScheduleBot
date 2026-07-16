"""Sending shift-shortage and cat acceptance/release notifications to volunteers."""

import asyncio
import logging
from datetime import datetime, timedelta

from pyairtable.formulas import match
from telethon import Button

from app import state
from app.airtable_logger import airtable_context
from app.bot_client import bot
from app.constants import (
    DUTY_CLEANING,
    DUTY_MEDICAL,
    DUTY_SHORT_CLEANING,
    DUTY_SHORT_GENERAL_CLEANING,
    DUTY_SHORT_MEDICAL,
    DUTY_SHORT_STERIL,
    DUTY_STERIL,
)
from app.data.airtable_async import run_airtable
from app.data.notification_repo import get_or_create_notification
from app.models import Volunteer
from app.text.dates import format_date_by_language
from app.translations import (
    button_curator_ignore,
    button_new_schedule,
    button_steril_accept_acceptance,
    button_steril_accept_release,
    default_cleaning_notification_text,
    default_medical_notification_text,
    notifications_steril_message,
)


def _notifiable_volunteers(volunteers, category):
    """Filter volunteers eligible for a given notification category."""
    if category == "cleaning":
        return [v for v in volunteers if DUTY_CLEANING in v.duties]
    if category == "medical":
        return [v for v in volunteers if DUTY_MEDICAL in v.duties]
    if category == "steril":
        return [v for v in volunteers if DUTY_STERIL in v.duties]
    return [v for v in volunteers if DUTY_CLEANING in v.duties or DUTY_MEDICAL in v.duties]


def _duties_code(volunteer) -> str:
    """Pack a volunteer's duties into the ``cln+med+steril`` callback code."""
    duties_set = []
    if DUTY_CLEANING in volunteer.duties:
        duties_set.append(DUTY_SHORT_CLEANING)
        duties_set.append(DUTY_SHORT_GENERAL_CLEANING)
    if DUTY_MEDICAL in volunteer.duties:
        duties_set.append(DUTY_SHORT_MEDICAL)
    if DUTY_STERIL in volunteer.duties:
        duties_set.append(DUTY_SHORT_STERIL)
    return "+".join(duties_set)


@airtable_context("send_notifications")
async def send_notifications(curator_id: int, category: str = "", target_date: datetime = None):
    """Notify eligible volunteers. Returns (total_eligible, notifications_sent)."""
    volunteers = await run_airtable(Volunteer.all, fields=["telegram_chat_id", "language", "duty_codes"])
    notifiable_volunteers = _notifiable_volunteers(volunteers, category)

    text_cleaning = text_medical = None
    if category != "steril":
        curator = await run_airtable(Volunteer.first, formula=match({"telegram_chat_id": curator_id}))
        settings = await get_or_create_notification(curator_id, volunteer=curator)
        text_cleaning = settings.custom_text_cleaning
        text_medical = settings.custom_text_medical

        if not target_date:  # default to the curator's configured threshold
            target_date = datetime.now().date() + timedelta(days=int(str(settings.date_threshold).split("+")[1]))
        if not text_cleaning:
            text_cleaning = default_cleaning_notification_text[curator.language]
        if not text_medical:
            text_medical = default_medical_notification_text[curator.language]

    all_volunteers_count = len(notifiable_volunteers)
    received_notifications_count = 0
    for volunteer in notifiable_volunteers:
        try:
            if category == "steril":
                buttons = [
                    [
                        Button.inline(
                            button_steril_accept_acceptance[volunteer.language],
                            data=f"new_steril_acceptance;{curator_id};{target_date.timestamp()}",
                        )
                    ],
                    [
                        Button.inline(
                            button_steril_accept_release[volunteer.language],
                            data=f"new_steril_release;{curator_id};{target_date.timestamp()}",
                        )
                    ],
                    [Button.inline(button_curator_ignore[volunteer.language], data="back")],
                ]
            else:
                buttons = [
                    [
                        Button.inline(
                            button_new_schedule[volunteer.language], data=f"new_schedule;{_duties_code(volunteer)}"
                        )
                    ],
                ]

            if category == "steril":
                start_date = format_date_by_language(target_date, volunteer.language)
                end_date = format_date_by_language(target_date + timedelta(days=1), volunteer.language)
                try:
                    state.steril_notification_message = await bot.send_message(
                        volunteer.telegram_chat_id,
                        notifications_steril_message[volunteer.language].format(
                            start_date,
                            end_date,
                            start_date,
                            f"{start_date} и {end_date}"
                            if volunteer.language == "ru"
                            else f"{start_date} and {end_date}",
                            end_date,
                        ),
                        buttons=buttons,
                    )
                except Exception as err:
                    logging.error(
                        f"Error sending steril notification to {volunteer.telegram_chat_id}: {err}", exc_info=True
                    )
                    continue

            elif category != "all":
                try:
                    await bot.send_message(
                        volunteer.telegram_chat_id,
                        text_cleaning.format(format_date_by_language(target_date, volunteer.language))
                        if category == "cleaning"
                        else text_medical.format(format_date_by_language(target_date, volunteer.language)),
                        buttons=buttons,
                    )
                except Exception as err:
                    logging.error(
                        f"Error sending '{category}' notification to {volunteer.telegram_chat_id}: {err}", exc_info=True
                    )
                    continue
            else:
                try:
                    await bot.send_message(
                        volunteer.telegram_chat_id,
                        text_cleaning.format(format_date_by_language(target_date, volunteer.language))
                        + "\n\n"
                        + text_medical.format(format_date_by_language(target_date, volunteer.language)),
                        buttons=buttons,
                    )
                except Exception as err:
                    logging.error(
                        f"Error sending 'all' notification to {volunteer.telegram_chat_id}: {err}", exc_info=True
                    )
                    continue

            await asyncio.sleep(0.5)  # avoid flood limits
            received_notifications_count += 1
        except Exception as err:
            logging.error(f"Error sending notification to {volunteer.telegram_chat_id}: {err}", exc_info=True)

    return all_volunteers_count, received_notifications_count
