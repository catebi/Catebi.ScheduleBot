import logging
from datetime import datetime, timedelta

from pyairtable.formulas import match
from telethon import Button

from app import state
from app.bot_client import bot
from app.constants import (
    DUTY_SHORT_CLEANING,
    DUTY_SHORT_GENERAL_CLEANING,
    DUTY_SHORT_MEDICAL,
    SCHEDULE_TYPES,
    SCHEDULE_WINDOW_DAYS,
    TYPE_CLEANING,
    TYPE_CLEANING_CATLOFT,
    TYPE_GENERAL_CLEANING,
    TYPE_MEDICAL,
    TYPE_STERIL_ACCEPTANCE,
    TYPE_STERIL_RELEASE,
)
from app.data.airtable_async import run_airtable
from app.data.coerce import to_local
from app.models import Schedule
from app.services.schedule_service import show_loading_state, update_volunteers
from app.text.dates import format_date_by_language
from app.text.labels import label_for_type, slot_indicator
from app.translations import (
    add_schedule_success,
    add_schedule_success_steril_acceptance,
    add_schedule_topic_message,
    add_schedule_topic_steril_acceptance_message,
    button_back,
    button_type_cleaning,
    button_type_cleaning_location,
    button_type_general_cleaning,
    button_type_medical,
    button_type_steril_acceptance,
    button_type_steril_release,
    button_yes,
    curator_new_steril_signup,
    curator_steril_word,
    delete_schedule_success,
    delete_schedule_success_steril_acceptance,
    delete_schedule_topic_message,
    delete_schedule_topic_steril_acceptance_message,
    error_no_duties,
    general_schedule,
    localized_dates,
    my_schedule_delete_prompt,
    my_schedule_delete_prompt_steril_acceptance,
    my_schedule_prompt,
    new_schedule_cleaning_location_prompt,
    new_schedule_prompt,
    new_schedule_type_prompt,
    set_schedule_time_prompt,
    topic_duty_word,
    topic_relative_day,
)

_TOPIC_LANG = "ru"


def _relative_day_ru(date):
    words = topic_relative_day[_TOPIC_LANG]
    if date == datetime.now().date():
        return words["today"]
    if date == datetime.now().date() + timedelta(days=1):
        return words["tomorrow"]
    return format_date_by_language(date, _TOPIC_LANG)


def _duty_word_ru(shift_type):
    words = topic_duty_word[_TOPIC_LANG]
    return words.get(shift_type, words["steril"])


def _topic_emoji(shift_type, arrow):
    if shift_type == "medical":
        return "🏥"
    if shift_type == "cleaning":
        return "🧹🏠"
    if shift_type == "cleaning_catloft":
        return "🧹🪜"
    if shift_type == "general_cleaning":
        return "🧼🏠"
    return arrow


