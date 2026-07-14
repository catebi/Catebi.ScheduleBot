"""Level 1: verify the callback dispatcher routes each data string to exactly the
right flow handler(s), preserving the original control flow (esp. the load-bearing
returns for ``language`` and ``notifications_steril;;``)."""

import types

import pytest

import app.flows.dispatch as dispatch
from app.flows import notifications, settings
from app.flows import schedule as schedule_flow

# data string -> the ordered list of handler names it must invoke.
CASES = {
    "language:ru": ["start_handler"],
    "new_schedule;cln+med": ["schedule.new_schedule"],
    "set_schedule_time;2024-01-06;cleaning": ["schedule.set_schedule_time"],
    "set_schedule_time;2024-01-06;steril_acceptance": [],  # guard excludes it
    "add_schedule;2024-01-06;10:00;cleaning": ["schedule.add_schedule"],
    "my_schedule": ["schedule.my_schedule"],
    "my_schedule_delete;2024-01-06 10:00;cleaning": ["schedule.my_schedule_delete"],
    "delete_schedule;2024-01-06 10:00:00;cleaning": ["schedule.delete_schedule"],
    "general_schedule": ["schedule.general_schedule_view"],
    "notifications;;": ["notifications.open_menu"],
    "notifications;unset;": ["notifications.open_menu"],
    "notifications;reset;cleaning": ["notifications.open_menu"],
    "notifications_settings_text_menu": ["notifications.open_text_menu"],
    "notifications_settings_text;cleaning": ["notifications.choose_text_type"],
    "notifications_settings_notify_at": ["notifications.open_notify_at_menu"],
    "notifications_settings_notify_at;10:00": ["notifications.set_notify_at"],
    "notifications_settings_date_threshold": ["notifications.open_date_threshold_menu"],
    "notifications_settings_date_threshold;+1": ["notifications.set_date_threshold"],
    "notifications_send_menu": ["notifications.open_send_menu"],
    "notifications_send;cleaning;": ["notifications.send_now"],
    # Load-bearing: ";;" routes ONLY to the menu (the return stops choose_steril_dates).
    "notifications_steril;;": ["notifications.open_steril_menu"],
    "notifications_steril_own_dates;;": ["notifications.open_steril_own_dates"],
    "notifications_steril;2024-01-06": ["notifications.choose_steril_dates"],
    "notifications_steril_confirm;2024-01-06": ["notifications.confirm_steril"],
    "new_steril_acceptance;123;1700000000.0": ["notifications.new_steril"],
    "change_language": ["settings.change_language"],
    "change_view;today": ["settings.change_view"],
    "change_view_to;general": ["settings.change_view_to"],
    "back_steril": ["settings.back_steril"],
    "back_settings": ["settings.back_settings"],
    "back": ["settings.back"],
}

FLOW_FUNCS = {
    schedule_flow: [
        "new_schedule",
        "set_schedule_time",
        "add_schedule",
        "my_schedule",
        "my_schedule_delete",
        "delete_schedule",
        "general_schedule_view",
    ],
    notifications: [
        "open_menu",
        "open_text_menu",
        "choose_text_type",
        "open_notify_at_menu",
        "set_notify_at",
        "open_date_threshold_menu",
        "set_date_threshold",
        "open_send_menu",
        "send_now",
        "open_steril_menu",
        "open_steril_own_dates",
        "choose_steril_dates",
        "confirm_steril",
        "new_steril",
    ],
    settings: [
        "change_language",
        "change_view",
        "change_view_to",
        "back_steril",
        "back_settings",
        "back",
    ],
}


@pytest.fixture
def routing(monkeypatch):
    calls = []

    def recorder(name):
        async def _rec(*args, **kwargs):
            calls.append(name)

        return _rec

    for mod, names in FLOW_FUNCS.items():
        short = mod.__name__.split(".")[-1]
        for n in names:
            monkeypatch.setattr(mod, n, recorder(f"{short}.{n}"))

    monkeypatch.setattr(dispatch, "start_handler", recorder("start_handler"))
    fake_user = types.SimpleNamespace(language="ru")
    monkeypatch.setattr(dispatch, "Volunteer", types.SimpleNamespace(first=lambda **kw: fake_user))
    return calls


@pytest.mark.parametrize("data,expected", list(CASES.items()))
async def test_routing(routing, make_event, data, expected):
    await dispatch.callback_handler(make_event(data=data))
    assert routing == expected, f"{data!r} routed to {routing}, expected {expected}"


async def test_unregistered_user_callback_is_ignored(routing, make_event, monkeypatch):
    """A callback from a user not in the volunteer table is ignored, not crashed on."""
    monkeypatch.setattr(dispatch, "Volunteer", types.SimpleNamespace(first=lambda **kw: None))

    await dispatch.callback_handler(make_event(data="back"))  # must not raise

    assert routing == []  # no flow handler invoked


async def test_callback_is_answered_immediately(routing, make_event):
    """The query is answered (before the flow runs) so a slow lookup can't expire it."""
    event = make_event(data="back")
    await dispatch.callback_handler(event)
    # First recorded action is the answer, ahead of any flow's edit/respond.
    assert event.sent and event.sent[0]["method"] == "answer"


async def test_unregistered_user_callback_is_still_answered(routing, make_event, monkeypatch):
    """Even a stale button from a non-volunteer gets its spinner stopped."""
    monkeypatch.setattr(dispatch, "Volunteer", types.SimpleNamespace(first=lambda **kw: None))

    event = make_event(data="back")
    await dispatch.callback_handler(event)

    assert any(s["method"] == "answer" for s in event.sent)
