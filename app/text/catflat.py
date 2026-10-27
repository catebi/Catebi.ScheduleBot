"""Formatters for individual cat entries in the daily changes notification."""

from datetime import datetime

from app.constants import SOFTR_CAT_FLAT_DETAILS_URL, SOFTR_REQUEST_DETAILS_URL
from app.text.dates import parse_airtable_date
from app.translations import (
    catflat_days_in,
    catflat_days_in_full,
    catflat_days_unknown,
    catflat_days_unknown_full,
    catflat_link_label,
)

# The changes notification is posted to a shared Russian-language topic.
_LANG = "ru"


def format_cat_entry_full(cat_data_dict, full_cat_data=None):
    """Format a cat entry with request_id, requestor, status, days, and a кд link.

    ``full_cat_data`` (the live normalized record) is preferred; otherwise values
    are read from ``cat_data_dict`` (e.g. a departed cat reconstructed from JSON).
    """
    if full_cat_data:
        request_id = full_cat_data.get("request_id", cat_data_dict.get("request_id", "N/A"))
        record_id = full_cat_data.get("record_id", cat_data_dict.get("record_id"))
        requestor_name = full_cat_data.get("requestor_name", "")
        status = full_cat_data.get("status", cat_data_dict.get("status", ""))
        notes_kk = full_cat_data.get("notes_kk", "")
        fields_data = full_cat_data.get("fields_data", {})
        in_date_raw = fields_data.get("in_date") if fields_data else None
        sterilization_date_raw = fields_data.get("sterilization_date") if fields_data else None
    else:
        request_id = cat_data_dict.get("request_id", "N/A")
        record_id = cat_data_dict.get("record_id")
        requestor_name = cat_data_dict.get("requestor_name", "")
        status = cat_data_dict.get("status", "")
        notes_kk = cat_data_dict.get("notes_kk", "")
        # Dates from saved state are stored as strings.
        in_date_raw = cat_data_dict.get("in_date") or None
        sterilization_date_raw = cat_data_dict.get("sterilization_date") or None

    today = datetime.now().date()
    date_obj = parse_airtable_date(sterilization_date_raw) or parse_airtable_date(in_date_raw)
    days_text = catflat_days_in[_LANG].format((today - date_obj).days) if date_obj else catflat_days_unknown[_LANG]

    requestor_part = f" ({requestor_name})" if requestor_name else ""

    if record_id:
        kd_link = f'<a href="{SOFTR_CAT_FLAT_DETAILS_URL.format(record_id)}">{catflat_link_label[_LANG]}</a>'
    else:
        kd_link = catflat_link_label[_LANG]

    notes_part = f" ({notes_kk.strip()})" if notes_kk and notes_kk.strip() else ""

    return f"{request_id}{requestor_part}, <i>{status}</i>, {days_text}{kd_link}{notes_part}"


def format_status_change_entry(cat_data_dict):
    """Format a status-change entry (status lives in the group header, so it's omitted).

    Example: ``<a href="...">1234</a> (requestor) 10 дн в кд (notes)``.
    """
    full_cat_data = cat_data_dict.get("full_cat_data") or {}
    fields_data = full_cat_data.get("fields_data", {}) if isinstance(full_cat_data, dict) else {}

    request_id = cat_data_dict.get("request_id", "N/A")
    request_record_id = cat_data_dict.get("request_record_id")
    requestor_name = ""
    notes_kk = ""
    if isinstance(full_cat_data, dict):
        requestor_name = full_cat_data.get("requestor_name", "") or ""
        notes_kk = full_cat_data.get("notes_kk", "") or ""

    today = datetime.now().date()
    in_date_raw = fields_data.get("in_date") if fields_data else None
    sterilization_date_raw = fields_data.get("sterilization_date") if fields_data else None
    date_obj = parse_airtable_date(sterilization_date_raw) or parse_airtable_date(in_date_raw)
    if date_obj:
        days_part = catflat_days_in_full[_LANG].format((today - date_obj).days)
    else:
        days_part = catflat_days_unknown_full[_LANG]

    if request_record_id:
        request_id_part = f'<a href="{SOFTR_REQUEST_DETAILS_URL.format(request_record_id)}">{request_id}</a>'
    else:
        request_id_part = str(request_id)

    requestor_part = f" ({requestor_name})" if requestor_name else ""
    notes_kk = notes_kk.strip() if isinstance(notes_kk, str) else str(notes_kk)
    notes_part = f" ({notes_kk})" if notes_kk else ""

    return f"{request_id_part}{requestor_part} {days_part}{notes_part}"
