"""Level 2: curator notification flows with mocked Telegram + Airtable."""

import pytest

from app.flows import notifications as notif
from app.flows.protocol import CallbackContext
from app.translations import notifications_send_success


def ctx(event, data, user, language="ru"):
    return CallbackContext(event, data, user, language, "01.06")


class FakeNotification:
    def __init__(self, **kwargs):
        self.custom_text_cleaning = kwargs.get("custom_text_cleaning", "")
        self.custom_text_medical = kwargs.get("custom_text_medical", "")
        self.notify_at = kwargs.get("notify_at", "12:00")
        self.date_threshold = kwargs.get("date_threshold", "+1")
        self.saved = False

    def save(self):
        self.saved = True


@pytest.fixture
def patch_notification(monkeypatch):
    """Make get_or_create_notification (async) return a provided FakeNotification."""

    def _install(notification):
        async def _get(*a, **k):
            return notification

        monkeypatch.setattr(notif, "get_or_create_notification", _get)
        return notification

    return _install


async def test_open_menu_renders_settings_menu(make_event, user_factory, patch_notification, button_data):
    patch_notification(FakeNotification())
    event = make_event()

    await notif.open_menu(ctx(event, "notifications;;", user_factory()))

    data = button_data(event.last["buttons"])
    assert "notifications_settings_text_menu" in data
    assert "notifications_settings_notify_at" in data
    assert "notifications_settings_date_threshold" in data
    assert "notifications_send_menu" in data
    assert "back" in data


async def test_set_notify_at_saves(make_event, user_factory, patch_notification):
    admin = patch_notification(FakeNotification(notify_at="12:00"))
    event = make_event()

    await notif.set_notify_at(ctx(event, "notifications_settings_notify_at;09:00", user_factory()))

    assert admin.notify_at == "09:00"
    assert admin.saved is True
    assert "09:00" in event.last_text


async def test_set_date_threshold_saves(make_event, user_factory, patch_notification):
    admin = patch_notification(FakeNotification(date_threshold="+1"))
    event = make_event()

    await notif.set_date_threshold(ctx(event, "notifications_settings_date_threshold;+3", user_factory()))

    assert admin.date_threshold == "+3"
    assert admin.saved is True


async def test_send_now_reports_counts(make_event, user_factory, monkeypatch):
    async def fake_send(curator_id, category, target_date):
        return 10, 7  # (total_eligible, sent)

    monkeypatch.setattr(notif, "send_notifications", fake_send)
    event = make_event()

    await notif.send_now(ctx(event, "notifications_send;cleaning;", user_factory()))

    assert event.last_text == notifications_send_success["ru"].format(7, 10)
