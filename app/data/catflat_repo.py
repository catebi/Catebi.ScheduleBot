import logging

from pyairtable.formulas import AND, OR, match

from app.airtable_logger import airtable_context
from app.bot_client import sterilization_api
from app.config import airtable_sterilization_base_id
from app.constants import (
    CAT_FLAT_STATUSES,
    CAT_FLAT_TABLE,
    DEPARTED_FETCH_CHUNK_SIZE,
    NO_ROOM,
)
from app.data.coerce import coerce_lookup, coerce_text

# Fields fetched for the overview / changes comparison (full set).
FIELDS_OVERVIEW = [
    "request_id",
    "sterilization_date",
    "in_date",
    "record_id",
    "request_record_id",
    "notes_kk",
    "requestor_name",
    "status",
    "room",
    "💊 med_care",
    "🦟is_deflead",
    "💉is_vaccinated",
    "𓆑is_dewormed",
    "required_vaccination",
]

# Fields fetched for the daily medical notification (no notes/requestor).
FIELDS_MEDICAL = [
    "request_id",
    "sterilization_date",
    "in_date",
    "record_id",
    "request_record_id",
    "status",
    "room",
    "💊 med_care",
    "🦟is_deflead",
    "💉is_vaccinated",
    "𓆑is_dewormed",
    "required_vaccination",
]


def is_configured() -> bool:
    return bool(airtable_sterilization_base_id and sterilization_api)


def cat_flat_table():
    return sterilization_api.table(airtable_sterilization_base_id, CAT_FLAT_TABLE)


def active_cats_formula():
    status_formula = OR(*[match({"status": status}) for status in CAT_FLAT_STATUSES])
    return AND(status_formula, match({"is_test": False}))


@airtable_context("fetch_cat_flat_records")
async def fetch_cat_flat_records():
    if not is_configured():
        logging.error("Sterilization base ID or API not configured.")
        return []

    try:
        records = cat_flat_table().all(
            formula=str(active_cats_formula()),
            fields=FIELDS_OVERVIEW,
        )

        normalized_cats = []
        for record in records:
            fields_data = record.get("fields", {})

            normalized_cats.append(
                {
                    "record_id": coerce_lookup(fields_data.get("record_id"), record.get("id")),
                    "status": fields_data.get("status", ""),
                    "is_deflead": fields_data.get("🦟is_deflead", False),
                    "is_vaccinated": fields_data.get("💉is_vaccinated", False),
                    "is_dewormed": fields_data.get("𓆑is_dewormed", False),
                    "request_id": coerce_lookup(fields_data.get("request_id"), "N/A"),
                    "request_record_id": coerce_lookup(fields_data.get("request_record_id"), None),
                    "room": coerce_text(fields_data.get("room", ""), NO_ROOM),
                    "notes_kk": coerce_text(fields_data.get("notes_kk", ""), ""),
                    "requestor_name": coerce_text(fields_data.get("requestor_name", ""), ""),
                    "record": record,  # Keep full record for formatting
                    "fields_data": fields_data,  # Keep fields_data for formatting
                }
            )

        return normalized_cats
    except Exception as err:
        logging.error(f"Error fetching cat flat records: {err}", exc_info=True)
        return []


def fetch_departed_status_notes(departed_ids):
    result = {}
    if not (departed_ids and is_configured()):
        return result

    table = cat_flat_table()
    for i in range(0, len(departed_ids), DEPARTED_FETCH_CHUNK_SIZE):
        chunk = departed_ids[i : i + DEPARTED_FETCH_CHUNK_SIZE]
        formula_str = "OR(" + ",".join([f"RECORD_ID()='{rid}'" for rid in chunk]) + ")"
        records = table.all(formula=formula_str, fields=["status", "notes_kk"])
        for rec in records:
            rid = rec.get("id")
            if not rid:
                continue
            fields = rec.get("fields", {})
            result[rid] = {
                "status": fields.get("status", ""),
                "notes_kk": coerce_text(fields.get("notes_kk", ""), ""),
            }
    return result
