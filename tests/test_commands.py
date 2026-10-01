"""Level 2: command handlers with mocked Telegram + Airtable."""

import types

import pytest

from app.handlers import commands
from app.models import Settings, Volunteer
from app.translations import (
    error_not_admin,
    error_not_registered,
    help_message,
    language_selection,
    main_menu_header,
    settings_overview,
    settings_view,
)


@pytest.fixture
def patch_volunteer(monkeypatch):
    """Make Volunteer.first return whatever the test sets via the returned setter."""
    holder = {}

    def set_user(user):
        holder["user"] = user
        monkeypatch.setattr(Volunteer, "first", lambda **kw: holder.get("user"))

    set_user(None)
    return set_user


async def test_schedule_handler_shows_main_menu(make_event, user_factory, patch_volunteer, button_data):
    patch_volunteer(user_factory(language="ru", duties=["kk_cleaning", "kk_medical", "kk_admin_curator"]))
    event = make_event()

    await commands.schedule_handler(event)

    assert event.last["method"] == "respond"
    assert main_menu_header["ru"] in event.last_text
    data = button_data(event.last["buttons"])
    assert "new_schedule;cln+med" in data
    assert "my_schedule" in data
    assert "general_schedule" in data  # visible in "today" view
    assert "notifications;;" in data  # admin only
    assert "notifications_steril;;" in data


async def test_schedule_handler_defaults_unset_view_to_today(make_event, user_factory, patch_volunteer, button_data):
    """A volunteer with no schedule_view set gets the documented "today" view, not a crash/general."""
    patch_volunteer(user_factory(language="ru", schedule_view=None, duties=["kk_cleaning"]))
    event = make_event()

    await commands.schedule_handler(event)

    assert main_menu_header["ru"] in event.last_text  # "today" menu, not the general view
    assert "general_schedule" in button_data(event.last["buttons"])  # button only shown in "today" view


async def test_schedule_handler_non_admin_has_no_notifications(make_event, user_factory, patch_volunteer, button_data):
    patch_volunteer(user_factory(language="ru", duties=["kk_cleaning"]))
    event = make_event()

    await commands.schedule_handler(event)

    data = button_data(event.last["buttons"])
    assert "notifications;;" not in data
    assert "new_schedule;cln" in data


async def test_start_handler_shows_language_menu(make_event, button_data):
    event = make_event()
    await commands.start_handler(event)  # check_user defaults to False

    assert event.last["method"] == "edit"
    assert event.last_text == language_selection["en"]
    assert button_data(event.last["buttons"]) == ["language:en", "language:ru"]


async def test_start_handler_unregistered(make_event, patch_volunteer):
    patch_volunteer(None)
    event = make_event()

    await commands.start_handler(event, check_user=True, language="ru")

    assert event.last_text == error_not_registered["ru"]


async def test_start_handler_registered_sets_language_and_opens_menu(make_event, user_factory, patch_volunteer):
    user = user_factory(language="en", duties=["kk_cleaning"])
    patch_volunteer(user)
    event = make_event()

    await commands.start_handler(event, check_user=True, language="ru")

    assert user.language == "ru"  # saved
    assert main_menu_header["ru"] in event.last_text  # delegated to schedule_handler


async def test_help_handler(make_event, user_factory, patch_volunteer):
    patch_volunteer(user_factory(language="ru"))
    event = make_event()

    await commands.help_handler(event)

    assert event.last["method"] == "respond"
    assert help_message["ru"] in event.last_text
    assert "Bot Version" in event.last_text


async def test_settings_handler_unregistered_does_not_crash(make_event, patch_volunteer):
    patch_volunteer(None)  # not in the volunteer table
    event = make_event()

    await commands.settings_handler(event)  # must not raise (regression: user.language on None)

    assert event.last_text == error_not_registered["en"]


async def test_settings_handler(make_event, user_factory, patch_volunteer, button_data):
    patch_volunteer(user_factory(language="ru", schedule_view="today"))
    event = make_event()

    await commands.settings_handler(event)

    assert event.last["method"] == "respond"
    assert event.last_text == settings_overview["ru"].format("🇷🇺 Русский", "Только сегодня")
    assert button_data(event.last["buttons"]) == ["change_language", "change_view;today"]


