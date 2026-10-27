# Enforce a request timeout on pyairtable, which otherwise ignores it.

import logging

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import AIRTABLE_TIMEOUT
from app.models import Notification, Schedule, Settings, Volunteer

AIRTABLE_RETRY = Retry(
    total=2,
    connect=2,
    read=1,
    status=2,
    backoff_factor=0.3,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"}),
    raise_on_status=False,
)


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

    adapter = TimeoutHTTPAdapter(max_retries=AIRTABLE_RETRY, timeout=timeout)
    session.mount("https://", adapter)
    session.mount("http://", adapter)


def install_airtable_timeout(timeout=AIRTABLE_TIMEOUT):
    from app.bot_client import sterilization_api

    apply_timeout(sterilization_api, timeout)
    for model_class in (Volunteer, Schedule, Notification, Settings):
        apply_timeout(model_class.meta.api, timeout)
    logging.info("Airtable request timeout enforced: %s", timeout)
