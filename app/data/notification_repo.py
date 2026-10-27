from pyairtable.formulas import match

from app.data.airtable_async import run_airtable
from app.models import Notification


async def get_or_create_notification(telegram_chat_id, volunteer=None, admin_curator=None):
    notification = await run_airtable(Notification.first, formula=match({"telegram_chat_id": telegram_chat_id}))
    if notification is None:
        notification = Notification(
            admin_curator=admin_curator,
            volunteer=volunteer,
            telegram_chat_id=telegram_chat_id,
            notify_at="12:00",
            date_threshold="+1",
        )
        await run_airtable(notification.save)
    return notification
