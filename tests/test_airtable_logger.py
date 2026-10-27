"""Level 1: the Airtable request-logging wrapper must never mask the real error."""

import pytest

from app.airtable_logger import log_airtable_request


def test_reraises_keyboardinterrupt_without_unbound_error():
    """Regression: KeyboardInterrupt (a BaseException) must propagate cleanly,
    not be replaced by an UnboundLocalError from the finally block."""

    @log_airtable_request
    def boom():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        boom()


def test_reraises_regular_exception():
    @log_airtable_request
    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        boom()


def test_returns_result_on_success():
    @log_airtable_request
    def ok():
        return 42

    assert ok() == 42
