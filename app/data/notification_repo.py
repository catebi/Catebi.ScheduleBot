from pyairtable.formulas import match

from app.models import Notification


def get_or_create_notification(telegram_chat_id, volunteer=None, admin_curator=None):
    notification = Notification.first(formula=match({"telegram_chat_id": telegram_chat_id}))
    if notification is None:
        notification = Notification(
            admin_curator=admin_curator,
            volunteer=volunteer,
            telegram_chat_id=telegram_chat_id,
            notify_at="12:00",
            date_threshold="+1",
        )
        notification.save()
    return notification
