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

SESSION_NAME = os.getenv("SESSION_NAME", "catebi")

AIRTABLE_TIMEOUT = (10, 30)

# Timezone the bot operates in (all schedule times are interpreted in it).
TIMEZONE = "Asia/Tbilisi"
