"""Level 1/2: get_or_create_notification creates the row when it's missing."""

from app.data import notification_repo as repo


async def test_returns_existing_when_present(monkeypatch):
    existing = object()

    class FakeNotification:
        @classmethod
        def first(cls, **kw):
            return existing

    monkeypatch.setattr(repo, "Notification", FakeNotification)
    assert await repo.get_or_create_notification(1) is existing


async def test_creates_with_defaults_when_missing(monkeypatch):
    created = {}

    class FakeNotification:
        def __init__(self, **kwargs):
            created["kwargs"] = kwargs

        def save(self):
            created["saved"] = True

        @classmethod
        def first(cls, **kw):
            return None

    monkeypatch.setattr(repo, "Notification", FakeNotification)

    result = await repo.get_or_create_notification(42, admin_curator="bob")

    assert isinstance(result, FakeNotification)
    assert created["kwargs"]["telegram_chat_id"] == 42
    assert created["kwargs"]["admin_curator"] == "bob"
    assert created["kwargs"]["notify_at"] == "12:00"
    assert created["kwargs"]["date_threshold"] == "+1"
    assert created["saved"] is True
