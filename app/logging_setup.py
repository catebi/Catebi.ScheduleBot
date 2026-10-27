import inspect
import logging
import os
from functools import wraps
from logging.handlers import RotatingFileHandler

# Logs live in ``logs/`` so they land in the volume mounted by docker-compose
# (``./logs:/app/logs``) and survive container recreation.
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "airtable.log")

# Rotate at 10 MB and keep 3 backups (~40 MB cap) so the file never fills the disk.
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 3


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(
                LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )


def logger(func):
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logging.error("Unhandled error in %s", func.__name__, exc_info=True)
            raise

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            logging.error("Unhandled error in %s", func.__name__, exc_info=True)
            raise

    return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
