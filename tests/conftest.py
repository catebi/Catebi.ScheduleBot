import os
import tempfile

os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "dummyhash")
os.environ.setdefault("BOT_TOKEN", "12345:dummy")
os.environ.setdefault("AIRTABLE_API_KEY", "dummykey")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTEST")
os.environ.setdefault("AIRTABLE_STERILIZATION_BASE_ID", "appSTERIL")

_TEST_SESSION = os.path.join(tempfile.gettempdir(), "catebi_test_session")
os.environ.setdefault("SESSION_NAME", _TEST_SESSION)

import glob  # noqa: E402
import types  # noqa: E402

import pytest  # noqa: E402


class FakeSender:
    def __init__(self, sender_id=100, username="tester"):
        self.id = sender_id
        self.username = username


class FakeEvent:
    """Records what a handler would send. Mirrors the Telethon event surface used by handlers."""

    def __init__(
        self,
        data="",
        sender_id=100,
        username="tester",
        is_private=True,
        message="",
        reply_to_msg_id=None,
        chat_id=-1001,
        pattern=None,
    ):
        self.data = data.encode("utf-8") if isinstance(data, str) else data
        self.sender = FakeSender(sender_id, username)
        self.sender_id = sender_id
        self.is_private = is_private
        self.chat = types.SimpleNamespace(id=chat_id)
        self.message = types.SimpleNamespace(message=message, reply_to_msg_id=reply_to_msg_id)
        self.pattern_match = pattern
        self.sent = []  # recorded {method, text, buttons}

    async def _record(self, method, text, buttons):
        self.sent.append({"method": method, "text": text, "buttons": buttons})
        return types.SimpleNamespace(id=999, message=text, buttons=buttons, entities=None)

    async def answer(self, message=None, **kw):
        return await self._record("answer", message, None)

    async def edit(self, text, buttons=None, **kw):
        return await self._record("edit", text, buttons)

    async def respond(self, text, buttons=None, **kw):
        return await self._record("respond", text, buttons)

    async def reply(self, text, buttons=None, **kw):
        return await self._record("reply", text, buttons)

    @property
    def last(self):
        return self.sent[-1] if self.sent else None

    @property
    def last_text(self):
        return self.last["text"] if self.last else None


@pytest.fixture
def make_event():
    """Factory for FakeEvent."""
    return FakeEvent


def make_user(language="ru", duties=None, schedule_view="today", telegram="@tester", chat_id=100):
    return types.SimpleNamespace(
        language=language,
        duties=duties or [],
        schedule_view=schedule_view,
        telegram=telegram,
        telegram_chat_id=chat_id,
        save=lambda: None,
    )


@pytest.fixture
def user_factory():
    return make_user


@pytest.fixture
def sent_messages(monkeypatch):
    """Capture ``bot.send_message`` calls; returns the list of recorded calls."""
    from app.bot_client import bot

    calls = []

    async def _send(recipient, text=None, **kw):
        calls.append({"to": recipient, "text": text, **kw})
        return types.SimpleNamespace(id=1, message=text)

    monkeypatch.setattr(bot, "send_message", _send)
    return calls


def _button_data(buttons):
    """Flatten a Telethon buttons matrix to the list of callback-data strings."""
    result = []
    for row in buttons or []:
        row = row if isinstance(row, list) else [row]
        for b in row:
            data = getattr(b, "data", None)
            if isinstance(data, bytes):
                data = data.decode()
            result.append(data)
    return result


def _button_labels(buttons):
    """Flatten a Telethon buttons matrix to the list of button labels."""
    result = []
    for row in buttons or []:
        row = row if isinstance(row, list) else [row]
        for b in row:
            result.append(getattr(b, "text", None))
    return result


@pytest.fixture
def button_data():
    return _button_data


@pytest.fixture
def button_labels():
    return _button_labels


def pytest_sessionfinish(session, exitstatus):
    # Remove the isolated Telethon session file created when bot_client was imported.
    for f in glob.glob(_TEST_SESSION + ".session*"):
        try:
            os.remove(f)
        except OSError:
            pass
