"""Admin/curator notification callback flows: settings menu, sending, and steril."""

import logging
from datetime import datetime, timedelta

from pyairtable.formulas import match
from telethon import Button

from app import state
from app.constants import SCHEDULE_WINDOW_DAYS
from app.models import Notification
from app.services.notification_service import send_notifications
from app.services.schedule_service import show_loading_state
from app.text.dates import format_date_by_language
from app.translations import (
    button_back,
    button_curator_notifications_send_all,
    button_curator_notifications_send_cleaning,
    button_curator_notifications_send_medical,
    button_notifications_send_menu,
    button_notifications_settings_cleaning_text,
    button_notifications_settings_date_threshold,
    button_notifications_settings_medical_text,
    button_notifications_settings_notify_at,
    button_notifications_settings_text_menu,
    button_notifications_text_reset,
    button_steril_own_dates,
    button_yes,
    default_cleaning_notification_text,
    default_medical_notification_text,
    notifications_menu,
    notifications_send_menu,
    notifications_send_success,
    notifications_settings_date_threshold_prompt,
    notifications_settings_date_threshold_success,
    notifications_settings_notify_at_prompt,
    notifications_settings_notify_at_success,
    notifications_settings_text_menu,
    notifications_settings_text_prompt,
    notifications_steril_curator_confirm_prompt,
    notifications_steril_curator_dates_prompt,
    notifications_steril_curator_start_date_prompt,
    notifications_steril_message,
    notifications_steril_volunteer_acceptance_prompt,
    notifications_steril_volunteer_release_date_prompt,
)


async def open_menu(ctx):
    """The main curator notifications menu (data: notifications;;/unset;/reset;)."""
    event, user, language = ctx.event, ctx.user, ctx.language
    _, action, notif_type = ctx.data.split(";")
    logging.info(f"Notifications settings: {action}, {notif_type}")

    if action == "unset":
        state.custom_text_setting.pop(event.sender.id)

    current_settings = Notification.first(
        fields=["admin_curator", "notify_at", "custom_text_cleaning", "custom_text_medical", "date_threshold"],
        formula=match({"telegram_chat_id": event.sender.id}),
    )
    if not current_settings:
        current_settings = Notification(
            admin_curator=event.sender.username,
            volunteer=user,
            telegram_chat_id=event.sender.id,
            notify_at="12:00",
            date_threshold="+1",
        )
        current_settings.save()

    if action == "reset":
        if notif_type == "cleaning":
            current_settings.custom_text_cleaning = ""
        elif notif_type == "medical":
            current_settings.custom_text_medical = ""
        current_settings.save()
        state.custom_text_setting.pop(event.sender.id)

    buttons = [
        [Button.inline(button_notifications_settings_text_menu[language], data="notifications_settings_text_menu")],
        [Button.inline(button_notifications_settings_notify_at[language], data="notifications_settings_notify_at")],
        [
            Button.inline(
                button_notifications_settings_date_threshold[language], data="notifications_settings_date_threshold"
            )
        ],
        [Button.inline(button_notifications_send_menu[language], data="notifications_send_menu")],
        [Button.inline(button_back[language], data="back")],
    ]
    notification_date = datetime.now().date() + timedelta(days=int(str(current_settings.date_threshold).split("+")[1]))
    await event.edit(
        notifications_menu[language].format(
            str(current_settings.custom_text_cleaning).format(format_date_by_language(notification_date, language))
            if current_settings.custom_text_cleaning != ""
            else default_cleaning_notification_text[language].format(
                format_date_by_language(notification_date, language)
            ),
            str(current_settings.custom_text_medical).format(format_date_by_language(notification_date, language))
            if current_settings.custom_text_medical != ""
            else default_medical_notification_text[language].format(
                format_date_by_language(notification_date, language)
            ),
            current_settings.notify_at,
            current_settings.date_threshold,
            format_date_by_language(notification_date, language),
        ),
        buttons=buttons,
    )


async def open_text_menu(ctx):
    event, language = ctx.event, ctx.language
    buttons = [
        [
            Button.inline(
                button_notifications_settings_cleaning_text[language], data="notifications_settings_text;cleaning"
            )
        ],
        [
            Button.inline(
                button_notifications_settings_medical_text[language], data="notifications_settings_text;medical"
            )
        ],
        [Button.inline(button_back[language], data="notifications;;")],
    ]
    await event.edit(notifications_settings_text_menu[language], buttons=buttons)


