"""Level 2: the hourly curator notification cron, focused on the blocked-bot path."""

import logging
import types
from datetime import datetime

from telethon.errors import UserIsBlockedError

from app.jobs import scheduling
from app.models import Notification, Schedule, Volunteer


def _curator(chat_id, telegram):
    return types.SimpleNamespace(
        telegram=telegram,
        telegram_chat_id=chat_id,
        duties=["kk_admin_curator"],
        language="ru",
    )


def _settings(chat_id):
    # notify_at == now so the job acts on this run; +0 threshold keeps it to today only.
    return types.SimpleNamespace(
        telegram_chat_id=chat_id,
        notify_at=datetime.now().strftime("%H:%M"),
        date_threshold="+0",
    )


async def _run_job():
    # ``send_curator_notifications`` is an aiocron ``Cron`` object; ``.func`` is the
    # decorated coroutine (logger -> airtable_context -> the real body).
    return await scheduling.send_curator_notifications.func()


async def test_blocked_curator_is_logged_and_others_still_notified(monkeypatch, caplog):
    blocked = _curator(1, "@blocked")
    reachable = _curator(2, "@reachable")

    monkeypatch.setattr(Volunteer, "all", lambda **kw: [blocked, reachable])
    monkeypatch.setattr(Notification, "all", lambda **kw: [_settings(1), _settings(2)])
    # No schedules on any date -> the "no volunteers at all" branch fires and a message is sent.
    monkeypatch.setattr(Schedule, "all", lambda **kw: [])

    sent = []

    async def _send(recipient, text=None, **kw):
        if recipient == 1:
            raise UserIsBlockedError(request=None)
        sent.append(recipient)
        return types.SimpleNamespace(id=1, message=text)

    monkeypatch.setattr(scheduling.bot, "send_message", _send)

    with caplog.at_level(logging.WARNING):
        await _run_job()

    # The reachable curator still got their notification despite the blocked one failing first.
    assert sent == [2]
    # The block was logged as a warning, not swallowed silently or raised.
    assert any(
        rec.levelno == logging.WARNING and "unreachable" in rec.getMessage() and "@blocked" in rec.getMessage()
        for rec in caplog.records
    )


async def test_unexpected_send_error_is_logged_and_reraised(monkeypatch, caplog):
    """A non-block error must surface via @logger (proving the decorator now wraps the coroutine)."""
    monkeypatch.setattr(Volunteer, "all", lambda **kw: [_curator(1, "@boom")])
    monkeypatch.setattr(Notification, "all", lambda **kw: [_settings(1)])
    monkeypatch.setattr(Schedule, "all", lambda **kw: [])

    async def _send(recipient, text=None, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(scheduling.bot, "send_message", _send)

    raised = False
    with caplog.at_level(logging.ERROR):
        try:
            await _run_job()
        except RuntimeError:
            raised = True

    assert raised
    assert any(
        rec.levelno == logging.ERROR and "Unhandled error in send_curator_notifications" in rec.getMessage()
        for rec in caplog.records
    )
