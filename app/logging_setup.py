import logging
import os


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("airtable.log"),
            logging.StreamHandler(),
        ],
    )


def logger(func):
    def decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            logging.error(err, exc_info=True)

    return decorator
