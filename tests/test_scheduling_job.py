"""Level 1: curator-notification helpers from the scheduling cron job."""

from datetime import datetime

from app.constants import TYPE_CLEANING, TYPE_GENERAL_CLEANING
from app.jobs.scheduling import expected_cleaning_type


def test_expected_cleaning_type_weekdays():
    # 2024-06-03 is a Monday.
    for day in range(3, 8):  # Mon..Fri
        assert expected_cleaning_type(datetime(2024, 6, day)) == TYPE_CLEANING


def test_expected_cleaning_type_weekends():
    assert expected_cleaning_type(datetime(2024, 6, 8)) == TYPE_GENERAL_CLEANING  # Saturday
    assert expected_cleaning_type(datetime(2024, 6, 9)) == TYPE_GENERAL_CLEANING  # Sunday
