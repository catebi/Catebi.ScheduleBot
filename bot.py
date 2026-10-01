from app.logging_setup import setup_logging
from app.monitoring import init_error_tracking

# Configure logging and error tracking as early as possible — before importing
# the rest of the app — so even import-time failures are logged and reported.
setup_logging()
init_error_tracking()

from app.main import run  # noqa: E402

if __name__ == "__main__":
    run()