async def new_schedule(ctx):
    event, data, language = ctx.event, ctx.data, ctx.language

    duty_code = data.split(";")[1]
    # No duties assigned.
    if duty_code == "none":
        await event.edit(error_no_duties[language], buttons=[Button.inline(button_back[language], data="back")])
        return
    # Multiple duties: ask which type to sign up for.
    elif len(duty_code.split("+")) > 1:
        duties = duty_code.split("+")
        buttons = []
        if DUTY_SHORT_CLEANING in duties:
            buttons.append([Button.inline(button_type_cleaning[language], data="new_schedule;cleaning")])
        if DUTY_SHORT_GENERAL_CLEANING in duties:
            buttons.append(
                [Button.inline(button_type_general_cleaning[language], data="new_schedule;general_cleaning")]
            )
        if DUTY_SHORT_MEDICAL in duties:
            buttons.append([Button.inline(button_type_medical[language], data="new_schedule;medical")])
        if TYPE_STERIL_ACCEPTANCE in duties:
            buttons.append(
                [Button.inline(button_type_steril_acceptance[language], data="new_schedule;steril_acceptance")]
            )
        if TYPE_STERIL_RELEASE in duties:
            buttons.append([Button.inline(button_type_steril_release[language], data="new_schedule;steril_release")])
        buttons.append([Button.inline(button_back[language], data="back")])
        await event.edit(new_schedule_type_prompt[language], buttons=buttons)
        return

    # Normalize short duty codes to full shift types.
    shift_type = duty_code
    if shift_type not in SCHEDULE_TYPES:
        if shift_type == DUTY_SHORT_CLEANING:
            shift_type = TYPE_CLEANING
        elif shift_type == DUTY_SHORT_GENERAL_CLEANING:
            shift_type = TYPE_GENERAL_CLEANING
        elif shift_type == DUTY_SHORT_MEDICAL:
            shift_type = TYPE_MEDICAL
        elif shift_type == TYPE_STERIL_ACCEPTANCE:
            shift_type = TYPE_STERIL_ACCEPTANCE
        elif shift_type == TYPE_STERIL_RELEASE:
            shift_type = TYPE_STERIL_RELEASE

    # Ask for cleaning location before picking a date (third segment marks it done).
    if shift_type in (TYPE_CLEANING, TYPE_GENERAL_CLEANING) and len(data.split(";")) < 3:
        buttons = [
            [Button.inline(button_type_cleaning_location[language]["catflat"], data=f"new_schedule;{shift_type};loc")],
            [Button.inline(button_back[language], data="back")],
        ]
        await event.edit(new_schedule_cleaning_location_prompt[language], buttons=buttons)
        return

    # Build the available dates for the next two weeks, tallying taken slots.
    available_dates = {}
    for i in range(SCHEDULE_WINDOW_DAYS):
        date = datetime.now().date() + timedelta(days=i)
        # Regular cleaning runs on weekdays only, general cleaning on weekends only.
        if shift_type == TYPE_CLEANING and date.weekday() >= 5:
            continue
        if shift_type == TYPE_GENERAL_CLEANING and date.weekday() < 5:
            continue
        available_dates[date] = {
            "cleaning": 0,
            "cleaning_catloft": 0,
            "general_cleaning": 0,
            "medical": 0,
            "steril_release": 0,
            "steril_acceptance": 0,
        }
    logging.info(f"Available dates: {available_dates}")

    state.scheduled_dates = await run_airtable(
        Schedule.all, fields=["date", "type"], formula=match({"date": (">=", datetime.now().date())}), sort=["date"]
    )
    for entry in state.scheduled_dates:
        entry.date = to_local(entry.date)
        logging.info(f"Scheduled date: {entry.date.date()}, type: {entry.type}")
        if entry.date.date() in available_dates:
            available_dates[entry.date.date()][entry.type] += 1

    # Hide dates the user already signed up for (for this shift type).
    user_scheduled_dates = await run_airtable(
        Schedule.all, fields=["date", "type"], formula=match({"telegram_chat_id": event.sender.id})
    )
    for entry in user_scheduled_dates:
        entry.date = to_local(entry.date)
        if entry.date.date() in available_dates and entry.type == shift_type:
            available_dates.pop(entry.date.date())

    buttons = []
    for date in available_dates:
        slot_count = (
            available_dates[date][shift_type]
            if shift_type in [TYPE_CLEANING, TYPE_CLEANING_CATLOFT, TYPE_GENERAL_CLEANING]
            else available_dates[date]["cleaning"]
        )
        cb_data = (
            f"add_schedule;{date};;{shift_type}"
            if shift_type == TYPE_STERIL_ACCEPTANCE
            else f"set_schedule_time;{date};{shift_type}"
        )
        buttons.append(
            [Button.inline(f"{format_date_by_language(date, language)} {slot_indicator(slot_count)}", data=cb_data)]
        )
    buttons.append([Button.inline(button_back[language], data="back")])
    await event.edit(new_schedule_prompt[language].format(label_for_type(shift_type, language)), buttons=buttons)


