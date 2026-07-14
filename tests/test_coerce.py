"""Level 1: Airtable value coercion helpers."""

from datetime import UTC, datetime

from app.data.coerce import coerce_lookup, coerce_text, to_local


def test_coerce_lookup_list_takes_first():
    assert coerce_lookup(["a", "b"]) == "a"


def test_coerce_lookup_scalar_stringified():
    assert coerce_lookup(42) == "42"


def test_coerce_lookup_none_returns_default():
    assert coerce_lookup(None, "N/A") == "N/A"
    assert coerce_lookup(None) is None


def test_coerce_lookup_zero_is_kept():
    # 0 is not None, so it must be kept (this is the difference from coerce_text).
    assert coerce_lookup(0, "N/A") == "0"


def test_coerce_lookup_empty_list_stringifies_to_bracket():
    # Preserves the original edge-case behavior: empty list -> "[]".
    assert coerce_lookup([], "N/A") == "[]"


def test_coerce_text_list_takes_first():
    assert coerce_text(["room1"], "default") == "room1"


def test_coerce_text_falsy_returns_default():
    assert coerce_text("", "default") == "default"
    assert coerce_text([], "default") == "default"
    assert coerce_text(None, "default") == "default"


def test_coerce_text_truthy_stringified():
    assert coerce_text("hello") == "hello"


def test_to_local_returns_aware_datetime():
    utc_dt = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    local = to_local(utc_dt)
    # Same instant, just re-expressed in the local zone.
    assert local == utc_dt
    assert local.tzinfo is not None
