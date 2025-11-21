import os

# Telegram API credentials
api_id = os.getenv('API_ID', None)
api_hash = os.getenv('API_HASH', None)
bot_token = os.getenv('BOT_TOKEN', None)

# Airtable API credentials
airtable_api_key = os.getenv('AIRTABLE_API_KEY', None)
airtable_base_id = os.getenv('AIRTABLE_BASE_ID', None)
airtable_sterilization_base_id = os.getenv('AIRTABLE_STERILIZATION_BASE_ID', None)

version = os.getenv('VERSION', 'unknown')
