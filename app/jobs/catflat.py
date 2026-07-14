"""Cron jobs: the daily cat-flat status snapshot and the day-over-day changes report."""

import json
import logging

import aiocron

from app import state
from app.airtable_logger import airtable_context
from app.bot_client import bot
from app.constants import CAT_FLAT_STATE_FILE
from app.data.catflat_repo import fetch_cat_flat_records, fetch_departed_status_notes
from app.data.settings_repo import load_settings, resolve_topic_entity
from app.logging_setup import logger
from app.services.catflat_service import build_cat_flat_overview
from app.text.catflat import format_cat_entry_full, format_status_change_entry
from app.translations import (
    changes_bad_prev_state,
    changes_departed,
    changes_header,
    changes_medical,
    changes_new,
    changes_no_prev_state,
    changes_none,
    changes_status,
)

_LANG = "ru"


@logger
@aiocron.crontab("00 10 * * *")  # every day at 10:00
@airtable_context("daily_cat_flat_status_notification")
async def send_daily_cat_flat_status_notification():
    settings_dict = await load_settings()
    if not settings_dict.get("process_notification_topic_id"):
        logging.error("Process notification topic ID is not set, skipping daily cat flat status notification.")
        return
    process_notification_topic_id = settings_dict.get("process_notification_topic_id")

    try:
        state.topic_input_entity = await resolve_topic_entity(settings_dict.get("topic_chat_id"))
    except (ValueError, Exception) as err:
        logging.error(f"Error getting topic chat entity for daily cat flat status notification: {err}")
        return

    try:
        message, state_data = await build_cat_flat_overview()
        if not message:
            logging.warning("No cat records found for status notification.")
            return

        await bot.send_message(
            state.topic_input_entity,
            message,
            reply_to=process_notification_topic_id,
            parse_mode="html",
            link_preview=False,
        )

        # Save state to JSON for the changes notification to compare against.
        try:
            with open(CAT_FLAT_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            logging.info(
                f"Cat flat state saved to {CAT_FLAT_STATE_FILE}. "
                f"Total cats: {len(state_data['cats']) if state_data else 0}"
            )
        except Exception as save_err:
            logging.error(f"Error saving cat flat state to JSON: {save_err}", exc_info=True)

        logging.info("Daily cat flat status notification sent successfully.")
    except Exception as err:
        logging.error(f"Error sending daily cat flat status notification: {err}", exc_info=True)


def _load_previous_state():
    """Read the previous snapshot; returns (prev_cats, error_message_or_None)."""
    try:
        with open(CAT_FLAT_STATE_FILE, encoding="utf-8") as f:
            prev_state = json.load(f)
        prev_cats = prev_state.get("cats", {})
        logging.info(
            f"Loaded previous state from {prev_state.get('timestamp', 'unknown')}. Total cats: {len(prev_cats)}"
        )
        return prev_cats, None
    except FileNotFoundError:
        logging.warning(f"Previous state file not found at {CAT_FLAT_STATE_FILE}. This may be the first run.")
        return None, changes_no_prev_state[_LANG]
    except json.JSONDecodeError as json_err:
        logging.error(f"Error parsing previous state JSON: {json_err}")
        return None, changes_bad_prev_state[_LANG]


async def _diff_cats(prev_cats, current_cats):
    """Categorize changes between snapshots.

    Returns (new_cats, departed_cats, status_changes, medical_changes).
    """
    new_cats = [cat for rid, cat in current_cats.items() if rid not in prev_cats]

    # For departed cats, fetch their current status/notes from Airtable.
    departed_ids = [rid for rid in prev_cats.keys() if rid not in current_cats]
    try:
        departed_current_map = await fetch_departed_status_notes(departed_ids)
    except Exception as fetch_err:
        logging.warning(f"Could not batch fetch departed cats status/notes: {fetch_err}")
        departed_current_map = {}

    departed_cats = []
    status_changes = {}  # {(prev_status, new_status): [cat, ...]}
    medical_changes = []
    for record_id, prev_cat in prev_cats.items():
        if record_id not in current_cats:
            cur = departed_current_map.get(record_id)
            if cur:
                prev_cat["status"] = cur.get("status", prev_cat.get("status", ""))
                prev_cat["notes_kk"] = cur.get("notes_kk", prev_cat.get("notes_kk", ""))
            departed_cats.append(prev_cat)
            continue

        curr_cat = current_cats[record_id]
        if prev_cat["status"] != curr_cat["status"]:
            status_changes.setdefault((prev_cat["status"], curr_cat["status"]), []).append(curr_cat)

        changed = []
        if prev_cat["is_deflead"] != curr_cat["is_deflead"]:
            changed.append("🦟☑️")
        if prev_cat["is_vaccinated"] != curr_cat["is_vaccinated"]:
            changed.append("💉☑️")
        if prev_cat["is_dewormed"] != curr_cat["is_dewormed"]:
            changed.append("𓆑☑️")
        if changed:
            medical_changes.append({"cat": curr_cat, "changes": changed})

    return new_cats, departed_cats, status_changes, medical_changes


def _build_changes_message(new_cats, departed_cats, status_changes, medical_changes):
    message_parts = []

    if new_cats:
        message_parts.append(changes_new[_LANG])
        for cat in new_cats:
            message_parts.append(format_cat_entry_full(cat, cat.get("full_cat_data")))
        message_parts.append("")

    if departed_cats:
        message_parts.append(changes_departed[_LANG])
        for prev_cat in departed_cats:
            message_parts.append(format_cat_entry_full(prev_cat))
        message_parts.append("")

    if status_changes:
        message_parts.append(changes_status[_LANG])
        message_parts.append("")
        for (prev_status, new_status), cats in status_changes.items():
            message_parts.append(f"<u>{prev_status} -> {new_status}</u>")
            for cat in cats:
                message_parts.append(format_status_change_entry(cat))
            message_parts.append("")
        message_parts.append("")

    if medical_changes:
        message_parts.append(changes_medical[_LANG])
        for med_change in medical_changes:
            cat = med_change["cat"]
            entry = format_cat_entry_full(cat, cat.get("full_cat_data"))
            message_parts.append(f"{''.join(med_change['changes'])} {entry}")
        message_parts.append("")

    if message_parts:
        return changes_header[_LANG] + "\n\n" + "\n".join(message_parts).strip()
    return changes_none[_LANG]


@logger
@aiocron.crontab("00 22 * * *")  # every day at 22:00 (10 PM)
@airtable_context("daily_cat_flat_changes_notification")
async def send_daily_cat_flat_changes_notification():
    settings_dict = await load_settings()
    if not settings_dict.get("process_notification_topic_id"):
        logging.error("Process notification topic ID is not set, skipping daily cat flat changes notification.")
        return
    process_notification_topic_id = settings_dict.get("process_notification_topic_id")

    try:
        state.topic_input_entity = await resolve_topic_entity(settings_dict.get("topic_chat_id"))
    except (ValueError, Exception) as err:
        logging.error(f"Error getting topic chat entity for daily cat flat changes notification: {err}")
        return

    try:
        prev_cats, error_message = _load_previous_state()
        if error_message:
            await bot.send_message(
                state.topic_input_entity,
                error_message,
                reply_to=process_notification_topic_id,
                parse_mode="html",
                link_preview=False,
            )
            return

        current_normalized_cats = await fetch_cat_flat_records()
        if not current_normalized_cats:
            logging.warning("No current cat records found for changes notification.")
            return

        current_cats = {
            cat_data["record_id"]: {
                "record_id": cat_data["record_id"],
                "status": cat_data["status"],
                "is_deflead": cat_data["is_deflead"],
                "is_vaccinated": cat_data["is_vaccinated"],
                "is_dewormed": cat_data["is_dewormed"],
                "request_id": cat_data["request_id"],
                "request_record_id": cat_data["request_record_id"],
                "room": cat_data["room"],
                "full_cat_data": cat_data,
            }
            for cat_data in current_normalized_cats
        }

        new_cats, departed_cats, status_changes, medical_changes = await _diff_cats(prev_cats, current_cats)
        message = _build_changes_message(new_cats, departed_cats, status_changes, medical_changes)

        await bot.send_message(
            state.topic_input_entity,
            message,
            reply_to=process_notification_topic_id,
            parse_mode="html",
            link_preview=False,
        )
        logging.info(
            f"Daily cat flat changes notification sent successfully. New: {len(new_cats)}, "
            f"Departed: {len(departed_cats)}, Status changes: {len(status_changes)}, "
            f"Medical changes: {len(medical_changes)}"
        )
    except Exception as err:
        logging.error(f"Error sending daily cat flat changes notification: {err}", exc_info=True)
