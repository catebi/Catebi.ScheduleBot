from telethon import utils

from app.bot_client import bot
from app.constants import SUPERGROUP_ID_PREFIX
from app.data.airtable_async import run_airtable
from app.models import Settings


async def load_settings() -> dict:
    settings = await run_airtable(Settings.all)
    return {setting.key: setting.value for setting in settings}


async def resolve_topic_entity(topic_chat_id):
    marked_topic_chat_id = int(SUPERGROUP_ID_PREFIX + str(topic_chat_id))
    topic_entity = await bot.get_entity(marked_topic_chat_id)
    return utils.get_input_channel(utils.get_input_peer(topic_entity))
