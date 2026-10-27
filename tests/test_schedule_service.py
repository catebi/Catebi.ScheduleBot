"""Level 2: update_volunteers with mocked Telegram + Airtable."""

import types

from app.bot_client import bot
from app.services import schedule_service as svc


class FakeSchedule:
    @classmethod
    def all(cls, **kw):
        return []


class FakeSettings:
    created = []

    def __init__(self, **kwargs):
        self.key = kwargs.get("key")
        self.value = kwargs.get("value")
        FakeSettings.created.append(self)

    def save(self):
        pass

    @classmethod
    def first(cls, **kw):
        return None  # no settings rows exist yet


async def test_update_volunteers_creates_missing_pin_settings(monkeypatch):
    """Regression: when last_pinned_* rows don't exist, they are created, not crashed on."""
    FakeSettings.created = []
    monkeypatch.setattr(svc, "Schedule", FakeSchedule)
    monkeypatch.setattr(svc, "Settings", FakeSettings)

    async def _load_settings():
        return {"topic_chat_id": 123}

    monkeypatch.setattr(svc, "load_settings", _load_settings)

    async def _resolve(_chat_id):
        return "ENTITY"

    monkeypatch.setattr(svc, "resolve_topic_entity", _resolve)

    async def _send(*a, **k):
        return types.SimpleNamespace(id=777)

    async def _pin(*a, **k):
        return None

    monkeypatch.setattr(bot, "send_message", _send)
    monkeypatch.setattr(bot, "pin_message", _pin)

    # Must not raise (previously crashed on Settings.first(...) being None).
    await svc.update_volunteers("startup")

    created_keys = {s.key for s in FakeSettings.created}
    assert created_keys == {
        "last_pinned_general_message_id",
        "last_pinned_cleaning_message_id",
        "last_pinned_medical_message_id",
        "last_pinned_steril_message_id",
    }
    assert all(s.value == 777 for s in FakeSettings.created)
