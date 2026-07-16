"""Level 1: label / button-text helpers."""

from app.constants import (
    TYPE_CLEANING,
    TYPE_CLEANING_CATLOFT,
    TYPE_GENERAL_CLEANING,
    TYPE_MEDICAL,
    TYPE_STERIL_ACCEPTANCE,
    TYPE_STERIL_RELEASE,
)
from app.text.labels import build_label, label_for_type, slot_indicator
from app.translations import (
    button_type_cleaning,
    button_type_cleaning_location,
    button_type_general_cleaning,
    button_type_medical,
    button_type_steril_acceptance,
    button_type_steril_release,
)


def test_build_label_contains_username_and_emoji():
    label = build_label(TYPE_CLEANING, "@alice")
    assert "@alice" in label
    assert "🧹" in label and "🏠" in label


def test_build_label_general_cleaning():
    label = build_label(TYPE_GENERAL_CLEANING, "@alice")
    assert "@alice" in label
    assert "🧼" in label and "🏠" in label


def test_build_label_medical_and_steril():
    assert "🏥" in build_label(TYPE_MEDICAL, "@bob")
    assert "⬆️" in build_label(TYPE_STERIL_RELEASE, "@bob")
    # steril_acceptance / default is the down arrow.
    assert "⬇️" in build_label(TYPE_STERIL_ACCEPTANCE, "@bob")


def test_label_for_type_all_types_ru():
    assert label_for_type(TYPE_CLEANING, "ru") == button_type_cleaning["ru"]
    assert label_for_type(TYPE_CLEANING_CATLOFT, "ru") == button_type_cleaning_location["ru"]["catloft"]
    assert label_for_type(TYPE_GENERAL_CLEANING, "ru") == button_type_general_cleaning["ru"]
    assert label_for_type(TYPE_MEDICAL, "ru") == button_type_medical["ru"]
    assert label_for_type(TYPE_STERIL_RELEASE, "ru") == button_type_steril_release["ru"]
    assert label_for_type(TYPE_STERIL_ACCEPTANCE, "ru") == button_type_steril_acceptance["ru"]


def test_label_for_type_default_is_acceptance():
    # Unknown type falls back to the acceptance label (matches original behavior).
    assert label_for_type("something_else", "ru") == button_type_steril_acceptance["ru"]


def test_slot_indicator():
    assert slot_indicator(0) == "🆓"
    assert slot_indicator(1) == "1️⃣"
    assert slot_indicator(2) == "2️⃣"
