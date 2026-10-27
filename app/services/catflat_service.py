"""Build the cat-flat overview message (shared by the cron job and /catflat_overview)."""

import logging
from datetime import datetime

from pyairtable.formulas import AND, GTE, LTE, OR, Field, match

from app.airtable_logger import airtable_context
from app.constants import (
    DAYS_GREEN_THRESHOLD,
    DAYS_YELLOW_THRESHOLD,
    ROOM_CAPACITIES,
    SOFTR_CAT_FLAT_DETAILS_URL,
    SOFTR_REQUEST_DETAILS_URL,
    UNKNOWN_DAYS_SORT_KEY,
)
from app.data.airtable_async import run_airtable
from app.data.catflat_repo import fetch_cat_flat_records
from app.models import Schedule
from app.text.dates import parse_airtable_date
from app.translations import (
    catflat_days_in,
    catflat_days_unknown,
    catflat_link_label,
    catflat_overview_empty,
    catflat_overview_header,
    catflat_schedule_cleaning,
    catflat_schedule_cleaning_none,
    catflat_schedule_medical,
    catflat_schedule_medical_none,
)

_LANG = "ru"


def _normalize_telegram(username) -> str:
    """Return an @-prefixed username, or @unknown when missing."""
    if not username:
        return "@unknown"
    username = str(username).strip()
    return username if username.startswith("@") else f"@{username}"


def _traffic_light(days: int) -> str:
    if days < DAYS_GREEN_THRESHOLD:
        return "🟢"
    if days < DAYS_YELLOW_THRESHOLD:
        return "🟡"
    return "🔴"


async def _todays_schedule_summary():
    """Build the '🧹 уборка / 🏥 медуход сегодня' lines appended to the overview."""
    tz = datetime.now().astimezone().tzinfo
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)
    today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz)

    schedule_formula = AND(
        GTE(Field("date"), today_start),
        LTE(Field("date"), today_end),
        OR(match({"type": "medical"}), match({"type": "cleaning"})),
    )
    today_schedules = await run_airtable(Schedule.all, formula=schedule_formula, fields=["date", "telegram", "type"])

    cleaning = []
    medical = []
    for s in today_schedules or []:
        try:
            s.date = s.date.astimezone(tz)
        except Exception:
            pass
        time_str = s.date.strftime("%H:%M") if getattr(s, "date", None) else "??:??"
        if s.type == "cleaning":
            cleaning.append((time_str, _normalize_telegram(getattr(s, "telegram", None))))
        elif s.type == "medical":
            medical.append((time_str, _normalize_telegram(getattr(s, "telegram", None))))

    cleaning.sort(key=lambda x: x[0])
    medical.sort(key=lambda x: x[0])

    lines = []
    if cleaning:
        lines.append(catflat_schedule_cleaning[_LANG].format(", ".join([f"{u} ({t})" for t, u in cleaning])))
    else:
        lines.append(catflat_schedule_cleaning_none[_LANG])
    if medical:
        lines.append(catflat_schedule_medical[_LANG].format(", ".join([f"{u} ({t})" for t, u in medical])))
    else:
        lines.append(catflat_schedule_medical_none[_LANG])
    return lines