async def test_settings_handler_defaults_unset_view(make_event, user_factory, patch_volunteer):
    """A volunteer with no schedule_view set must not crash /settings (regression: KeyError: None)."""
    patch_volunteer(user_factory(language="ru", schedule_view=None))
    event = make_event()

    await commands.settings_handler(event)  # must not raise

    assert event.last["method"] == "respond"
    assert settings_view["today"]["ru"] in event.last_text  # fell back to the "today" default


async def test_set_topic_handler_rejects_non_admin(make_event, user_factory, patch_volunteer):
    patch_volunteer(user_factory(language="ru", duties=["kk_cleaning"]))
    event = make_event(pattern=types.SimpleNamespace(group=lambda i: "/set_cleaning_topic"))

    await commands.set_topic_handler(event)

    assert event.last_text == error_not_admin["ru"]


async def test_set_topic_handler_admin_saves(make_event, user_factory, patch_volunteer, monkeypatch, sent_messages):
    patch_volunteer(user_factory(language="ru", duties=["kk_admin_curator"]))
    saved = []

    class FakeSetting:
        def __init__(self):
            self.value = None

        def save(self):
            saved.append(self.value)

    monkeypatch.setattr(Settings, "first", lambda **kw: FakeSetting())
    event = make_event(
        chat_id=-1009,
        reply_to_msg_id=555,
        pattern=types.SimpleNamespace(group=lambda i: "/set_cleaning_topic"),
    )

    await commands.set_topic_handler(event)

    # topic_chat_id (chat id) and cleaning_topic_id (reply msg id) both saved.
    assert -1009 in saved
    assert 555 in saved
    assert sent_messages and "topic set successfully" in sent_messages[-1]["text"]


async def test_set_alert_topic_rejects_non_admin(make_event, user_factory, patch_volunteer):
    patch_volunteer(user_factory(language="ru", duties=["kk_cleaning"]))
    event = make_event(is_private=False)

    await commands.set_alert_topic_handler(event)

    assert event.last_text == error_not_admin["ru"]


async def test_set_alert_topic_admin_saves_and_applies(make_event, user_factory, patch_volunteer, monkeypatch):
    patch_volunteer(user_factory(language="ru", duties=["kk_admin_curator"]))
    # Baseline so monkeypatch restores state after the test (handler mutates it).
    monkeypatch.setattr(commands.state, "alert_chat_id", None)
    monkeypatch.setattr(commands.state, "alert_topic_id", None)
    created = []

    class FakeSettings:
        def __init__(self, **kwargs):
            self.key = kwargs.get("key")
            self.value = kwargs.get("value")
            created.append(self)

        def save(self):
            pass

        @classmethod
        def first(cls, **kw):
            return None  # no existing rows

    monkeypatch.setattr(commands, "Settings", FakeSettings)
    event = make_event(is_private=False, chat_id=-1009, reply_to_msg_id=777)

    await commands.set_alert_topic_handler(event)

    by_key = {s.key: s.value for s in created}
    assert by_key == {"alert_chat_id": -1009, "alert_topic_id": 777}
    # Applied to live state immediately (no restart needed).
    assert commands.state.alert_chat_id == -1009
    assert commands.state.alert_topic_id == 777
    assert "Alert topic set" in event.last_text


async def test_logger_decorator_reraises_async():
    """Regression: the @logger decorator must surface errors, not swallow them."""
    from app.logging_setup import logger

    @logger
    async def boom():
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        await boom()


def test_logger_decorator_reraises_sync():
    from app.logging_setup import logger

    @logger
    def boom():
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        boom()


async def test_set_topic_handler_creates_missing_settings_rows(
    make_event, user_factory, patch_volunteer, monkeypatch, sent_messages
):
    """When the settings rows don't exist yet, the command creates them (regression)."""
    patch_volunteer(user_factory(language="ru", duties=["kk_admin_curator"]))
    created = []

    class FakeSettings:
        def __init__(self, **kwargs):
            self.key = kwargs.get("key")
            self.value = kwargs.get("value")
            created.append(self)

        def save(self):
            pass

        @classmethod
        def first(cls, **kw):
            return None  # no existing rows

    monkeypatch.setattr(commands, "Settings", FakeSettings)
    event = make_event(
        chat_id=-1009,
        reply_to_msg_id=555,
        pattern=types.SimpleNamespace(group=lambda i: "/set_cleaning_topic"),
    )

    await commands.set_topic_handler(event)

    by_key = {s.key: s.value for s in created}
    assert by_key == {"topic_chat_id": -1009, "cleaning_topic_id": 555}
    assert sent_messages and "topic set successfully" in sent_messages[-1]["text"]