async def set_schedule_time(ctx):
    event, data, language = ctx.event, ctx.data, ctx.language

    if len(data.split(";")) < 4:
        _, date_str, shift_type = data.split(";")
        extra = ""
    else:
        _, date_str, shift_type, extra = data.split(";")

    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    current_time = datetime.now()
    # First selectable hour is the next hour today, or midnight for future dates.
    start_hour = current_time.hour + 1 if date == current_time.date() else 0

    buttons = []
    for j in range(0, 24, 4):
        row = []
        for i in range(j, min(j + 4, 24)):
            if i >= start_hour:
                row.append(Button.inline(f"{i:02d}:00", data=f"add_schedule;{date};{i:02d}:00;{shift_type};{extra}"))
        if row:
            buttons.append(row)
    buttons.append([Button.inline(button_back[language], data="back")])
    await event.edit(
        set_schedule_time_prompt[language].format(format_date_by_language(date, language)), buttons=buttons
    )


async def add_schedule(ctx):
    event, data, user, language = ctx.event, ctx.data, ctx.user, ctx.language
    await show_loading_state(event, language)

    if len(data.split(";")) < 5:
        _, date_str, time_str, shift_type = data.split(";")
        extra = ""
    else:
        _, date_str, time_str, shift_type, extra = data.split(";")
    if time_str == "":
        time_str = "00:00"

    date = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").astimezone(datetime.now().astimezone().tzinfo)
    new_shift = Schedule(
        telegram_chat_id=event.sender.id,
        date=date,
        telegram="@" + str(event.sender.username).lower(),
        volunteer=user,
        type=shift_type,
    )
    await run_airtable(new_shift.save)
    await update_volunteers("add_schedule")

    if shift_type == TYPE_STERIL_ACCEPTANCE:
        await event.edit(
            add_schedule_success_steril_acceptance[language].format(
                button_type_steril_acceptance[language], format_date_by_language(date, language)
            ),
            buttons=[Button.inline(button_back[language], data="back")],
        )
        if not state.topic_input_entity:
            logging.error("Topic chat ID is not set, please set it in the settings.")
            return
        await bot.send_message(
            state.topic_input_entity,
            add_schedule_topic_steril_acceptance_message[_TOPIC_LANG].format(
                "😸⬇️", user.telegram, _relative_day_ru(date)
            ),
            reply_to=state.steril_cat_topic_id,
        )
        return

    await event.edit(
        add_schedule_success[language].format(
            label_for_type(shift_type, language), format_date_by_language(date, language), date.strftime("%H:%M")
        ),
        buttons=[Button.inline(button_back[language], data="back")],
    )
    if not state.topic_input_entity:
        logging.error("Topic chat ID is not set, please set it in the settings.")
        return
    await bot.send_message(
        state.topic_input_entity,
        add_schedule_topic_message[_TOPIC_LANG].format(
            _topic_emoji(shift_type, arrow="😸⬆️"),
            user.telegram,
            _duty_word_ru(shift_type),
            _relative_day_ru(date),
            date.strftime("%H:%M"),
        ),
        reply_to=state.cleaning_topic_id
        if shift_type in ["cleaning", "cleaning_catloft", "general_cleaning"]
        else state.medical_topic_id
        if shift_type == "medical"
        else state.steril_cat_topic_id,
    )

    if extra:
        curator = int(extra)
        steril_word = curator_steril_word[_TOPIC_LANG]["acceptance" if shift_type == "steril_acceptance" else "release"]
        await bot.send_message(
            curator,
            curator_new_steril_signup[_TOPIC_LANG].format(
                steril_word, user.telegram, format_date_by_language(date, language)
            ),
        )


async def my_schedule(ctx):
    event, language = ctx.event, ctx.language
    await show_loading_state(event, language)

    state.scheduled_dates = await run_airtable(
        Schedule.all,
        fields=["date", "type"],
        formula=match({"telegram_chat_id": event.sender.id, "date": (">=", datetime.now().date())}),
        sort=["date"],
    )
    for shift in state.scheduled_dates:
        shift.date = to_local(shift.date)
    buttons = [
        [
            Button.inline(
                f"{format_date_by_language(shift.date, language)}: {label_for_type(shift.type, language)}"
                + (f" ({shift.date.strftime('%H:%M')})" if shift.type != TYPE_STERIL_ACCEPTANCE else ""),
                data=f"my_schedule_delete;{shift.date.strftime('%Y-%m-%d %H:%M')};{shift.type}",
            )
        ]
        for shift in state.scheduled_dates
    ]
    buttons.append([Button.inline(button_back[language], data="back")])
    await event.edit(my_schedule_prompt[language], buttons=buttons)


