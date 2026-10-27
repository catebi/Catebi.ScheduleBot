"""Date parsing and human-friendly, localized date formatting."""

from datetime import datetime

from babel.dates import format_date


def format_date_by_language(date: datetime, language: str) -> str:
    """Format a date as ``31.12, Monday`` localized to ``language`` (en/ru)."""
    # Generic format for all languages, e.g. "31.12, Monday".
    formatted_date = format_date(date, format="dd.MM, EEEE", locale=language)
    # Capitalize the first letter of the day of the week.
    return f"{formatted_date.split(' ')[0]} {formatted_date.split(' ')[1].capitalize()}"


def parse_airtable_date(date_value):
    """Parse a date from an Airtable field (string, datetime, or list) to a date."""
    if not date_value:
        return None

    # Lookup fields may arrive as arrays.
    if isinstance(date_value, list) and len(date_value) > 0:
        date_value = date_value[0]

    # Parse ISO date strings.
    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value.split("T")[0], "%Y-%m-%d").date()
        except Exception:
            return None

    # Already a date/datetime object.
    if hasattr(date_value, "date"):
        return date_value.date()

    return None
