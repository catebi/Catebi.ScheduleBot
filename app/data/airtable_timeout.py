"""Enforce a request timeout on pyairtable, which otherwise ignores it.

pyairtable (through 3.4.0 and the current ``main`` branch) accepts ``timeout=``
on ``Api``/ORM ``Meta`` and stores it as ``Api.timeout``, but never passes it to
the underlying ``requests`` call — ``Api.request()`` calls ``session.request(...)``
without ``timeout=``. As a result ``AIRTABLE_TIMEOUT`` has no effect and a stalled
connection can hang the bot indefinitely.

We fix it at the transport layer: mount an ``HTTPAdapter`` on each Api's session
that injects the timeout into every request that doesn't already set one. The
adapter keeps the retry strategy pyairtable configured, so retries still work.
"""

import logging

from requests.adapters import HTTPAdapter

from app.config import AIRTABLE_TIMEOUT
from app.models import Notification, Schedule, Settings, Volunteer


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, timeout=None, **kwargs):
        self._timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self._timeout
        return super().send(request, **kwargs)


def apply_timeout(api, timeout=AIRTABLE_TIMEOUT):
    if api is None:
        return
    session = api.session

    max_retries = getattr(session.get_adapter("https://"), "max_retries", 0)
    adapter = TimeoutHTTPAdapter(max_retries=max_retries, timeout=timeout)
    session.mount("https://", adapter)
    session.mount("http://", adapter)


def install_airtable_timeout(timeout=AIRTABLE_TIMEOUT):
    from app.bot_client import sterilization_api

    apply_timeout(sterilization_api, timeout)
    for model_class in (Volunteer, Schedule, Notification, Settings):
        apply_timeout(model_class.meta.api, timeout)
    logging.info("Airtable request timeout enforced: %s", timeout)
