"""Level 1: date parsing and localized formatting."""

from datetime import date, datetime

from app.text.dates import format_date_by_language, parse_airtable_date


def test_parse_iso_string():
    assert parse_airtable_date("2024-03-15") == date(2024, 3, 15)


def test_parse_iso_datetime_string():
    assert parse_airtable_date("2024-03-15T10:30:00.000Z") == date(2024, 3, 15)


def test_parse_list_takes_first():
    assert parse_airtable_date(["2024-03-15"]) == date(2024, 3, 15)


def test_parse_datetime_object():
    assert parse_airtable_date(datetime(2024, 3, 15, 9, 0)) == date(2024, 3, 15)


def test_parse_none_and_empty():
    assert parse_airtable_date(None) is None
    assert parse_airtable_date("") is None
    assert parse_airtable_date([]) is None


def test_parse_garbage_string():
    assert parse_airtable_date("not-a-date") is None


def test_format_date_ru():
    # 2024-12-31 is a Tuesday; format is "dd.MM, <Weekday capitalized>".
    result = format_date_by_language(date(2024, 12, 31), "ru")
    assert result.startswith("31.12,")
    # Day name is capitalized (Вторник).
    assert result.split(", ")[1][0].isupper()


def test_format_date_en():
    result = format_date_by_language(date(2024, 12, 31), "en")
    assert result == "31.12, Tuesday"
