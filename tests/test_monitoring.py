"""GlitchTip init is optional and must never break startup."""

from app import monitoring


def test_init_error_tracking_disabled_without_dsn(monkeypatch):
    """With no DSN, init is a no-op and doesn't require sentry-sdk installed."""
    monkeypatch.setattr(monitoring, "glitchtip_dsn", None)

    monitoring.init_error_tracking()  # must not raise


def test_init_error_tracking_calls_sdk_when_dsn_set(monkeypatch):
    """With a DSN, the SDK is initialized with the configured options."""
    monkeypatch.setattr(monitoring, "glitchtip_dsn", "https://token@example.com/1")
    monkeypatch.setattr(monitoring, "environment", "testing")
    monkeypatch.setattr(monitoring, "version", "1.2.3")
    monkeypatch.setattr(monitoring, "glitchtip_traces_sample_rate", 0.5)

    captured = {}

    class FakeSdk:
        def init(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(__import__("sys").modules, "sentry_sdk", FakeSdk())

    monitoring.init_error_tracking()

    assert captured["dsn"] == "https://token@example.com/1"
    assert captured["environment"] == "testing"
    assert captured["release"] == "1.2.3"
    assert captured["traces_sample_rate"] == 0.5
    assert captured["auto_session_tracking"] is False