async def choose_text_type(ctx):
    event, language = ctx.event, ctx.language
    _, notif_type = ctx.data.split(";")
    # Arm the free-text FSM (consumed by handlers.text_input.custom_notifications_handler).
    state.custom_text_setting[event.sender.id] = {"type": notif_type}
    state.custom_text_setting[event.sender.id]["prompt"] = await event.edit(
        notifications_settings_text_prompt[language],
        buttons=[
            Button.inline(button_back[language], data="notifications;unset;"),
            Button.inline(button_notifications_text_reset[language], data=f"notifications;reset;{notif_type}"),
        ],
    )


async def open_notify_at_menu(ctx):
    event, language = ctx.event, ctx.language
    hours = [f"{i:02d}:00" for i in range(24)]
    buttons = [
        [Button.inline(hour, data=f"notifications_settings_notify_at;{hour}") for hour in hours[i : i + 4]]
        for i in range(0, len(hours), 4)
    ]
    buttons.append([Button.inline(button_back[language], data="notifications;;")])
    await event.edit(notifications_settings_notify_at_prompt[language], buttons=buttons)


async def set_notify_at(ctx):
    event, language = ctx.event, ctx.language
    _, time_str = ctx.data.split(";")
    hour, minute = time_str.split(":")
    admin = Notification.first(formula=match({"telegram_chat_id": event.sender.id}))
    admin.notify_at = f"{hour}:{minute}"
    admin.save()
    await event.edit(
        notifications_settings_notify_at_success[language].format(f"{hour}:{minute}"),
        buttons=[Button.inline(button_back[language], data="notifications;;")],
    )


async def open_date_threshold_menu(ctx):
    event, language = ctx.event, ctx.language
    days = [f"+{i}" for i in range(1, 7)]
    buttons = [[Button.inline(day, data=f"notifications_settings_date_threshold;{day}") for day in days]]
    buttons.append([Button.inline(button_back[language], data="notifications;;")])
    await event.edit(notifications_settings_date_threshold_prompt[language], buttons=buttons)


async def set_date_threshold(ctx):
    event, language = ctx.event, ctx.language
    _, day = ctx.data.split(";")
    admin = Notification.first(formula=match({"telegram_chat_id": event.sender.id}))
    admin.date_threshold = day
    admin.save()

    day_variation = {
        "en": "days" if int(day) > 1 else "day",
        "ru": "день" if int(day) == 1 else "дня" if int(day) < 5 else "дней",
    }
    await event.edit(
        notifications_settings_date_threshold_success[language].format(day, day_variation[language]),
        buttons=[Button.inline(button_back[language], data="notifications;;")],
    )


async def open_send_menu(ctx):
    event, language = ctx.event, ctx.language
    buttons = [
        [Button.inline(button_curator_notifications_send_cleaning[language], data="notifications_send;cleaning;")],
        [Button.inline(button_curator_notifications_send_medical[language], data="notifications_send;medical;")],
        [Button.inline(button_curator_notifications_send_all[language], data="notifications_send;all;")],
        [Button.inline(button_back[language], data="notifications;;")],
    ]
    await event.edit(notifications_send_menu[language], buttons=buttons)


async def send_now(ctx):
    event, language = ctx.event, ctx.language
    _, notif_type, date = ctx.data.split(";")
    if date != "":
        date = datetime.fromtimestamp(float(date))
    all_count, received_count = await send_notifications(event.sender.id, notif_type, date)
    await event.edit(
        notifications_send_success[language].format(received_count, all_count),
        buttons=[Button.inline(button_back[language], data="back")],
    )


