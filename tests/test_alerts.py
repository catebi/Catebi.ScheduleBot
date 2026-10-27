"""Which log records the Telegram alert handler mirrors to the topic."""

import logging

from app.alerts import TelegramAlertHandler


def _record(name, level, msg="x"):
    return logging.LogRecord(name=name, level=level, pathname=__file__, lineno=1, msg=msg, args=(), exc_info=None)


def test_mirrors_app_warnings_and_errors():
    assert TelegramAlertHandler._should_mirror(_record("app.flows.schedule", logging.WARNING))
    assert TelegramAlertHandler._should_mirror(_record("app.flows.schedule", logging.ERROR))


def test_skips_telethon_records():
    # Skipped at every level to avoid an error -> send -> error feedback loop.
    assert not TelegramAlertHandler._should_mirror(_record("telethon.client.users", logging.ERROR))


def test_skips_transient_urllib3_warnings_but_keeps_errors():
    assert not TelegramAlertHandler._should_mirror(_record("urllib3.connectionpool", logging.WARNING))
    assert not TelegramAlertHandler._should_mirror(_record("requests.adapters", logging.WARNING))
    # A genuine ERROR from the same library still gets through.
    assert TelegramAlertHandler._should_mirror(_record("urllib3.connectionpool", logging.ERROR))
