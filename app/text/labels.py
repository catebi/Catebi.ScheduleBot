"""Inline-button and schedule-entry label helpers."""

from app.constants import (
    TYPE_CLEANING,
    TYPE_CLEANING_CATLOFT,
    TYPE_GENERAL_CLEANING,
    TYPE_MEDICAL,
    TYPE_STERIL_RELEASE,
)
from app.translations import (
    button_type_cleaning,
    button_type_cleaning_location,
    button_type_general_cleaning,
    button_type_medical,
    button_type_steril_acceptance,
    button_type_steril_release,
)

# Word joiner (U+2060) + non-breaking space (U+00A0) keep emoji + username on one line.
WORD_JOINER = "⁠"
NBSP = " "


def build_label(date_type: str, username: str) -> str:
    """Build a non-wrapping ``emoji + username`` label for a schedule entry."""
    if date_type == TYPE_CLEANING:
        return "🧹" + WORD_JOINER + "🏠" + WORD_JOINER + username
    if date_type == TYPE_CLEANING_CATLOFT:
        return "🧹" + WORD_JOINER + "🪜" + WORD_JOINER + username
    if date_type == TYPE_GENERAL_CLEANING:
        return "🧼" + WORD_JOINER + "🏠" + WORD_JOINER + username
    if date_type == TYPE_MEDICAL:
        return "🏥" + WORD_JOINER + username
    if date_type == TYPE_STERIL_RELEASE:
        return "😸" + WORD_JOINER + "⬆️" + WORD_JOINER + username
    # steril_acceptance and any other type default to the down arrow.
    return "😸" + WORD_JOINER + "⬇️" + WORD_JOINER + username


def label_for_type(shift_type: str, language: str) -> str:
    """Human-readable button label for a shift type, localized to ``language``."""
    if shift_type == TYPE_CLEANING:
        return button_type_cleaning[language]
    if shift_type == TYPE_CLEANING_CATLOFT:
        return button_type_cleaning_location[language]["catloft"]
    if shift_type == TYPE_GENERAL_CLEANING:
        return button_type_general_cleaning[language]
    if shift_type == TYPE_MEDICAL:
        return button_type_medical[language]
    if shift_type == TYPE_STERIL_RELEASE:
        return button_type_steril_release[language]
    # steril_acceptance and any other type.
    return button_type_steril_acceptance[language]


def slot_indicator(slot_count: int) -> str:
    """Emoji showing how many cleaning slots on a date are taken (0/1/2)."""
    return "1️⃣" if slot_count == 1 else "2️⃣" if slot_count == 2 else "🆓"
