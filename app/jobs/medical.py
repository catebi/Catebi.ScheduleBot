"""Cron job: the daily medical topic notification (cats needing treatment)."""

import logging
from datetime import datetime

import aiocron
from pyairtable.formulas import AND, GTE, LTE, Field, match

from app import state
from app.airtable_logger import airtable_context
from app.bot_client import bot
from app.constants import (
    NO_ROOM,
    SOFTR_CAT_FLAT_DETAILS_URL,
    SOFTR_REQUEST_DETAILS_URL,
    UNKNOWN_DAYS_SORT_KEY,
)
from app.data.airtable_async import run_airtable
from app.data.catflat_repo import (
    FIELDS_MEDICAL,
    active_cats_formula,
    cat_flat_table,
    is_configured,
)
from app.data.coerce import coerce_lookup, coerce_text, to_local
from app.data.settings_repo import load_settings, resolve_topic_entity
from app.logging_setup import logger
from app.models import Schedule
from app.text.dates import parse_airtable_date
from app.translations import (
    catflat_days_in_full,
    catflat_days_unknown_full,
    medical_all_clear,
    medical_attention_header,
    medical_duty_none,
    medical_duty_today,
)

# The medical notification is posted to a shared Russian-language topic.
_LANG = "ru"

# Visible label for the cat-flat detail link in this notification (a fixed tag).
_LINK_LABEL = "kk_link"


def _cat_attention_entry(record, today):
    """Format one 'needs attention' cat entry; returns (request_id_num, room, entry)."""
    fields_data = record.get("fields", {})
    is_deflead = fields_data.get("🦟is_deflead", False)
    is_vaccinated = fields_data.get("💉is_vaccinated", False)
    is_dewormed = fields_data.get("𓆑is_dewormed", False)
    has_med_care = bool(fields_data.get("💊 med_care", False))

    request_id = coerce_lookup(fields_data.get("request_id"), "N/A")
    try:
        request_id_num = int(request_id) if request_id != "N/A" else UNKNOWN_DAYS_SORT_KEY
    except Exception:
        request_id_num = UNKNOWN_DAYS_SORT_KEY

    request_record_id = coerce_lookup(fields_data.get("request_record_id"), None)
    record_id = coerce_lookup(fields_data.get("record_id"), record.get("id"))
    room = coerce_text(fields_data.get("room", ""), NO_ROOM)

    emojis = []
    if has_med_care:
        emojis.append("💊")
    if not is_deflead:
        emojis.append("🦟")
    if not is_vaccinated:
        required_vaccination = fields_data.get("required_vaccination", "")
        emojis.append("💉(" + required_vaccination + ")" if required_vaccination else "💉")
    if not is_dewormed:
        emojis.append("𓆑")
    emoji_str = "".join(emojis)

    date_obj = parse_airtable_date(fields_data.get("sterilization_date")) or parse_airtable_date(
        fields_data.get("in_date")
    )
    days_text = (
        catflat_days_in_full[_LANG].format((today - date_obj).days) if date_obj else catflat_days_unknown_full[_LANG]
    )

    if request_record_id:
        request_id_link = f'<a href="{SOFTR_REQUEST_DETAILS_URL.format(request_record_id)}">{request_id}</a>'
    else:
        request_id_link = request_id

    if record_id:
        details_link = f'<a href="{SOFTR_CAT_FLAT_DETAILS_URL.format(record_id)}">{_LINK_LABEL}</a>'
    else:
        details_link = _LINK_LABEL

    entry = f"{request_id_link} {emoji_str} {days_text}, {details_link}"
    return request_id_num, room, entry


async def _todays_medical_duty():
    """Return the 'дежурный медухода' line for today."""
    today_start = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.now().astimezone().tzinfo
    )
    today_end = datetime.now().replace(
        hour=23, minute=59, second=59, microsecond=999999, tzinfo=datetime.now().astimezone().tzinfo
    )
    formula = AND(GTE(Field("date"), today_start), LTE(Field("date"), today_end), match({"type": "medical"}))
    today_schedules = await run_airtable(Schedule.all, formula=formula, fields=["date", "telegram", "type"])

    if today_schedules:
        schedule = today_schedules[0]
        schedule_date = to_local(schedule.date)
        username = schedule.telegram if schedule.telegram else "unknown"
        return medical_duty_today[_LANG].format(username, schedule_date.strftime("%H:%M"))
    return medical_duty_none[_LANG]


@logger
@aiocron.crontab("00 11 * * *")  # every day at 11:00
@airtable_context("daily_medical_notification")
async def send_daily_medical_notification():
    settings_dict = await load_settings()
    if not settings_dict.get("topic_chat_id") or not settings_dict.get("medical_topic_id"):
        logging.error("Topic chat ID or medical topic ID is not set, skipping daily medical notification.")
        return

    state.medical_topic_id = settings_dict.get("medical_topic_id")

    try:
        state.topic_input_entity = await resolve_topic_entity(settings_dict.get("topic_chat_id"))
    except (ValueError, Exception) as err:
        logging.error(f"Error getting topic chat entity for daily medical notification: {err}")
        return

    if not is_configured():
        logging.error("Sterilization base ID or API not configured, skipping daily medical notification.")
        return

    try:
        records = await run_airtable(cat_flat_table().all, formula=str(active_cats_formula()), fields=FIELDS_MEDICAL)

        # Group cats needing attention by room: {room: [(request_id_num, entry), ...]}.
        cats_by_room = {}
        today = datetime.now().date()
        for record in records:
            fields_data = record.get("fields", {})
            is_deflead = fields_data.get("🦟is_deflead", False)
            is_vaccinated = fields_data.get("💉is_vaccinated", False)
            is_dewormed = fields_data.get("𓆑is_dewormed", False)
            has_med_care = bool(fields_data.get("💊 med_care", False))

            if not is_deflead or not is_vaccinated or not is_dewormed or has_med_care:
                request_id_num, room, entry = _cat_attention_entry(record, today)
                cats_by_room.setdefault(room, []).append((request_id_num, entry))

        # Sort rooms desc, entries within a room by request_id desc.
        cats_needing_attention = []
        sorted_rooms = sorted(cats_by_room.keys(), reverse=True)
        for i, room in enumerate(sorted_rooms):
            cats_needing_attention.append(f"<u>{room}</u>")
            for _, entry in sorted(cats_by_room[room], key=lambda x: x[0], reverse=True):
                cats_needing_attention.append(entry)
            if i < len(sorted_rooms) - 1:
                cats_needing_attention.append("")

        duty_info = await _todays_medical_duty()

        if cats_needing_attention:
            message = medical_attention_header[_LANG] + "\n\n" + "\n".join(cats_needing_attention) + f"\n\n{duty_info}"
        else:
            message = medical_all_clear[_LANG]

        await bot.send_message(
            state.topic_input_entity,
            message,
            reply_to=state.medical_topic_id,
            parse_mode="html",
            link_preview=False,
        )
        logging.info(
            f"Daily medical notification sent successfully. Cats needing attention: {len(cats_needing_attention)}"
        )
    except Exception as err:
        logging.error(f"Error sending daily medical notification: {err}", exc_info=True)
