"""Level 2: notification service (duty filtering + counts) with mocked Airtable."""

import asyncio
import types
from datetime import datetime

from app.models import Notification, Volunteer
from app.services import notification_service as svc


async def _noop_sleep(*a, **k):
    return None


def _vol(chat_id, duties, language="ru"):
    return types.SimpleNamespace(telegram_chat_id=chat_id, duties=duties, language=language)


async def test_send_notifications_filters_by_duty(monkeypatch, sent_messages):
    volunteers = [
        _vol(1, ["kk_cleaning"]),
        _vol(2, ["kk_medical"]),
        _vol(3, ["kk_cleaning", "kk_medical"]),
    ]
    curator = types.SimpleNamespace(language="ru")
    settings = types.SimpleNamespace(
        custom_text_cleaning="Убираем {}!",
        custom_text_medical="Мед {}!",
        date_threshold="+1",
    )
    monkeypatch.setattr(Volunteer, "all", lambda **kw: volunteers)
    monkeypatch.setattr(Volunteer, "first", lambda **kw: curator)
    monkeypatch.setattr(Notification, "first", lambda **kw: settings)
    monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

    total, sent = await svc.send_notifications(999, "cleaning", datetime(2024, 6, 1))

    # Only the two volunteers with the cleaning duty are notified.
    assert total == 2
    assert sent == 2
    assert len(sent_messages) == 2
    assert {m["to"] for m in sent_messages} == {1, 3}
    assert sent_messages[0]["text"].startswith("Убираем")


async def test_send_notifications_medical_only(monkeypatch, sent_messages):
    volunteers = [_vol(1, ["kk_cleaning"]), _vol(2, ["kk_medical"])]
    monkeypatch.setattr(Volunteer, "all", lambda **kw: volunteers)
    monkeypatch.setattr(Volunteer, "first", lambda **kw: types.SimpleNamespace(language="ru"))
    monkeypatch.setattr(
        Notification,
        "first",
        lambda **kw: types.SimpleNamespace(custom_text_cleaning="", custom_text_medical="", date_threshold="+1"),
    )
    monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

    total, sent = await svc.send_notifications(999, "medical", datetime(2024, 6, 1))

    assert total == 1
    assert {m["to"] for m in sent_messages} == {2}
