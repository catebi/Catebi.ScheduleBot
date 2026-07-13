from datetime import datetime

from pyairtable.formulas import match
from telethon import events

from app.airtable_logger import airtable_context
from app.bot_client import bot
from app.flows import notifications, settings
from app.flows import schedule as schedule_flow
from app.flows.protocol import CallbackContext
from app.handlers.commands import start_handler
from app.logging_setup import logger
from app.models import Volunteer


@bot.on(events.CallbackQuery())
@logger
@airtable_context("callback_handler")
async def callback_handler(event):
    data = str(event.data.decode("utf-8"))
    user = Volunteer.first(formula=match({"telegram_chat_id": event.sender.id}))
    today = datetime.now().date().strftime("%d.%m")

    # Change user's language (handled before the language is resolved below).
    if data.startswith("language"):
        _, lang = data.split(":")
        await start_handler(event, check_user=True, language=lang)
        return

    language = user.language
    ctx = CallbackContext(event, data, user, language, today)

    # --- Scheduling wizard --------------------------------------------------
    if data.startswith("new_schedule"):
        await schedule_flow.new_schedule(ctx)

    if data.startswith("set_schedule_time") and data.split(";")[2] not in ["steril_acceptance"]:
        await schedule_flow.set_schedule_time(ctx)

    if data.startswith("add_schedule"):
        await schedule_flow.add_schedule(ctx)

    if data == "my_schedule":
        await schedule_flow.my_schedule(ctx)

    if data.startswith("my_schedule_delete"):
        await schedule_flow.my_schedule_delete(ctx)

    if data.startswith("delete_schedule"):
        await schedule_flow.delete_schedule(ctx)

    if data == "general_schedule":
        await schedule_flow.general_schedule_view(ctx)

    # --- Curator notifications menu -----------------------------------------
    if (
        data.startswith("notifications;;")
        or data.startswith("notifications;unset;")
        or data.startswith("notifications;reset;")
    ):
        await notifications.open_menu(ctx)

    if data == "notifications_settings_text_menu":
        await notifications.open_text_menu(ctx)

    if data.startswith("notifications_settings_text;"):
        await notifications.choose_text_type(ctx)

    if data == "notifications_settings_notify_at":
        await notifications.open_notify_at_menu(ctx)

    if data.startswith("notifications_settings_notify_at;"):
        await notifications.set_notify_at(ctx)

    if data == "notifications_settings_date_threshold":
        await notifications.open_date_threshold_menu(ctx)

    if data.startswith("notifications_settings_date_threshold;"):
        await notifications.set_date_threshold(ctx)

    if data == "notifications_send_menu":
        await notifications.open_send_menu(ctx)

    if data.startswith("notifications_send;"):
        await notifications.send_now(ctx)

    # --- Cat acceptance/release notifications -------------------------------
    if data.startswith("notifications_steril;;"):
        await notifications.open_steril_menu(ctx)
        return  # stop the broader "notifications_steril;" prefix below from also matching

    if data.startswith("notifications_steril_own_dates"):
        await notifications.open_steril_own_dates(ctx)

    if data.startswith("notifications_steril;"):
        await notifications.choose_steril_dates(ctx)

    if data.startswith("notifications_steril_confirm;"):
        await notifications.confirm_steril(ctx)

    if data.startswith("new_steril_"):
        await notifications.new_steril(ctx)

    # --- Settings & back navigation -----------------------------------------
    if data == "change_language":
        await settings.change_language(ctx)

    if data.startswith("change_view;"):
        await settings.change_view(ctx)

    if data.startswith("change_view_to;"):
        await settings.change_view_to(ctx)

    if data == "back_steril":
        await settings.back_steril(ctx)

    if data == "back_settings":
        await settings.back_settings(ctx)

    if data == "back":
        await settings.back(ctx)
