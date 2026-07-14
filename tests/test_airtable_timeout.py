from unittest import mock

from requests.adapters import HTTPAdapter

from app.data.airtable_timeout import (
    TimeoutHTTPAdapter,
    apply_timeout,
    install_airtable_timeout,
)


def test_adapter_injects_default_timeout(monkeypatch):
    captured = {}

    def fake_send(self, request, **kwargs):
        captured.update(kwargs)
        return "resp"

    monkeypatch.setattr(HTTPAdapter, "send", fake_send)
    adapter = TimeoutHTTPAdapter(timeout=(10, 30))

    adapter.send("req")

    assert captured["timeout"] == (10, 30)


def test_adapter_keeps_explicit_timeout(monkeypatch):
    captured = {}

    def fake_send(self, request, **kwargs):
        captured.update(kwargs)
        return "resp"

    monkeypatch.setattr(HTTPAdapter, "send", fake_send)
    adapter = TimeoutHTTPAdapter(timeout=(10, 30))

    adapter.send("req", timeout=5)

    assert captured["timeout"] == 5


def test_apply_timeout_mounts_adapter_and_preserves_retries():
    from pyairtable import Api

    api = Api("dummy", timeout=(1, 1))
    original_retries = api.session.get_adapter("https://").max_retries

    apply_timeout(api, (7, 8))

    for scheme in ("https://", "http://"):
        adapter = api.session.get_adapter(scheme)
        assert isinstance(adapter, TimeoutHTTPAdapter)
        assert adapter._timeout == (7, 8)
        # Retry strategy pyairtable configured must survive the remount.
        assert adapter.max_retries == original_retries


def test_apply_timeout_ignores_none():
    # No sterilization Api (missing key) must not raise.
    apply_timeout(None, (7, 8))


def _timeout_seen_at_transport(api):
    """Drive a real ``Api.request`` and capture the timeout that reaches urllib3."""
    captured = {}

    def base_send(self, request, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        raise RuntimeError("stop")  # short-circuit before real network I/O

    # Patch the *base* adapter so TimeoutHTTPAdapter.send still runs its injection.
    with mock.patch.object(HTTPAdapter, "send", base_send):
        try:
            api.request("GET", "https://api.airtable.com/v0/appX/tblX")
        except RuntimeError:
            pass
    return captured.get("timeout")


def test_stock_pyairtable_drops_timeout_regression():
    from pyairtable import Api

    # Documents the upstream bug this module works around: without the adapter,
    # the configured timeout never reaches the transport layer.
    api = Api("dummy", timeout=(10, 30))
    assert _timeout_seen_at_transport(api) is None


def test_workaround_delivers_timeout_to_transport():
    from pyairtable import Api

    api = Api("dummy", timeout=(10, 30))
    apply_timeout(api, (10, 30))
    assert _timeout_seen_at_transport(api) == (10, 30)


def test_install_patches_all_apis():
    from app.bot_client import sterilization_api
    from app.models import Notification, Schedule, Settings, Volunteer

    install_airtable_timeout((3, 4))

    apis = [m.meta.api for m in (Volunteer, Schedule, Notification, Settings)]
    if sterilization_api is not None:
        apis.append(sterilization_api)

    for api in apis:
        adapter = api.session.get_adapter("https://")
        assert isinstance(adapter, TimeoutHTTPAdapter)
        assert adapter._timeout == (3, 4)