async def my_schedule_delete(ctx):
    event, language = ctx.event, ctx.language
    _, date_str, shift_type = ctx.data.split(";")
    date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    logging.info(f"Deleting schedule: {date}, {shift_type}")

    buttons = [
        [Button.inline(button_yes[language], data=f"delete_schedule;{date};{shift_type}")],
        [Button.inline(button_back[language], data="back")],
    ]

    if shift_type == TYPE_STERIL_ACCEPTANCE:
        await event.edit(
            my_schedule_delete_prompt_steril_acceptance[language].format(
                button_type_steril_acceptance[language], format_date_by_language(date, language)
            ),
            buttons=buttons,
        )
        return

    await event.edit(
        my_schedule_delete_prompt[language].format(
            label_for_type(shift_type, language), format_date_by_language(date, language), date.strftime("%H:%M")
        ),
        buttons=buttons,
    )


async def delete_schedule(ctx):
    event, user, language = ctx.event, ctx.user, ctx.language
    await show_loading_state(event, language)

    _, date_str, shift_type = ctx.data.split(";")
    date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").astimezone(datetime.now().astimezone().tzinfo)

    unwanted_schedule = await run_airtable(
        Schedule.first, formula=match({"telegram_chat_id": event.sender.id, "date": date, "type": shift_type})
    )
    if unwanted_schedule:
        await run_airtable(unwanted_schedule.delete)
    else:
        logging.error(f"Record not found: {event.sender.id}, {date}, {shift_type}; probably already deleted.")
    await update_volunteers("delete_schedule")

    if not state.topic_input_entity:
        logging.error("Topic chat ID is not set, please set it in the settings.")
        return

    if shift_type == TYPE_STERIL_ACCEPTANCE:
        await event.edit(
            delete_schedule_success_steril_acceptance[language].format(
                button_type_steril_acceptance[language], format_date_by_language(date, language)
            ),
            buttons=[Button.inline(button_back[language], data="back")],
        )
        await bot.send_message(
            state.topic_input_entity,
            delete_schedule_topic_steril_acceptance_message[_TOPIC_LANG].format(
                "😿⬇️", user.telegram, _relative_day_ru(date)
            ),
            reply_to=state.steril_cat_topic_id,
        )
        return

    await event.edit(
        delete_schedule_success[language].format(
            label_for_type(shift_type, language), format_date_by_language(date, language), date.strftime("%H:%M")
        ),
        buttons=[Button.inline(button_back[language], data="back")],
    )
    await bot.send_message(
        state.topic_input_entity,
        delete_schedule_topic_message[_TOPIC_LANG].format(
            _topic_emoji(shift_type, arrow="😿⬆️"),
            user.telegram,
            _duty_word_ru(shift_type),
            _relative_day_ru(date),
            date.strftime("%H:%M"),
        ),
        reply_to=state.cleaning_topic_id
        if shift_type in ["cleaning", "cleaning_catloft", "general_cleaning"]
        else state.medical_topic_id
        if shift_type == "medical"
        else state.steril_cat_topic_id,
    )


async def general_schedule_view(ctx):
    event, language, today = ctx.event, ctx.language, ctx.today

    translated_dates = []
    if language == "ru":
        for item in state.dates_list:
            for key, value in localized_dates["ru"].items():
                item = item.replace(key, value)
            translated_dates.append(item)

    await event.edit(
        general_schedule[language].format(
            today,
            ", ".join(state.today_volunteers_list) if state.today_volunteers_list else "😿",
            "\n".join(state.dates_list if language == "en" else translated_dates),
        ),
        buttons=[Button.inline(button_back[language], data="back")],
    )