@airtable_context("build_cat_flat_overview")
async def build_cat_flat_overview():
    """Build the overview message and a JSON-serializable state snapshot.

    Returns ``(message, state_data)`` or ``(None, None)`` when there are no cats.
    """
    normalized_cats = await fetch_cat_flat_records()
    if not normalized_cats:
        return None, None

    cats_by_room = {}  # {room: [(date_obj, days, entry), ...]}
    today = datetime.now().date()
    state_data = {"timestamp": datetime.now().isoformat(), "cats": {}}

    for cat_data in normalized_cats:
        fields_data = cat_data["fields_data"]
        is_deflead = cat_data["is_deflead"]
        is_vaccinated = cat_data["is_vaccinated"]
        is_dewormed = cat_data["is_dewormed"]
        has_med_care = bool(fields_data.get("💊 med_care", False))
        request_id = cat_data["request_id"]
        request_record_id = cat_data["request_record_id"]
        record_id = cat_data["record_id"]
        room = cat_data["room"]
        status = cat_data["status"]
        notes_kk = cat_data.get("notes_kk", "")
        requestor_name = cat_data.get("requestor_name", "")

        in_date_raw = fields_data.get("in_date")
        sterilization_date_raw = fields_data.get("sterilization_date")

        # Snapshot for the changes-notification comparison.
        state_data["cats"][record_id] = {
            "record_id": record_id,
            "status": status,
            "is_deflead": is_deflead,
            "is_vaccinated": is_vaccinated,
            "is_dewormed": is_dewormed,
            "request_id": request_id,
            "request_record_id": request_record_id,
            "room": room,
            "notes_kk": notes_kk,
            "requestor_name": requestor_name,
            "in_date": str(in_date_raw) if in_date_raw else "",
            "sterilization_date": str(sterilization_date_raw) if sterilization_date_raw else "",
        }

        # End-of-entry emojis.
        end_emojis = []
        if has_med_care:
            end_emojis.append("💊")
        if (not is_deflead) or (not is_vaccinated) or (not is_dewormed):
            end_emojis.append("💉")
        end_emoji_str = "".join(end_emojis)

        # Days in cat flat (sterilization_date first, then in_date).
        date_obj = parse_airtable_date(sterilization_date_raw) or parse_airtable_date(in_date_raw)
        if date_obj:
            days = (today - date_obj).days
            days_prefix = catflat_days_in[_LANG].format(days)
        else:
            days = UNKNOWN_DAYS_SORT_KEY  # sort unknowns to the end
            days_prefix = catflat_days_unknown[_LANG]

        status_emoji = _traffic_light(days)

        if request_record_id:
            request_id_link = f'<a href="{SOFTR_REQUEST_DETAILS_URL.format(request_record_id)}">{request_id}</a>'
        else:
            request_id_link = request_id

        if record_id:
            kk_link = f'<a href="{SOFTR_CAT_FLAT_DETAILS_URL.format(record_id)}">{catflat_link_label[_LANG]}</a>'
        else:
            kk_link = catflat_link_label[_LANG]

        requestor_part = f" ({requestor_name})" if requestor_name else ""
        entry = (
            f"{status_emoji} {request_id_link}{requestor_part}, <i>{status}</i>, "
            f"{days_prefix}{kk_link}{' ' + end_emoji_str if end_emoji_str else ''}"
        )

        notes_kk = notes_kk.strip() if notes_kk else ""
        if notes_kk:
            entry += f" ({notes_kk})"

        cats_by_room.setdefault(room, []).append((date_obj if date_obj else datetime.max.date(), days, entry))

    total_capacity = sum(ROOM_CAPACITIES.values())

    # Sort rooms ascending, entries oldest first.
    sorted_rooms = sorted(cats_by_room.keys(), reverse=False)
    all_cats = []
    total_cats_count = 0
    for i, room in enumerate(sorted_rooms):
        room_count = len(cats_by_room[room])
        total_cats_count += room_count

        room_capacity = ROOM_CAPACITIES.get(room, 0)
        if room_capacity > 0:
            room_percent = int((room_count / room_capacity) * 100)
            room_header = f"<u>{room}</u> ({room_count}/{room_capacity}, {room_percent}%🪫)"
        else:
            room_header = f"<u>{room}</u> ({room_count})"

        all_cats.append(room_header)
        for _, _, entry in sorted(cats_by_room[room], key=lambda x: (x[0], x[1])):
            all_cats.append(entry)

        if i < len(sorted_rooms) - 1:
            all_cats.append("")

    overall_percent = int((total_cats_count / total_capacity) * 100) if total_capacity > 0 else 0
    if all_cats:
        header = catflat_overview_header[_LANG].format(
            total_cats_count, total_cats_count, total_capacity, overall_percent
        )
        message = header + "\n\n" + "\n".join(all_cats)
    else:
        message = catflat_overview_empty[_LANG]

    # Append today's schedule summary (medical + cleaning).
    try:
        message = message + "\n\n" + "\n".join(await _todays_schedule_summary())
    except Exception as err:
        logging.error(f"Error building catflat schedule summary: {err}", exc_info=True)

    return message, state_data