async def open_steril_menu(ctx):
    """Curator picks the acceptance/release weekend (data: notifications_steril;;)."""
    event, language = ctx.event, ctx.language
    today = datetime.now().date()
    next_saturday = today + timedelta(days=(5 - today.weekday()) % 7)
    next_sunday = next_saturday + timedelta(days=1)
    next_next_saturday = next_saturday + timedelta(days=7)
    next_next_sunday = next_next_saturday + timedelta(days=1)

    buttons = [
        [
            Button.inline(
                f"{format_date_by_language(next_saturday, language)} — {format_date_by_language(next_sunday, language)}",
                data=f"notifications_steril;{next_saturday}",
            )
        ],
        [
            Button.inline(
                f"{format_date_by_language(next_next_saturday, language)} — {format_date_by_language(next_next_sunday, language)}",
                data=f"notifications_steril;{next_next_saturday}",
            )
        ],
        [Button.inline(button_steril_own_dates[language], data="notifications_steril_own_dates;;")],
        [Button.inline(button_back[language], data="back")],
    ]
    await event.edit(notifications_steril_curator_dates_prompt[language], buttons=buttons)


async def open_steril_own_dates(ctx):
    event, language = ctx.event, ctx.language
    today = datetime.now().date()
    available_dates = [today + timedelta(days=i) for i in range(SCHEDULE_WINDOW_DAYS)]
    buttons = [
        [
            Button.inline(format_date_by_language(date, language), data=f"notifications_steril;{date}")
            for date in available_dates[i : i + 2]
        ]
        for i in range(0, len(available_dates), 2)
    ]
    buttons.append([Button.inline(button_back[language], data="notifications_steril;;")])
    await event.edit(notifications_steril_curator_start_date_prompt[language], buttons=buttons)


async def choose_steril_dates(ctx):
    event, language = ctx.event, ctx.language
    _, start = ctx.data.split(";")
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = start_date + timedelta(days=1)

    formatted_start_date = format_date_by_language(start_date, language)
    formatted_end_date = format_date_by_language(end_date, language)
    buttons = [
        [Button.inline(button_yes[language], data=f"notifications_steril_confirm;{start}")],
        [Button.inline(button_back[language], data="notifications_steril;;")],
    ]
    await event.edit(
        notifications_steril_curator_confirm_prompt[language].format(
            notifications_steril_message[language].format(
                formatted_start_date,
                formatted_end_date,
                formatted_start_date,
                f"{formatted_start_date} и {formatted_end_date}"
                if language == "ru"
                else f"{formatted_start_date} and {formatted_end_date}",
                formatted_end_date,
            )
        ),
        buttons=buttons,
    )


async def confirm_steril(ctx):
    event, language = ctx.event, ctx.language
    _, start = ctx.data.split(";")
    start_date = datetime.strptime(start, "%Y-%m-%d")

    await show_loading_state(event, language)
    all_count, received_count = await send_notifications(event.sender.id, "steril", start_date)
    await event.edit(
        notifications_send_success[language].format(received_count, all_count),
        buttons=[[Button.inline(button_back[language], data="back")]],
    )


async def new_steril(ctx):
    """Volunteer chose accept/release from a steril notification (data: new_steril_*)."""
    event, language, data = ctx.event, ctx.language, ctx.data
    steril_type = data.split("_")[2].split(";")[0]  # 'acceptance' or 'release'
    curator = data.split(";")[1]
    date = datetime.fromtimestamp(float(data.split(";")[2])).date()

    if steril_type == "acceptance":
        buttons = [
            [
                Button.inline(
                    format_date_by_language(date, language), data=f"add_schedule;{date};;steril_{steril_type};{curator}"
                )
            ],
            [
                Button.inline(
                    format_date_by_language(date + timedelta(days=1), language),
                    data=f"add_schedule;{date + timedelta(days=1)};;steril_{steril_type};{curator}",
                )
            ],
        ]
    else:
        buttons = [
            [
                Button.inline(
                    format_date_by_language(date, language),
                    data=f"set_schedule_time;{date};steril_{steril_type};{curator}",
                )
            ],
            [
                Button.inline(
                    format_date_by_language(date + timedelta(days=1), language),
                    data=f"set_schedule_time;{date + timedelta(days=1)};steril_{steril_type};{curator}",
                )
            ],
        ]
    buttons.append([Button.inline(button_back[language], data="back_steril")])

    await event.edit(
        notifications_steril_volunteer_acceptance_prompt[language]
        if steril_type == "acceptance"
        else notifications_steril_volunteer_release_date_prompt[language],
        buttons=buttons,
    )
