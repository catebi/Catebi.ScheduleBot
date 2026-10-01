"""GlitchTip error tracking (Sentry-compatible).

GlitchTip speaks the Sentry protocol, so we use the official ``sentry-sdk`` and
point it at the GlitchTip DSN. Tracking is optional: with no ``GLITCHTIP_DSN``
set (e.g. local dev) the app runs normally and nothing is sent.

The SDK's logging integration is enabled by default, so every
``logging.error(...)`` — including the re-raised handler errors from
``app.logging_setup.logger`` — and every unhandled exception is reported
automatically, with no manual ``capture_exception`` calls. This pairs with the
Telegram alert topic (instant ping) and keeps history/grouping in GlitchTip.
"""

import logging

from app.config import environment, glitchtip_dsn, glitchtip_traces_sample_rate, version


def init_error_tracking():
    """Initialize GlitchTip reporting if a DSN is configured; otherwise no-op."""
    if not glitchtip_dsn:
        logging.info("GLITCHTIP_DSN not set — error tracking disabled.")
        return

    try:
        import sentry_sdk
    except ImportError:
        logging.warning("sentry-sdk is not installed — error tracking disabled.")
        return

    sentry_sdk.init(
        dsn=glitchtip_dsn,
        traces_sample_rate=glitchtip_traces_sample_rate,
        auto_session_tracking=False,  # GlitchTip does not support sessions.
        release=version,
        environment=environment,
    )
    logging.info(
        "GlitchTip error tracking initialized (environment=%s, release=%s).",
        environment,
        version,
    )
