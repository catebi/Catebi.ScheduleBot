import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load a local .env file if present. For local development only;
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

# Telegram API credentials
api_id = os.getenv("API_ID", None)
api_hash = os.getenv("API_HASH", None)
bot_token = os.getenv("BOT_TOKEN", None)

# Airtable API credentials
airtable_api_key = os.getenv("AIRTABLE_API_KEY", None)
airtable_base_id = os.getenv("AIRTABLE_BASE_ID", None)
airtable_sterilization_base_id = os.getenv("AIRTABLE_STERILIZATION_BASE_ID", None)

version = os.getenv("VERSION", "unknown")

# GlitchTip / Sentry error tracking (optional; disabled when the DSN is empty).
glitchtip_dsn = os.getenv("GLITCHTIP_DSN", None)
# Deployment name attached to every reported event (e.g. production, staging).
environment = os.getenv("ENVIRONMENT", "production")
# Fraction of transactions sampled for performance tracing (0.0–1.0).
glitchtip_traces_sample_rate = float(os.getenv("GLITCHTIP_TRACES_SAMPLE_RATE", "0.01"))

SESSION_NAME = os.getenv("SESSION_NAME", "catebi")

AIRTABLE_TIMEOUT = (10, 30)

# Timezone the bot operates in (all schedule times are interpreted in it).
TIMEZONE = "Asia/Tbilisi"
