"""Level 2: scheduling callback flows with mocked Telegram + Airtable."""

from datetime import UTC, datetime

import pytest

from app import state
from app.flows import schedule as sched
from app.flows.protocol import CallbackContext
from app.translations import add_schedule_success, add_schedule_success_steril_acceptance, error_no_duties


def ctx(event, data, user, language="ru"):
    return CallbackContext(event, data, user, language, "01.06")


class FakeSchedule:
    """Stand-in for the ORM model: records constructions/saves; configurable .all/.first."""

    saved = []
    all_result = []
    first_result = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def save(self):
        FakeSchedule.saved.append(self.kwargs)

    @classmethod
    def all(cls, **kw):
        return cls.all_result

    @classmethod
    def first(cls, **kw):
        return cls.first_result


@pytest.fixture
def fake_schedule(monkeypatch):
    FakeSchedule.saved = []
    FakeSchedule.all_result = []
    FakeSchedule.first_result = None
    monkeypatch.setattr(sched, "Schedule", FakeSchedule)
    return FakeSchedule


@pytest.fixture
def quiet_side_effects(monkeypatch):
    """No-op the loading state + volunteer refresh so flow tests stay in-process."""

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(sched, "show_loading_state", _noop)
    monkeypatch.setattr(sched, "update_volunteers", _noop)


@pytest.fixture
def topics(monkeypatch):
    """Give the flows resolved topic ids so topic posting is exercised."""
    monkeypatch.setattr(state, "topic_input_entity", "ENTITY")
    monkeypatch.setattr(state, "cleaning_topic_id", 11)
    monkeypatch.setattr(state, "medical_topic_id", 22)
    monkeypatch.setattr(state, "steril_cat_topic_id", 33)


async def test_new_schedule_no_duties(make_event, user_factory, button_data):
    event = make_event()
    await sched.new_schedule(ctx(event, "new_schedule;none", user_factory()))
    assert event.last_text == error_no_duties["ru"]
    assert button_data(event.last["buttons"]) == ["back"]


async def test_new_schedule_multiple_duties_offers_types(make_event, user_factory, button_data):
    event = make_event()
    await sched.new_schedule(ctx(event, "new_schedule;cln+gcln+med", user_factory()))
    data = button_data(event.last["buttons"])
    assert "new_schedule;cleaning" in data
    assert "new_schedule;general_cleaning" in data
    assert "new_schedule;medical" in data


async def test_new_schedule_cleaning_asks_location(make_event, user_factory, button_data):
    event = make_event()
    await sched.new_schedule(ctx(event, "new_schedule;cleaning", user_factory()))
    assert "new_schedule;cleaning;loc" in button_data(event.last["buttons"])


async def test_new_schedule_general_cleaning_asks_location(make_event, user_factory, button_data):
    event = make_event()
    await sched.new_schedule(ctx(event, "new_schedule;general_cleaning", user_factory()))
    assert "new_schedule;general_cleaning;loc" in button_data(event.last["buttons"])


def _date_buttons(data):
    return [d for d in data if d and d.startswith("set_schedule_time;")]


async def test_new_schedule_lists_weekdays_for_cleaning(make_event, user_factory, button_data, fake_schedule):
    fake_schedule.all_result = []  # nothing booked
    event = make_event()
    await sched.new_schedule(ctx(event, "new_schedule;cleaning;loc", user_factory()))
    data = button_data(event.last["buttons"])
    assert data[-1] == "back"
    date_buttons = _date_buttons(data)
    # 14-day window = 2 full weeks -> exactly 10 weekdays.
    assert len(date_buttons) == 10
    for d in date_buttons:
        assert datetime.strptime(d.split(";")[1], "%Y-%m-%d").weekday() < 5


async def test_new_schedule_lists_weekends_for_general_cleaning(make_event, user_factory, button_data, fake_schedule):
    fake_schedule.all_result = []  # nothing booked
    event = make_event()
    await sched.new_schedule(ctx(event, "new_schedule;general_cleaning;loc", user_factory()))
    data = button_data(event.last["buttons"])
    date_buttons = _date_buttons(data)
    # 14-day window = 2 full weeks -> exactly 4 weekend days.
    assert len(date_buttons) == 4
    for d in date_buttons:
        assert datetime.strptime(d.split(";")[1], "%Y-%m-%d").weekday() >= 5


async def test_add_schedule_cleaning_saves_and_posts(
    make_event, user_factory, fake_schedule, quiet_side_effects, topics, sent_messages
):
    user = user_factory(language="ru", telegram="@alice")
    event = make_event(username="alice")
    await sched.add_schedule(ctx(event, "add_schedule;2024-06-01;10:00;cleaning", user))

    assert len(fake_schedule.saved) == 1
    assert fake_schedule.saved[0]["type"] == "cleaning"
    # user got a success message...
    assert event.last["method"] == "edit"
    assert add_schedule_success["ru"].split("{")[0] in event.last_text
    # ...and the cleaning topic got a post.
    assert sent_messages and sent_messages[-1]["reply_to"] == 11


async def test_add_schedule_general_cleaning_saves_and_posts_to_cleaning_topic(
    make_event, user_factory, fake_schedule, quiet_side_effects, topics, sent_messages
):
    user = user_factory(language="ru", telegram="@alice")
    event = make_event(username="alice")
    await sched.add_schedule(ctx(event, "add_schedule;2024-06-01;10:00;general_cleaning", user))

    assert len(fake_schedule.saved) == 1
    assert fake_schedule.saved[0]["type"] == "general_cleaning"
    assert add_schedule_success["ru"].split("{")[0] in event.last_text
    # general cleaning announcements go to the same cleaning topic.
    assert sent_messages and sent_messages[-1]["reply_to"] == 11


async def test_add_schedule_steril_acceptance_path(
    make_event, user_factory, fake_schedule, quiet_side_effects, topics, sent_messages
):
    user = user_factory(language="ru", telegram="@bob")
    event = make_event(username="bob")
    await sched.add_schedule(ctx(event, "add_schedule;2024-06-01;;steril_acceptance", user))

    assert len(fake_schedule.saved) == 1
    assert fake_schedule.saved[0]["type"] == "steril_acceptance"
    assert add_schedule_success_steril_acceptance["ru"].split("{")[0] in event.last_text
    # posted to the steril topic.
    assert sent_messages and sent_messages[-1]["reply_to"] == 33


async def test_my_schedule_lists_shifts(make_event, user_factory, fake_schedule, quiet_side_effects, button_data):
    shift = type("S", (), {"date": datetime(2024, 6, 1, 10, 0, tzinfo=UTC), "type": "cleaning"})()
    fake_schedule.all_result = [shift]
    event = make_event()
    await sched.my_schedule(ctx(event, "my_schedule", user_factory()))
    data = button_data(event.last["buttons"])
    assert any(d and d.startswith("my_schedule_delete;") for d in data)
    assert data[-1] == "back"


async def test_delete_schedule_deletes_and_posts(
    make_event, user_factory, fake_schedule, quiet_side_effects, topics, sent_messages
):
    deleted = []
    fake_schedule.first_result = type("S", (), {"delete": lambda self: deleted.append(True)})()
    user = user_factory(language="ru", telegram="@alice")
    event = make_event(username="alice")

    await sched.delete_schedule(ctx(event, "delete_schedule;2024-06-01 10:00:00;cleaning", user))

    assert deleted == [True]
    assert event.last["method"] == "edit"
    assert sent_messages and sent_messages[-1]["reply_to"] == 11
