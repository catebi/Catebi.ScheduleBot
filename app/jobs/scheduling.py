"""Cron jobs for the schedule: midnight refresh and hourly curator notifications."""

import logging
from datetime import datetime, timedelta

import aiocron
from pyairtable.formulas import AND, GTE, LTE, OR, Field, match
from telethon import Button

from app.airtable_logger import airtable_context
from app.bot_client import bot
from app.constants import DUTY_ADMIN_CURATOR, TYPE_CLEANING, TYPE_GENERAL_CLEANING
from app.data.airtable_async import run_airtable
from app.logging_setup import logger
from app.models import Notification, Schedule, Volunteer
from app.services.schedule_service import update_volunteers
from app.text.dates import format_date_by_language
from app.translations import (
    button_curator_ignore,
    button_curator_notifications_send_all,
    button_curator_notifications_send_cleaning,
    button_curator_notifications_send_medical,
    notifications_no_cleaning_volunteers,
    notifications_no_general_cleaning_volunteers,
    notifications_no_medical_volunteers,
    notifications_no_volunteers_at_all,
)


def expected_cleaning_type(date) -> str:
    """The cleaning shift type a date is supposed to have: regular on weekdays, general on weekends."""
    return TYPE_GENERAL_CLEANING if date.weekday() >= 5 else TYPE_CLEANING


@logger
@aiocron.crontab("0 0 * * *")  # every day at midnight
async def daily_schedule_update():
    """Refresh cached lists and re-pin topic messages at midnight."""
    await update_volunteers("daily")


@logger
@aiocron.crontab("0 * * * *")  # every hour at minute 0
@airtable_context("send_curator_notifications")
async def send_curator_notifications():
    """Notify each curator, at their configured time, of the nearest empty date."""
    volunteers = await run_airtable(Volunteer.all, fields=["telegram", "telegram_chat_id", "duty_codes", "language"])
    curators = [v for v in volunteers if DUTY_ADMIN_CURATOR in v.duties]
    if not curators:
        return

    # Fetch all curator notification settings in one query.
    curator_matches = [match({"telegram_chat_id": c.telegram_chat_id}) for c in curators]
    all_curator_settings = await run_airtable(Notification.all, formula=OR(*curator_matches)) if curator_matches else []
    curator_settings_map = {s.telegram_chat_id: s for s in all_curator_settings}

    for curator in curators:
        try:
            curator_settings = curator_settings_map[curator.telegram_chat_id]
        except KeyError:
            logging.warning(
                f"No notification settings found for curator {curator.telegram} ({curator.telegram_chat_id}), skipping."
            )
            continue

        # Only act at the curator's configured notify time.
        if datetime.now().strftime("%H:%M") != curator_settings.notify_at:
            continue

        start_date = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.now().astimezone().tzinfo
        )
        end_date = start_date + timedelta(days=int(str(curator_settings.date_threshold).split("+")[1]))
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        for date in (start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)):
            logging.info(f"Checking for volunteers for {date} for {curator.telegram}")
            formula = AND(
                GTE(Field("date"), date.replace(hour=0, minute=0, second=0, microsecond=0)),
                LTE(Field("date"), date.replace(hour=23, minute=59, second=59, microsecond=999999)),
            )
            schedules = await run_airtable(Schedule.all, formula=formula, fields=["type"])

            buttons = []
            text = ""
            if not schedules:
                logging.info(f"No volunteers found for {date} for {curator.telegram}, sending notification.")
                buttons.append(
                    [
                        Button.inline(
                            button_curator_notifications_send_all[curator.language],
                            data=f"notifications_send;all;{date.timestamp()}",
                        )
                    ]
                )
                text = notifications_no_volunteers_at_all[curator.language].format(
                    format_date_by_language(date, curator.language)
                )
            else:
                schedule_types = [s.type for s in schedules]
                # Weekdays expect a regular cleaning shift, weekends a general cleaning one.
                cleaning_type = expected_cleaning_type(date)
                if cleaning_type not in schedule_types:
                    logging.info(
                        f"No {cleaning_type} volunteers found for {date} for {curator.telegram}, sending notification."
                    )
                    buttons.append(
                        [
                            Button.inline(
                                button_curator_notifications_send_cleaning[curator.language],
                                data=f"notifications_send;cleaning;{date.timestamp()}",
                            )
                        ]
                    )
                    no_volunteers_text = (
                        notifications_no_general_cleaning_volunteers
                        if cleaning_type == TYPE_GENERAL_CLEANING
                        else notifications_no_cleaning_volunteers
                    )
                    text = no_volunteers_text[curator.language].format(format_date_by_language(date, curator.language))
                elif "medical" not in schedule_types:
                    logging.info(
                        f"No medical volunteers found for {date} for {curator.telegram}, sending notification."
                    )
                    buttons.append(
                        [
                            Button.inline(
                                button_curator_notifications_send_medical[curator.language],
                                data=f"notifications_send;medical;{date.timestamp()}",
                            )
                        ]
                    )
                    text = notifications_no_medical_volunteers[curator.language].format(
                        format_date_by_language(date, curator.language)
                    )

            if text:
                buttons.append([Button.inline(button_curator_ignore[curator.language], data="back")])
                await bot.send_message(curator.telegram_chat_id, text, buttons=buttons)
                break  # Only notify about the closest empty date.
