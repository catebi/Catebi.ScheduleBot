from telethon import TelegramClient, events, Button, utils, functions, types, errors

import logging
import os, time
import json
from pyairtable import Api
from pyairtable.formulas import match, OR, AND, GTE, LTE, Field
from datetime import datetime, timedelta
from babel.dates import format_date

import aiocron
import asyncio

from settings import *
from translations import *
from airtable_model import *
from airtable_logger import airtable_context  # Import the context manager

# Initialize sterilization base API
sterilization_api = Api(api_key=airtable_api_key) if airtable_api_key else None

logging.basicConfig(format='[%(levelname)s] %(message)s',
                    level=logging.WARNING)

def logger(func):
    def decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            logging.error(err, exc_info=True)
    return decorator

os.environ['TZ'] = 'Asia/Tbilisi'
time.tzset()
logging.info(f"Timezone set to {os.environ['TZ']}, time is {datetime.now()}.")

# Initialize Airtable API
api = Api(api_key=airtable_api_key)

bot = TelegramClient('catebi', api_id, api_hash).start(bot_token=bot_token)

# Initialize global variables
scheduled_dates = None
today_volunteers_list = None
dates_list = None
topic_input_entity = None
cleaning_topic_id = None
medical_topic_id = None
steril_cat_topic_id = None

steril_notification_message = None

# region Functions

# function to format the date in the user's language
def format_date_by_language(date: datetime, language: str):
    formatted_date = format_date(date, format='dd.MM, EEEE', locale=language) # use generic format for all languages: 31.12, Monday
    return f"{formatted_date.split(' ')[0]} {formatted_date.split(' ')[1].capitalize()}" # capitalize the first letter of the day of the week

# Helper function to parse date from Airtable field
def parse_airtable_date(date_value):
    """Parse date from Airtable field (string, datetime, or list) and return date object."""
    if not date_value:
        return None

    # Handle lookup fields which might be arrays
    if isinstance(date_value, list) and len(date_value) > 0:
        date_value = date_value[0]

    # Parse date string if it's a string
    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value.split('T')[0], '%Y-%m-%d').date()
        except:
            return None

    # If it's already a date object, extract date if needed
    if hasattr(date_value, 'date'):
        return date_value.date()

    return None

# Build a non-wrapping emoji + username label
WORD_JOINER = '\u2060'
NBSP = '\u00A0'
def build_label(date_type: str, username: str):
    if date_type == 'cleaning':
        return '🧹' + WORD_JOINER + username
    if date_type == 'medical':
        return '🏥' + WORD_JOINER + username
    if date_type == 'steril_release':
        return '😸' + WORD_JOINER + '⬆️' + WORD_JOINER + username
    # steril_acceptance and any other types default to down arrow
    return '😸' + WORD_JOINER + '⬇️' + WORD_JOINER + username

# Helper function to show loading state and prevent multiple button presses
async def show_loading_state(event, user_language: str):
    """Show loading message and remove buttons to prevent multiple presses"""
    try:
        await event.edit(loading_text[user_language], buttons=None)
    except Exception as err:
        logging.error(f"Error showing loading state: {err}")

# update volunteers list and schedule
@airtable_context('update_volunteers')
async def update_volunteers(step: str):
    global scheduled_dates, today_volunteers_list, dates_list, topic_input_entity, cleaning_topic_id, medical_topic_id, steril_cat_topic_id
    scheduled_dates = Schedule.all(
        fields=['date', 'volunteer', 'telegram', 'type'],
        sort=['date'],
        formula=match({
            # set hours, minutes, seconds and microseconds to 0 to display all schedules for today
            # if need to hide past times in todays_volunteers_list, remove time overrides but leave tzinfo
            'date': (">=", datetime.today().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.now().astimezone().tzinfo))
        })
    )

    today_volunteers_list = []
    dates_list = []
    today = datetime.now().date().strftime('%d.%m')
    for date in scheduled_dates:
        date.date = date.date.astimezone(datetime.now().astimezone().tzinfo) # convert date to local timezone
        # aggregate volunteers if two are scheduled at the same date
        if date.date.date() == datetime.now().date():
            entry = build_label(date.type, date.volunteer.telegram)
            if date.type != 'steril_acceptance':
                entry += f"{NBSP}({date.date.strftime('%H:%M')})"
            today_volunteers_list.append(entry)
            continue
        same_date = [d for d in dates_list if d.startswith(date.date.strftime('%d.%m'))]
        if same_date:
            dates_list.remove(same_date[0])
            new_entry = build_label(date.type, date.volunteer.telegram)
            if date.type != 'steril_acceptance':
                new_entry += f"{NBSP}({date.date.strftime('%H:%M')})"
            dates_list.append(f"{date.date.strftime('%d.%m, %A')}: {same_date[0].split(': ')[1]}, {new_entry}")
        else:
            entry = build_label(date.type, date.volunteer.telegram)
            if date.type != 'steril_acceptance':
                entry += f"{NBSP}({date.date.strftime('%H:%M')})"
            dates_list.append(f"{date.date.strftime('%d.%m, %A')}: {entry}")

    logging.info(f"<{step}> Volunteers list and schedule updated.")

    # update messages in topics
    settings = Settings.all()
    settings_dict = {setting.key: setting.value for setting in settings}

    if not settings_dict.get('topic_chat_id'):
        logging.error(f"<{step}> Topic chat ID is not set, please set it in the settings.")
        return

    topic_chat_id = settings_dict.get('topic_chat_id')
    cleaning_topic_id = settings_dict.get('cleaning_topic_id')
    medical_topic_id = settings_dict.get('medical_topic_id')
    steril_cat_topic_id = settings_dict.get('steril_cat_topic_id')
    last_pinned_general_message_id = settings_dict.get('last_pinned_general_message_id')
    last_pinned_cleaning_message_id = settings_dict.get('last_pinned_cleaning_message_id')
    last_pinned_medical_message_id = settings_dict.get('last_pinned_medical_message_id')
    last_pinned_steril_message_id = settings_dict.get('last_pinned_steril_message_id')

    messages = [
        (last_pinned_general_message_id, 'last_pinned_general_message_id', None),
        (last_pinned_cleaning_message_id, 'last_pinned_cleaning_message_id', cleaning_topic_id),
        (last_pinned_medical_message_id, 'last_pinned_medical_message_id', medical_topic_id),
        (last_pinned_steril_message_id, 'last_pinned_steril_message_id', steril_cat_topic_id)
    ]

    try:
        marked_topic_chat_id = int('-100'+str(topic_chat_id))
        topic_entity = await bot.get_entity(marked_topic_chat_id)
        topic_input_entity = utils.get_input_channel(utils.get_input_peer(topic_entity))
    except ValueError as err:
        logging.error(f"<{step}> Error getting topic chat entity, check if the chat ID is correct and bot is in the chat:\nmarked_topic_chat_id: {marked_topic_chat_id}\n{err}")
        return

    for message_id, setting_key, topic in messages:
        if not message_id:
            logging.info(f"<{step}> Message ID is not set, creating a new message.")
            pin_message = await bot.send_message(
                topic_input_entity,
                general_schedule['ru'].format(
                    today,
                    ', '.join(today_volunteers_list) if today_volunteers_list else '😿',
                    '\n'.join(dates_list)
                ),
                reply_to=topic
            )
            await bot.pin_message(topic_input_entity, pin_message.id)
            setting = Settings.first(formula=match({'key': setting_key}))
            setting.value = pin_message.id
            setting.save()

    # update messages in topics
    if step != 'startup':
        for id, setting_key, _ in messages:
            try:
                await bot.edit_message(topic_input_entity, id, general_schedule['ru'].format(
                    today,
                    ', '.join(today_volunteers_list) if today_volunteers_list else '😿',
                    '\n'.join(dates_list)
                ))
            except errors.MessageNotModifiedError:
                logging.info(f"<{step}> Message {id} in topic {topic} is already up to date, skipping edit.")
            await asyncio.sleep(0.5) # avoid flood limits

    # re-pin messages in topics if step is 'daily'
    if step == 'daily':
        # re-pin messages in topics
        for id, setting_key, topic in messages:
            if topic:
                logging.info(f"<{step}> Re-pinning message {id} in topic {topic}")
                await bot.pin_message(topic_input_entity, id)
                setting = Settings.first(formula=match({'key': setting_key}))
                setting.value = id
                setting.save()

    logging.info(f"<{step}> Messages in topics updated.")

# send notifications to volunteers, return the number of sent notifications and the total number of volunteers
@airtable_context('send_notifications')
async def send_notifications(curator_id: int, type: str = '', date: datetime = None):
    global steril_notification_message

    # send notifications to all volunteers with duties kk_cleaning
    volunteers = Volunteer.all(fields=['telegram_chat_id', 'language', 'duty_codes'])
    if type == 'cleaning':
        notifiable_volunteers = [volunteer for volunteer in volunteers if 'kk_cleaning' in volunteer.duties]
    elif type == 'medical':
        notifiable_volunteers = [volunteer for volunteer in volunteers if 'kk_medical' in volunteer.duties]
    elif type == 'steril':
        notifiable_volunteers = [volunteer for volunteer in volunteers if 'steril_cat_in_out' in volunteer.duties]
    else:
        notifiable_volunteers = [volunteer for volunteer in volunteers if 'kk_cleaning' in volunteer.duties or 'kk_medical' in volunteer.duties]

    if type != 'steril':
        curator = Volunteer.first(formula=match({'telegram_chat_id': curator_id}))
        text_cleaning = Notification.first(formula=match({'telegram_chat_id': curator_id})).custom_text_cleaning
        text_medical = Notification.first(formula=match({'telegram_chat_id': curator_id})).custom_text_medical

        if not date: # if date is not set, use the date from the notification settings
            date = datetime.now().date() + timedelta(days=int(str(Notification.first(formula=match({'telegram_chat_id': curator_id})).date_threshold).split('+')[1]))
        if not text_cleaning:
            text_cleaning = default_cleaning_notification_text[curator.language]

        if not text_medical:
            text_medical = default_medical_notification_text[curator.language]

    # count all selected volunteers
    all_volunteers_count = len(notifiable_volunteers)
    received_notifications_count = 0
    # iterate over all volunteers and send notifications
    for volunteer in notifiable_volunteers:
        try:
            duties_set = []
            if 'kk_cleaning' in volunteer.duties:
                duties_set.append('cln')
            if 'kk_medical' in volunteer.duties:
                duties_set.append('med')
            if 'steril_cat_in_out' in volunteer.duties:
                duties_set.append('steril')

            duties_set = '+'.join(duties_set)

            if type == 'steril':
                buttons = [
                    [Button.inline(button_steril_accept_acceptance[volunteer.language], data=f'new_steril_acceptance;{curator_id};{date.timestamp()}')],
                    [Button.inline(button_steril_accept_release[volunteer.language], data=f'new_steril_release;{curator_id};{date.timestamp()}')],
                    [Button.inline(button_curator_ignore[volunteer.language], data='back')]
                ]
            else:
                buttons = [
                    [Button.inline(button_new_schedule[volunteer.language], data=f'new_schedule;{duties_set}')],
                ]

            if type == 'steril':
                start_date = format_date_by_language(date, volunteer.language)
                end_date = format_date_by_language(date + timedelta(days=1), volunteer.language)
                try:
                    steril_notification_message = await bot.send_message(
                        volunteer.telegram_chat_id,
                        notifications_steril_message[volunteer.language].format(
                            start_date, end_date,
                            start_date,
                            f"{start_date} и {end_date}" if volunteer.language == 'ru' else f"{start_date} and {end_date}",
                            end_date
                        ),
                        buttons=buttons
                    )
                except Exception as err:
                    logging.error(f"Error sending steril notification to {volunteer.telegram_chat_id}: {err}", exc_info=True)
                    continue

            elif type != 'all':
                try:
                    await bot.send_message(
                        volunteer.telegram_chat_id,
                            text_cleaning.format(format_date_by_language(date, volunteer.language)) if type == 'cleaning' else text_medical.format(format_date_by_language(date, volunteer.language)),
                        buttons=buttons
                    )
                except Exception as err:
                    logging.error(f"Error sending '{type}' notification to {volunteer.telegram_chat_id}: {err}", exc_info=True)
                    continue
            else:
                try:
                    await bot.send_message(
                        volunteer.telegram_chat_id,
                        text_cleaning.format(format_date_by_language(date, volunteer.language)) + '\n\n' + text_medical.format(format_date_by_language(date, volunteer.language)),
                        buttons=buttons
                    )
                except Exception as err:
                    logging.error(f"Error sending 'all' notification to {volunteer.telegram_chat_id}: {err}", exc_info=True)
                    continue

            await asyncio.sleep(0.5) # avoid flood limits
            received_notifications_count += 1
        except Exception as err:
            logging.error(f"Error sending notification to {volunteer.telegram_chat_id}: {err}", exc_info=True)

    return all_volunteers_count, received_notifications_count

# Update volunteers list and schedule at midnight, re-pin messages in topics if needed
@logger
@aiocron.crontab('0 0 * * *') # every day at midnight
async def daily_schedule_update():
    await update_volunteers('daily')

# send personal notification to curators at their set time
@logger
@aiocron.crontab('0 * * * *') # every hour at minute 0
@airtable_context('send_curator_notifications')
async def send_curator_notifications():
    # find all volunteers with duties that contain 'kk_admin_curator'
    volunteers = Volunteer.all(fields=['telegram', 'telegram_chat_id', 'duty_codes', 'language'])
    curators = [volunteer for volunteer in volunteers if 'kk_admin_curator' in volunteer.duties]

    # If no curators, exit early
    if not curators:
        return

    # Fetch all curator notification settings at once
    curator_ids = [curator.telegram_chat_id for curator in curators]

    # Build a list of match conditions for each curator ID
    curator_matches = [match({'telegram_chat_id': curator_id}) for curator_id in curator_ids]

    # Only fetch curator settings if there are curators
    all_curator_settings = []
    if curator_matches:
        # Combine conditions with OR to get all curator settings in one call
        all_curator_settings = Notification.all(formula=OR(*curator_matches))

    curator_settings_map = {setting.telegram_chat_id: setting for setting in all_curator_settings}

    for curator in curators:
        try:
            curator_settings = curator_settings_map[curator.telegram_chat_id]
        except KeyError:
            logging.warning(f"No notification settings found for curator {curator.telegram} ({curator.telegram_chat_id}), skipping.")
            continue
        # check if the current time is equal to the time set in the notify_at field
        if datetime.now().strftime('%H:%M') == curator_settings.notify_at:
            # check if there are no volunteers scheduled for any date between today and the threshold date
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.now().astimezone().tzinfo)
            end_date = start_date + timedelta(days=int(str(curator_settings.date_threshold).split('+')[1]))
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

            for date in (start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)):
                logging.info(f"Checking for volunteers for {date} for {curator.telegram}")
                # Get all schedules for the current date in a single query
                formula = AND(
                    GTE(Field('date'), date.replace(hour=0, minute=0, second=0, microsecond=0)),
                    LTE(Field('date'), date.replace(hour=23, minute=59, second=59, microsecond=999999))
                )
                schedules = Schedule.all(
                    formula=formula,
                    fields=['type']
                )

                buttons = []
                text = ''
                if not schedules:
                    # No volunteers found at all
                    logging.info(f"No volunteers found for {date} for {curator.telegram}, sending notification.")
                    buttons.append([Button.inline(button_curator_notifications_send_all[curator.language], data=f'notifications_send;all;{date.timestamp()}')])
                    text = notifications_no_volunteers_at_all[curator.language].format(format_date_by_language(date, curator.language))
                else:
                    # Check if specific types are missing
                    schedule_types = [s.type for s in schedules]

                    if 'cleaning' not in schedule_types:
                    # No cleaning volunteers found
                        logging.info(f"No cleaning volunteers found for {date} for {curator.telegram}, sending notification.")
                        buttons.append([Button.inline(button_curator_notifications_send_cleaning[curator.language], data=f'notifications_send;cleaning;{date.timestamp()}')])
                        text = notifications_no_cleaning_volunteers[curator.language].format(format_date_by_language(date, curator.language))
                    elif 'medical' not in schedule_types:
                    # No medical volunteers found
                        logging.info(f"No medical volunteers found for {date} for {curator.telegram}, sending notification.")
                        buttons.append([Button.inline(button_curator_notifications_send_medical[curator.language], data=f'notifications_send;medical;{date.timestamp()}')])
                        text = notifications_no_medical_volunteers[curator.language].format(format_date_by_language(date, curator.language))

                if text:
                    buttons.append([Button.inline(button_curator_ignore[curator.language], data='back')])
                    await bot.send_message(curator.telegram_chat_id, text, buttons=buttons)
                    break  # Send only one notification for the closest date and break the loop, delete to notify about all future dates

# send daily medical topic notification at 11:00
@logger
@aiocron.crontab('00 11 * * *') # every day at 11:00
@airtable_context('daily_medical_notification')
async def send_daily_medical_notification():
    global topic_input_entity, medical_topic_id

    # Check if topic settings are available
    settings = Settings.all()
    settings_dict = {setting.key: setting.value for setting in settings}

    if not settings_dict.get('topic_chat_id') or not settings_dict.get('medical_topic_id'):
        logging.error("Topic chat ID or medical topic ID is not set, skipping daily medical notification.")
        return

    medical_topic_id = settings_dict.get('medical_topic_id')

    try:
        marked_topic_chat_id = int('-100'+str(settings_dict.get('topic_chat_id')))
        topic_entity = await bot.get_entity(marked_topic_chat_id)
        topic_input_entity = utils.get_input_channel(utils.get_input_peer(topic_entity))
    except (ValueError, Exception) as err:
        logging.error(f"Error getting topic chat entity for daily medical notification: {err}")
        return

    if not airtable_sterilization_base_id or not sterilization_api:
        logging.error("Sterilization base ID or API not configured, skipping daily medical notification.")
        return

    try:
        # Query cat_flat_fostering table from sterilization base
        table = sterilization_api.table(airtable_sterilization_base_id, 'cat_flat_fostering')

        # Filter by status - match any of the specified statuses
        statuses = ["принята в кд", "ожидает стерилизацию", "готова к выписке", "назначен медуход"]
        status_formulas = [match({'status': status}) for status in statuses]
        formula = OR(*status_formulas)

        # exclude cats with checked is_test field
        formula = AND(formula, match({'is_test': False}))

        # Fetch records with required fields
        records = table.all(
            formula=str(formula),
            fields=['request_id', 'sterilization_date', 'in_date', 'record_id', 'request_record_id',
                    'status', 'room', '💊 med_care', '🦟is_deflead', '💉is_vaccinated', '𓆑is_dewormed', 'required_vaccination']
        )

        # Filter records that need attention (any checkbox unchecked)
        # Group by room: {room: [(request_id_num, entry), ...]}
        cats_by_room = {}
        today = datetime.now().date()

        for record in records:
            fields_data = record.get('fields', {})
            is_deflead = fields_data.get('🦟is_deflead', False)
            is_vaccinated = fields_data.get('💉is_vaccinated', False)
            is_dewormed = fields_data.get('𓆑is_dewormed', False)
            has_med_care = bool(fields_data.get('💊 med_care', False))

            # Check if any of the three checkboxes is unchecked
            if not is_deflead or not is_vaccinated or not is_dewormed or has_med_care:
                # Handle request_id which is a lookup field (might be array or single value)
                request_id_raw = fields_data.get('request_id')
                if isinstance(request_id_raw, list) and len(request_id_raw) > 0:
                    request_id = str(request_id_raw[0])
                elif request_id_raw is not None:
                    request_id = str(request_id_raw)
                else:
                    request_id = 'N/A'

                # Get numeric request_id for sorting
                try:
                    request_id_num = int(request_id) if request_id != 'N/A' else 999999
                except:
                    request_id_num = 999999

                # Get request_record_id for link
                request_record_id_raw = fields_data.get('request_record_id')
                if isinstance(request_record_id_raw, list) and len(request_record_id_raw) > 0:
                    request_record_id = str(request_record_id_raw[0])
                elif request_record_id_raw is not None:
                    request_record_id = str(request_record_id_raw)
                else:
                    request_record_id = None

                # Get record_id for link (might be lookup field or direct field)
                record_id_raw = fields_data.get('record_id')
                if isinstance(record_id_raw, list) and len(record_id_raw) > 0:
                    record_id = str(record_id_raw[0])
                elif record_id_raw is not None:
                    record_id = str(record_id_raw)
                else:
                    record_id = record.get('id')  # fallback to record's own ID

                # Get room (might be lookup field returning array)
                room_raw = fields_data.get('room', '')
                if isinstance(room_raw, list) and len(room_raw) > 0:
                    room = str(room_raw[0])
                elif room_raw:
                    room = str(room_raw)
                else:
                    room = 'Без комнаты'  # Default room name if empty

                # Build emoji string for unchecked fields
                emojis = []
                if has_med_care:
                    emojis.append('💊')
                if not is_deflead:
                    emojis.append('🦟')
                if not is_vaccinated:
                    # required_vaccination field value is 'complex ✔, rabies ❌'
                    required_vaccination = fields_data.get('required_vaccination', '')
                    if required_vaccination:
                        emojis.append('💉' + ('(' + required_vaccination +')'))
                    else:
                        emojis.append('💉')
                if not is_dewormed:
                    emojis.append('𓆑')
                emoji_str = ''.join(emojis)

                # Calculate days in cat flat
                in_date_raw = fields_data.get('in_date')
                sterilization_date_raw = fields_data.get('sterilization_date')

                # Try sterilization_date first, then in_date
                date_obj = parse_airtable_date(sterilization_date_raw) or parse_airtable_date(in_date_raw)

                if date_obj:
                    days = (today - date_obj).days
                    days_text = f"{days} дн в кд"
                else:
                    days_text = f"срок пребывания в кд неизвестен"

                # Format entry with links: {request_id_link} {emojis} {days}, {details_link}
                # Format request_id as link if request_record_id is available
                if request_record_id:
                    request_id_url = f"https://catebi.softr.app/sterilization-request-details?recordId={request_record_id}"
                    request_id_link = f'<a href="{request_id_url}">{request_id}</a>'
                else:
                    request_id_link = request_id

                # Format details link if record_id is available
                if record_id:
                    details_url = f"https://catebi.softr.app/cat-flat-fostering-details?recordId={record_id}"
                    details_link = f'<a href="{details_url}">kk_link</a>'
                else:
                    details_link = 'kk_link'

                entry = f"{request_id_link} {emoji_str} {days_text}, {details_link}"
                
                # Group by room
                if room not in cats_by_room:
                    cats_by_room[room] = []
                cats_by_room[room].append((request_id_num, entry))

        # Sort rooms alphabetically (descending) and entries within each room by request_id (descending)
        sorted_rooms = sorted(cats_by_room.keys(), reverse=True)
        cats_needing_attention = []
        for i, room in enumerate(sorted_rooms):
            # Add room header
            cats_needing_attention.append(f"<u>{room}</u>")
            # Sort entries by request_id_num (descending) and add them
            sorted_entries = sorted(cats_by_room[room], key=lambda x: x[0], reverse=True)
            for _, entry in sorted_entries:
                cats_needing_attention.append(entry)
            
            # Add newline between rooms (but not after the last room)
            if i < len(sorted_rooms) - 1:
                cats_needing_attention.append('')

        # Get today's medical duty volunteer
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.now().astimezone().tzinfo)
        today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=datetime.now().astimezone().tzinfo)

        formula = AND(
            GTE(Field('date'), today_start),
            LTE(Field('date'), today_end),
            match({'type': 'medical'})
        )

        today_schedules = Schedule.all(
            formula=formula,
            fields=['date', 'telegram', 'type']
        )

        duty_info = "❗️на сегодня нет дежурного по медуходу"
        if today_schedules:
            # Get the first medical schedule for today
            schedule = today_schedules[0]
            schedule_date = schedule.date.astimezone(datetime.now().astimezone().tzinfo)
            username = schedule.telegram if schedule.telegram else 'unknown'
            time_str = schedule_date.strftime('%H:%M')
            duty_info = f"дежурный медухода сегодня {username}, в {time_str}"

        # Build and send message
        if cats_needing_attention:
            message = "⚠️ кошки в котодоме без обработки или на медуход\n\n" + "\n".join(cats_needing_attention) + f"\n\n{duty_info}"
        else:
            message = "🎉 все кошки в котодоме обработаны и не нуждаются в медуходе"

        await bot.send_message(
            topic_input_entity,
            message,
            reply_to=medical_topic_id,
            parse_mode='html',
            link_preview=False
        )

        logging.info(f"Daily medical notification sent successfully. Cats needing attention: {len(cats_needing_attention)}")

    except Exception as err:
        logging.error(f"Error sending daily medical notification: {err}", exc_info=True)

# Helper function to fetch and normalize cat flat records
@airtable_context('fetch_cat_flat_records')
async def fetch_cat_flat_records():
    """Fetch cat flat records and return normalized data for each cat."""
    if not airtable_sterilization_base_id or not sterilization_api:
        logging.error("Sterilization base ID or API not configured.")
        return []

    try:
        # Query cat_flat_fostering table from sterilization base
        table = sterilization_api.table(airtable_sterilization_base_id, 'cat_flat_fostering')

        # Filter by status - match any of the specified statuses
        statuses = ["принята в кд", "ожидает стерилизацию", "готова к выписке", "назначен медуход"]
        status_formulas = [match({'status': status}) for status in statuses]
        formula = OR(*status_formulas)

        # exclude cats with checked is_test field
        formula = AND(formula, match({'is_test': False}))

        # Fetch records with required fields
        records = table.all(
            formula=str(formula),
            fields=['request_id', 'sterilization_date', 'in_date', 'record_id', 'request_record_id', 'notes_kk', 'requestor_name',
                    'status', 'room', '💊 med_care', '🦟is_deflead', '💉is_vaccinated', '𓆑is_dewormed', 'required_vaccination']
        )

        normalized_cats = []
        for record in records:
            fields_data = record.get('fields', {})
            
            # Get record_id (use record's own ID as fallback)
            record_id_raw = fields_data.get('record_id')
            if isinstance(record_id_raw, list) and len(record_id_raw) > 0:
                record_id = str(record_id_raw[0])
            elif record_id_raw is not None:
                record_id = str(record_id_raw)
            else:
                record_id = record.get('id')  # fallback to record's own ID

            # Get status
            status = fields_data.get('status', '')

            # Get medical fields
            is_deflead = fields_data.get('🦟is_deflead', False)
            is_vaccinated = fields_data.get('💉is_vaccinated', False)
            is_dewormed = fields_data.get('𓆑is_dewormed', False)

            # Handle request_id
            request_id_raw = fields_data.get('request_id')
            if isinstance(request_id_raw, list) and len(request_id_raw) > 0:
                request_id = str(request_id_raw[0])
            elif request_id_raw is not None:
                request_id = str(request_id_raw)
            else:
                request_id = 'N/A'

            # Get request_record_id for link
            request_record_id_raw = fields_data.get('request_record_id')
            if isinstance(request_record_id_raw, list) and len(request_record_id_raw) > 0:
                request_record_id = str(request_record_id_raw[0])
            elif request_record_id_raw is not None:
                request_record_id = str(request_record_id_raw)
            else:
                request_record_id = None

            # Get room
            room_raw = fields_data.get('room', '')
            if isinstance(room_raw, list) and len(room_raw) > 0:
                room = str(room_raw[0])
            elif room_raw:
                room = str(room_raw)
            else:
                room = 'Без комнаты'

            # Get notes_kk
            notes_kk_raw = fields_data.get('notes_kk', '')
            if isinstance(notes_kk_raw, list) and len(notes_kk_raw) > 0:
                notes_kk = str(notes_kk_raw[0])
            elif notes_kk_raw:
                notes_kk = str(notes_kk_raw)
            else:
                notes_kk = ''

            # Get requestor_name (lookup field)
            requestor_name_raw = fields_data.get('requestor_name', '')
            if isinstance(requestor_name_raw, list) and len(requestor_name_raw) > 0:
                requestor_name = str(requestor_name_raw[0])
            elif requestor_name_raw:
                requestor_name = str(requestor_name_raw)
            else:
                requestor_name = ''

            normalized_cats.append({
                'record_id': record_id,
                'status': status,
                'is_deflead': is_deflead,
                'is_vaccinated': is_vaccinated,
                'is_dewormed': is_dewormed,
                'request_id': request_id,
                'request_record_id': request_record_id,
                'room': room,
                'notes_kk': notes_kk,
                'requestor_name': requestor_name,
                'record': record,  # Keep full record for formatting
                'fields_data': fields_data  # Keep fields_data for formatting
            })

        return normalized_cats
    except Exception as err:
        logging.error(f"Error fetching cat flat records: {err}", exc_info=True)
        return []

# send daily cat flat status notification at 10:00
@logger
@aiocron.crontab('00 10 * * *') # every day at 09:00
@airtable_context('daily_cat_flat_status_notification')
async def send_daily_cat_flat_status_notification():
    global topic_input_entity, process_notification_topic_id

    # Check if topic settings are available
    settings = Settings.all()
    settings_dict = {setting.key: setting.value for setting in settings}

    if not settings_dict.get('process_notification_topic_id'):
        logging.error("Process notification topic ID is not set, skipping daily cat flat status notification.")
        return

    process_notification_topic_id = settings_dict.get('process_notification_topic_id')

    try:
        marked_topic_chat_id = int('-100'+str(settings_dict.get('topic_chat_id')))
        topic_entity = await bot.get_entity(marked_topic_chat_id)
        topic_input_entity = utils.get_input_channel(utils.get_input_peer(topic_entity))
    except (ValueError, Exception) as err:
        logging.error(f"Error getting topic chat entity for daily cat flat status notification: {err}")
        return

    try:
        # Fetch normalized cat records
        normalized_cats = await fetch_cat_flat_records()
        
        if not normalized_cats:
            logging.warning("No cat records found for status notification.")
            return

        # Process ALL records (no filtering)
        # Group by room: {room: [(date_obj, days, entry), ...]}
        cats_by_room = {}
        today = datetime.now().date()
        
        # Prepare state data for saving to JSON
        state_data = {
            'timestamp': datetime.now().isoformat(),
            'cats': {}
        }

        for cat_data in normalized_cats:
            fields_data = cat_data['fields_data']
            record = cat_data['record']
            is_deflead = cat_data['is_deflead']
            is_vaccinated = cat_data['is_vaccinated']
            is_dewormed = cat_data['is_dewormed']
            has_med_care = bool(fields_data.get('💊 med_care', False))
            request_id = cat_data['request_id']
            request_record_id = cat_data['request_record_id']
            record_id = cat_data['record_id']
            room = cat_data['room']
            status = cat_data['status']
            notes_kk = cat_data.get('notes_kk', '')
            requestor_name = cat_data.get('requestor_name', '')

            # Get dates for state saving and calculations
            in_date_raw = fields_data.get('in_date')
            sterilization_date_raw = fields_data.get('sterilization_date')

            # Save state data for JSON
            state_data['cats'][record_id] = {
                'record_id': record_id,
                'status': status,
                'is_deflead': is_deflead,
                'is_vaccinated': is_vaccinated,
                'is_dewormed': is_dewormed,
                'request_id': request_id,
                'request_record_id': request_record_id,
                'room': room,
                'notes_kk': notes_kk,
                'requestor_name': requestor_name,
                'in_date': str(in_date_raw) if in_date_raw else '',
                'sterilization_date': str(sterilization_date_raw) if sterilization_date_raw else ''
            }

            # Build emoji string for unchecked fields (for display in middle)
            emojis = []
            if not is_deflead:
                emojis.append('🦟')
            if not is_vaccinated:
                # required_vaccination field value is 'complex ✔, rabies ❌'
                required_vaccination = fields_data.get('required_vaccination', '')
                if required_vaccination:
                    emojis.append('💉' + ('(' + required_vaccination +')'))
                else:
                    emojis.append('💉')
            if not is_dewormed:
                emojis.append('𓆑')
            emoji_str = ''.join(emojis)
            
            # Track end emojis separately
            end_emojis = []
            if has_med_care:
                end_emojis.append('💊')
            if not is_deflead or not is_vaccinated or not is_dewormed:
                end_emojis.append('💉')
            end_emoji_str = ''.join(end_emojis)

            # Calculate days in cat flat

            # Try sterilization_date first, then in_date
            date_obj = parse_airtable_date(sterilization_date_raw) or parse_airtable_date(in_date_raw)

            if date_obj:
                days = (today - date_obj).days
                days_prefix = f"{days} дн в "
            else:
                days = 999999  # Use large number for sorting if date is unknown
                days_prefix = "срок пребывания в "

            # Determine emoji based on days count
            if days < 7:
                status_emoji = '🟢'
            elif days < 30:
                status_emoji = '🟡'
            else:
                status_emoji = '🔴'

            # Format entry with links: {status_emoji} {request_id_link} {emojis} {days}, {details_link}
            # Format request_id as link if request_record_id is available
            if request_record_id:
                request_id_url = f"https://catebi.softr.app/sterilization-request-details?recordId={request_record_id}"
                request_id_link = f'<a href="{request_id_url}">{request_id}</a>'
            else:
                request_id_link = request_id

            # Format details link if record_id is available - use "кд" as link text
            if record_id:
                details_url = f"https://catebi.softr.app/cat-flat-fostering-details?recordId={record_id}"
                kk_link = f'<a href="{details_url}">кд</a>'
            else:
                kk_link = 'кд'

            # Format: {status_emoji} {request_id_link} (requestor_name), <i>status</i>, {days_prefix}{kk_link} {end_emojis}
            requestor_part = f" ({requestor_name})" if requestor_name else ""
            entry = f"{status_emoji} {request_id_link}{requestor_part}, <i>{status}</i>, {days_prefix}{kk_link}{' ' + end_emoji_str if end_emoji_str else ''}"

            # trim notes_kk 
            notes_kk = notes_kk.strip() if notes_kk else ''

            # add notes_kk if it exists to the end of the entry            
            if notes_kk:
                entry += f" ({notes_kk})"
            
            # Group by room, storing date_obj and days for sorting
            # Use max date for records without dates so they sort to the end
            if room not in cats_by_room:
                cats_by_room[room] = []
            cats_by_room[room].append((date_obj if date_obj else datetime.max.date(), days, entry))

        # Room capacities
        room_capacities = {
            'K1': 10,
            'K2': 10,
            'Hall': 4
        }
        total_capacity = sum(room_capacities.values())  # 24

        # Sort rooms alphabetically (ascending) and entries within each room by date (ascending - older first)
        sorted_rooms = sorted(cats_by_room.keys(), reverse=False)
        all_cats = []
        total_cats_count = 0
        for i, room in enumerate(sorted_rooms):
            room_count = len(cats_by_room[room])
            total_cats_count += room_count
            
            # Calculate room percentage
            room_capacity = room_capacities.get(room, 0)
            if room_capacity > 0:
                room_percent = int((room_count / room_capacity) * 100)
                room_header = f"<u>{room}</u> ({room_count}/{room_capacity}, {room_percent}%🪫)"
            else:
                # Room not in capacity list (e.g., "Без комнаты")
                room_header = f"<u>{room}</u> ({room_count})"
            
            # Add room header
            all_cats.append(room_header)
            # Sort entries by date_obj (ascending - older first), then by days (ascending)
            sorted_entries = sorted(cats_by_room[room], key=lambda x: (x[0], x[1]))
            for _, _, entry in sorted_entries:
                all_cats.append(entry)
            
            # Add newline between rooms (but not after the last room)
            if i < len(sorted_rooms) - 1:
                all_cats.append('')

        # Calculate overall percentage
        overall_percent = int((total_cats_count / total_capacity) * 100) if total_capacity > 0 else 0

        # Build and send message with cat count and percentage
        if all_cats:
            message = f"📋 {total_cats_count} кошек в котодоме ({total_cats_count}/{total_capacity}, {overall_percent}%🪫)\n\n" + "\n".join(all_cats)
        else:
            message = "📋 нет кошек в котодоме (0%)"

        await bot.send_message(
            topic_input_entity,
            message,
            reply_to=process_notification_topic_id,
            parse_mode='html',
            link_preview=False
        )

        # Save state to JSON file for comparison in changes notification
        try:
            state_file_path = os.path.join(os.path.dirname(__file__), 'cat_flat_state.json')
            with open(state_file_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            logging.info(f"Cat flat state saved to {state_file_path}. Total cats: {len(state_data['cats'])}")
        except Exception as save_err:
            logging.error(f"Error saving cat flat state to JSON: {save_err}", exc_info=True)

        logging.info(f"Daily cat flat status notification sent successfully. Total cats: {len([c for c in all_cats if not c.startswith('<u>') and c])}")

    except Exception as err:
        logging.error(f"Error sending daily cat flat status notification: {err}", exc_info=True)

# Helper function to format cat entry with full details
def format_cat_entry_full(cat_data_dict, full_cat_data=None):
    """Format a cat entry with request_id, requestor_name, status, days, and кд link."""
    # Get data from cat_data_dict or full_cat_data
    if full_cat_data:
        request_id = full_cat_data.get('request_id', cat_data_dict.get('request_id', 'N/A'))
        request_record_id = full_cat_data.get('request_record_id', cat_data_dict.get('request_record_id'))
        record_id = full_cat_data.get('record_id', cat_data_dict.get('record_id'))
        requestor_name = full_cat_data.get('requestor_name', '')
        status = full_cat_data.get('status', cat_data_dict.get('status', ''))
        notes_kk = full_cat_data.get('notes_kk', '')
        fields_data = full_cat_data.get('fields_data', {})
        in_date_raw = fields_data.get('in_date') if fields_data else None
        sterilization_date_raw = fields_data.get('sterilization_date') if fields_data else None
    else:
        # Try to get from cat_data_dict (for departed cats from JSON state)
        request_id = cat_data_dict.get('request_id', 'N/A')
        request_record_id = cat_data_dict.get('request_record_id')
        record_id = cat_data_dict.get('record_id')
        requestor_name = cat_data_dict.get('requestor_name', '')
        status = cat_data_dict.get('status', '')
        notes_kk = cat_data_dict.get('notes_kk', '')
        # Get dates from saved state (they're stored as strings)
        in_date_raw = cat_data_dict.get('in_date') or None
        sterilization_date_raw = cat_data_dict.get('sterilization_date') or None
    
    # Calculate days
    today = datetime.now().date()
    date_obj = parse_airtable_date(sterilization_date_raw) or parse_airtable_date(in_date_raw)
    
    if date_obj:
        days = (today - date_obj).days
        days_text = f"{days} дн в "
    else:
        days_text = "срок пребывания в "
    
    # Format request_id (no link, just text)
    request_id_text = str(request_id)
    
    # Format requestor_name
    requestor_part = f" ({requestor_name})" if requestor_name else ""
    
    # Format кд link
    if record_id:
        details_url = f"https://catebi.softr.app/cat-flat-fostering-details?recordId={record_id}"
        kd_link = f'<a href="{details_url}">кд</a>'
    else:
        kd_link = 'кд'
    
    # Format notes_kk
    notes_part = f" ({notes_kk.strip()})" if notes_kk and notes_kk.strip() else ""
    
    # Format: request_id (requestor_name), <i>status</i>, days in кд (notes_kk)
    return f"{request_id_text}{requestor_part}, <i>{status}</i>, {days_text}{kd_link}{notes_part}"

# send daily cat flat changes notification at 22:00
@logger
@aiocron.crontab('00 22 * * *') # every day at 22:00 (10 PM)
@airtable_context('daily_cat_flat_changes_notification')
async def send_daily_cat_flat_changes_notification():
    global topic_input_entity, process_notification_topic_id

    # Check if topic settings are available
    settings = Settings.all()
    settings_dict = {setting.key: setting.value for setting in settings}

    if not settings_dict.get('process_notification_topic_id'):
        logging.error("Process notification topic ID is not set, skipping daily cat flat changes notification.")
        return

    process_notification_topic_id = settings_dict.get('process_notification_topic_id')

    try:
        marked_topic_chat_id = int('-100'+str(settings_dict.get('topic_chat_id')))
        topic_entity = await bot.get_entity(marked_topic_chat_id)
        topic_input_entity = utils.get_input_channel(utils.get_input_peer(topic_entity))
    except (ValueError, Exception) as err:
        logging.error(f"Error getting topic chat entity for daily cat flat changes notification: {err}")
        return

    try:
        # Load previous state from JSON
        state_file_path = os.path.join(os.path.dirname(__file__), 'cat_flat_state.json')
        try:
            with open(state_file_path, 'r', encoding='utf-8') as f:
                prev_state = json.load(f)
            prev_cats = prev_state.get('cats', {})
            prev_timestamp = prev_state.get('timestamp', 'unknown')
            logging.info(f"Loaded previous state from {prev_timestamp}. Total cats: {len(prev_cats)}")
        except FileNotFoundError:
            logging.warning(f"Previous state file not found at {state_file_path}. This may be the first run.")
            await bot.send_message(
                topic_input_entity,
                "ℹ️ Изменения не могут быть определены: предыдущее состояние не найдено. Это может быть первый запуск.",
                reply_to=process_notification_topic_id,
                parse_mode='html',
                link_preview=False
            )
            return
        except json.JSONDecodeError as json_err:
            logging.error(f"Error parsing previous state JSON: {json_err}")
            await bot.send_message(
                topic_input_entity,
                "❌ Ошибка при чтении предыдущего состояния. Проверьте файл cat_flat_state.json.",
                reply_to=process_notification_topic_id,
                parse_mode='html',
                link_preview=False
            )
            return

        # Fetch current state
        current_normalized_cats = await fetch_cat_flat_records()
        if not current_normalized_cats:
            logging.warning("No current cat records found for changes notification.")
            return

        # Build current state dict
        current_cats = {}
        for cat_data in current_normalized_cats:
            record_id = cat_data['record_id']
            current_cats[record_id] = {
                'record_id': record_id,
                'status': cat_data['status'],
                'is_deflead': cat_data['is_deflead'],
                'is_vaccinated': cat_data['is_vaccinated'],
                'is_dewormed': cat_data['is_dewormed'],
                'request_id': cat_data['request_id'],
                'request_record_id': cat_data['request_record_id'],
                'room': cat_data['room'],
                'full_cat_data': cat_data  # Keep full normalized data for formatting
            }

        # Compare and categorize changes
        new_cats = []  # In current, not in previous
        departed_cats = []  # In previous, not in current
        status_changes = {}  # {('prev_status', 'new_status'): [cat_entries]}
        medical_changes = []  # Cats with medical field changes

        # Find new cats
        for record_id, cat_data in current_cats.items():
            if record_id not in prev_cats:
                new_cats.append(cat_data)

        # Find departed cats and check for changes
        # For departed cats (present in prev_state, absent in current filtered set),
        # fetch their *current* status and notes_kk from Airtable in batches.
        departed_ids = [rid for rid in prev_cats.keys() if rid not in current_cats]
        departed_current_map = {}
        if departed_ids and airtable_sterilization_base_id and sterilization_api:
            try:
                table_cf = sterilization_api.table(airtable_sterilization_base_id, 'cat_flat_fostering')
                # Keep chunks small to avoid Airtable formula length limits
                chunk_size = 25
                for i in range(0, len(departed_ids), chunk_size):
                    chunk = departed_ids[i:i + chunk_size]
                    # Airtable formula supports RECORD_ID()
                    formula_str = "OR(" + ",".join([f"RECORD_ID()='{rid}'" for rid in chunk]) + ")"
                    records = table_cf.all(
                        formula=formula_str,
                        fields=['status', 'notes_kk']
                    )
                    for rec in records:
                        rid = rec.get('id')
                        if not rid:
                            continue
                        f = rec.get('fields', {})
                        status_val = f.get('status', '')
                        notes_raw = f.get('notes_kk', '')
                        if isinstance(notes_raw, list) and len(notes_raw) > 0:
                            notes_val = str(notes_raw[0])
                        elif notes_raw:
                            notes_val = str(notes_raw)
                        else:
                            notes_val = ''
                        departed_current_map[rid] = {
                            'status': status_val,
                            'notes_kk': notes_val,
                        }
            except Exception as fetch_err:
                logging.warning(f"Could not batch fetch departed cats status/notes: {fetch_err}")

        for record_id, prev_cat in prev_cats.items():
            if record_id not in current_cats:
                # overwrite with actual current values if available
                cur = departed_current_map.get(record_id)
                if cur:
                    prev_cat['status'] = cur.get('status', prev_cat.get('status', ''))
                    prev_cat['notes_kk'] = cur.get('notes_kk', prev_cat.get('notes_kk', ''))
                departed_cats.append(prev_cat)
            else:
                curr_cat = current_cats[record_id]
                
                # Check status change
                if prev_cat['status'] != curr_cat['status']:
                    status_key = (prev_cat['status'], curr_cat['status'])
                    if status_key not in status_changes:
                        status_changes[status_key] = []
                    status_changes[status_key].append(curr_cat)
                
                # Check medical field changes
                medical_changed = False
                medical_changes_list = []
                if prev_cat['is_deflead'] != curr_cat['is_deflead']:
                    medical_changed = True
                    medical_changes_list.append("🦟☑️")
                if prev_cat['is_vaccinated'] != curr_cat['is_vaccinated']:
                    medical_changed = True
                    medical_changes_list.append("💉☑️")
                if prev_cat['is_dewormed'] != curr_cat['is_dewormed']:
                    medical_changed = True
                    medical_changes_list.append("𓆑☑️")
                
                if medical_changed:
                    medical_changes.append({
                        'cat': curr_cat,
                        'changes': medical_changes_list
                    })

        # Build message
        message_parts = []
        
        # New cats
        if new_cats:
            message_parts.append("🆕 <b>появились в котоквартире:</b>")
            for cat_data_dict in new_cats:
                full_cat_data = cat_data_dict.get('full_cat_data')
                entry = format_cat_entry_full(cat_data_dict, full_cat_data)
                message_parts.append(entry)
            message_parts.append("")

        # Departed cats
        if departed_cats:
            message_parts.append("🚙 <b>выехали из котоквартиры:</b>")
            for prev_cat in departed_cats:
                # For departed cats, we need to reconstruct the format from prev_cat
                # prev_cat doesn't have full_cat_data, so we'll use what we have
                entry = format_cat_entry_full(prev_cat)
                message_parts.append(entry)
            message_parts.append("")

        # Status changes
        if status_changes:
            message_parts.append("🔄 <b>изменения статуса:</b>")
            for (prev_status, new_status), cats in status_changes.items():
                message_parts.append(f"{prev_status} -> {new_status}:")
                for cat_data_dict in cats:
                    full_cat_data = cat_data_dict.get('full_cat_data')
                    entry = format_cat_entry_full(cat_data_dict, full_cat_data)
                    message_parts.append(entry)
            message_parts.append("")

        # Medical changes
        if medical_changes:
            message_parts.append("💊 <b>медобработка:</b>")
            for med_change in medical_changes:
                cat_data_dict = med_change['cat']
                full_cat_data = cat_data_dict.get('full_cat_data')
                entry = format_cat_entry_full(cat_data_dict, full_cat_data)
                # Format changes emojis: join with no space, then add space before entry
                changes_str = "".join(med_change['changes'])
                message_parts.append(f"{changes_str} {entry}")
            message_parts.append("")

        # Send message
        if message_parts:
            message = "📊 изменения в котоквартире\n\n" + "\n".join(message_parts).strip()
        else:
            message = "✅ изменений не обнаружено"

        await bot.send_message(
            topic_input_entity,
            message,
            reply_to=process_notification_topic_id,
            parse_mode='html',
            link_preview=False
        )

        logging.info(f"Daily cat flat changes notification sent successfully. New: {len(new_cats)}, Departed: {len(departed_cats)}, Status changes: {len(status_changes)}, Medical changes: {len(medical_changes)}")

    except Exception as err:
        logging.error(f"Error sending daily cat flat changes notification: {err}", exc_info=True)

# handle custom notification text setting
custom_text_setting = {}
@bot.on(events.NewMessage(func=lambda e: e.is_private and e.sender.id in custom_text_setting)) # Only in private chat
@logger
async def custom_notifications_handler(event):
    # prepare local variables
    admin = None
    custom_text = None
    prompt = None
    pre_curly = None
    post_curly = None

    logging.info(f"Custom text setting: {event.sender.id}, {event.message.message}")

    admin = Notification.first(formula=match({'telegram_chat_id': event.sender.id}))

    custom_text = str(event.message.message)
    if custom_text.startswith('/'):
        await event.respond(error_custom_text[admin.volunteer.language])
        raise events.StopPropagation

    if '{' in custom_text and '}' in custom_text:
        # replace everything within curly braces with empty string
        pre_curly, _, _ = custom_text.partition('{')
        _, _, post_curly = custom_text.partition('}')
        custom_text = pre_curly + r'{}' + post_curly

    if custom_text_setting[event.sender.id]['type'] == 'cleaning':
        admin.custom_text_cleaning = custom_text
    elif custom_text_setting[event.sender.id]['type'] == 'medical':
        admin.custom_text_medical = custom_text
    admin.save()

    prompt = custom_text_setting[event.sender.id]['prompt']

    await prompt.edit(prompt.message, buttons=None) # remove buttons from the prompt to avoid multiple clicks
    await event.respond(notifications_settings_text_success[admin.volunteer.language], buttons=[Button.inline(button_back[admin.volunteer.language], data='notifications;;')])

    custom_text_setting.pop(event.sender.id)

# region Commands

@bot.on(events.NewMessage(pattern='/start', func=lambda e: e.is_private)) # Only in private chat
@logger
@airtable_context('start_handler')
async def start_handler(event, check_user: bool = False, language: str = 'en'):
    # disable start command for supergroup chats
    if not event.is_private:
        return

    # show language selection menu on first launch
    if not check_user:
        buttons = [
            [Button.inline(languages[lang], data=f'language:{lang}')] for lang in languages
        ]
        await event.edit(language_selection[language], buttons=buttons)
        return

    # check if user exists in Airtable
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))

    if not user:
        # show warning that the user is not an existing volunteer
        await event.edit(error_not_registered[language])
        return

    else:
        # set user's language
        user.language = language
        user.save()

    await schedule_handler(event, language, update=True)

@bot.on(events.NewMessage(pattern='/help'))
@logger
@airtable_context('help_handler')
async def help_handler(event):
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    language = user.language if user else 'en'
    version_info = f"🤖 Bot Version: `{version}`"  # Add version info here

    if not user:
        # show warning that the user is not an existing volunteer
        await event.respond(f"{error_not_registered[language]}\n\n{version_info}")
        return

    await event.respond(f"{help_message[language]}\n\n{version_info}")

@bot.on(events.NewMessage(pattern='/settings', func=lambda e: e.is_private)) # Only in private chat
@logger
async def settings_handler(event, edit: bool = False):
    # read current settings
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    if not user:
        await event.respond(error_not_registered[user.language])
        return

    current_settings = {
        "language": user.language,
        "view": user.schedule_view
    }

    buttons = [
        [Button.inline(button_change_language[current_settings['language']], data='change_language')],
        [Button.inline(button_change_view[current_settings['language']], data=f'change_view;{current_settings['view']}')]
    ]

    if not edit:
        await event.respond(settings_overview[current_settings['language']].format(
            languages[current_settings['language']],
            settings_view[current_settings['view']][current_settings['language']]
        ), buttons=buttons)
        return

    await event.edit(settings_overview[current_settings['language']].format(
        languages[current_settings['language']],
        settings_view[current_settings['view']][current_settings['language']]
    ), buttons=buttons)

@bot.on(events.NewMessage(pattern='/set_cleaning_topic|/set_medical_topic|/set_steril_cat_topic'))
@logger
async def set_topic_handler(event):
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    if not user:
        await event.respond(error_not_registered[user.language])
        return

    if 'kk_admin_curator' not in user.duties:
        await event.respond(error_not_admin[user.language])
        return

    # set topic type
    topic_type = 'cleaning' if event.pattern_match.group(0) == '/set_cleaning_topic' else 'medical' if event.pattern_match.group(0) == '/set_medical_topic' else 'steril_cat'
    settings_topic_chat_id = Settings.first(formula=match({'key': 'topic_chat_id'}))
    if not settings_topic_chat_id.value: # check if topic chat id is set
        settings_topic_chat_id.value = event.chat.id
        settings_topic_chat_id.save()

    settings_topic_id = Settings.first(formula=match({'key': f'{topic_type}_topic_id'})) # save new topic id
    settings_topic_id.value = event.message.reply_to_msg_id
    settings_topic_id.save()

    await bot.send_message(event.sender.id, f"{topic_type.capitalize()} topic set successfully.")

# region Menu

@bot.on(events.NewMessage(pattern='/schedule'))
@logger
@airtable_context('schedule_handler')
async def schedule_handler(event, language: str = 'en', update: bool = False, view: str = 'today'):
    global today_volunteers_list, dates_list

    today = datetime.now().date().strftime('%d.%m')
    # check if user exists in Airtable
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    if not user:
        # show warning that the user is not an existing volunteer
        await event.respond(error_not_registered[language])
        return

    # if not in private chat just send general schedule
    if not event.is_private:
        await event.reply(general_schedule[language].format( # reply, to handle topics correctly
            today,
            ', '.join(today_volunteers_list) if today_volunteers_list else '😿',
            '\n'.join(dates_list)
        ))
        return

    language = user.language if user else 'en'
    view = user.schedule_view
    duties_set = []
    if 'kk_cleaning' in user.duties:
        duties_set.append('cln')
    if 'kk_medical' in user.duties:
        duties_set.append('med')
    if 'steril_cat_in_out' in user.duties:
        duties_set.append('steril_acceptance')
        duties_set.append('steril_release')

    if not duties_set:
        duties_set = 'none'
    else:
        duties_set = '+'.join(duties_set)

    admin_flag = True if 'kk_admin_curator' in user.duties else False

    buttons = [
        [Button.inline(button_new_schedule[language], data=f'new_schedule;{duties_set}')],
        [Button.inline(button_my_schedule[language], data=f'my_schedule')]
    ]

    if view == 'today':
        buttons.append([Button.inline(button_general_schedule[language], data=f'general_schedule')]) # only show general schedule button in today view

    if admin_flag:
        buttons.append([Button.inline(button_notifications[language], data='notifications;;')])
        buttons.append([Button.inline(button_notifications_steril[language], data='notifications_steril;;')])

    if update:
        await event.edit(
            main_menu_header[language]+'\n\n'+(
                todays_volunteers[language].format(today, ', '.join(today_volunteers_list) if today_volunteers_list else '😿')
            ) if view == 'today' else \
                general_schedule[language].format(today, ', '.join(today_volunteers_list) if today_volunteers_list else '😿', '\n'.join(dates_list)), buttons=buttons)
        return

    await event.respond(main_menu_header[language]+'\n\n'+(
        todays_volunteers[language].format(today, ', '.join(today_volunteers_list) if today_volunteers_list else '😿')
    ) if view == 'today' else \
        general_schedule[language].format(today, ', '.join(today_volunteers_list) if today_volunteers_list else '😿', '\n'.join(dates_list)), buttons=buttons)

# region Buttons
@bot.on(events.CallbackQuery())
@logger
@airtable_context('callback_handler')
async def callback_handler(event):
    global scheduled_dates, today_volunteers_list, dates_list, custom_text_setting, topic_input_entity, cleaning_topic_id, medical_topic_id, steril_cat_topic_id, steril_notification_message

    data = str(event.data.decode("utf-8"))
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    today = datetime.now().date().strftime('%d.%m')

    # Change user's language
    if data.startswith('language'):
        _, lang = data.split(':')
        # save user's language to Airtable
        await start_handler(event, check_user=True, language=lang)
        return

    language = user.language

    # New scheduled date
    if data.startswith('new_schedule'):
        # ask for the type of schedule if duty_switch is 3 (both duties are assigned)
        if data.split(';')[1] == 'none':
            await event.edit(error_no_duties[language], buttons=[Button.inline(button_back[language], data='back')])
            return
        elif len(data.split(';')[1].split('+')) > 1:
            buttons = []
            duties = data.split(';')[1].split('+')
            if 'cln' in duties:
                buttons.append([Button.inline(button_type_cleaning[language], data='new_schedule;cleaning')])
            if 'med' in duties:
                buttons.append([Button.inline(button_type_medical[language], data='new_schedule;medical')])
            if 'steril_acceptance' in duties:
                buttons.append([Button.inline(button_type_steril_acceptance[language], data='new_schedule;steril_acceptance')])
            if 'steril_release' in duties:
                buttons.append([Button.inline(button_type_steril_release[language], data='new_schedule;steril_release')])
            buttons.append([Button.inline(button_back[language], data='back')])
            await event.edit(new_schedule_type_prompt[language], buttons=buttons)
            return

        type = data.split(';')[1]
        if type not in ['cleaning', 'medical', 'steril_acceptance', 'steril_release']:
            if type == 'cln':
                type = 'cleaning'
            elif type == 'med':
                type = 'medical'
            elif type == 'steril_acceptance':
                type = 'steril_acceptance'
            elif type == 'steril_release':
                type = 'steril_release'


        # prepare a list of available dates, from today to 2 weeks in advance
        available_dates = {}
        for i in range(14):
            date = datetime.now().date() + timedelta(days=i)
            available_dates[date] = {}
            available_dates[date]['cleaning'] = 0
            available_dates[date]['medical'] = 0
            available_dates[date]['steril_release'] = 0
            available_dates[date]['steril_acceptance'] = 0

        logging.info(f"Available dates: {available_dates}")

        # check if the date is already scheduled by two volunteers, remove it from the list
        scheduled_dates = Schedule.all(fields=['date', 'type'], formula=match({'date': ('>=', datetime.now().date())}), sort=['date'])
        for entry in scheduled_dates:
            entry.date = entry.date.astimezone(datetime.now().astimezone().tzinfo) # convert date to local timezone
            logging.info(f"Scheduled date: {entry.date.date()}, type: {entry.type}")
            if entry.date.date() in available_dates:
                available_dates[entry.date.date()][entry.type] += 1

        for date in available_dates.copy(): # copy the list to avoid RuntimeError
            if (available_dates[date][type] == 2 and type == 'cleaning') or (available_dates[date][type] == 1 and type == 'medical'):
                available_dates.pop(date)

        # check if the date is already scheduled by the user, remove it from the list
        user_scheduled_dates = Schedule.all(fields=['date', 'type'], formula=match({'telegram_chat_id': event.sender.id}))
        for date in user_scheduled_dates:
            date.date = date.date.astimezone(datetime.now().astimezone().tzinfo) # convert date to local timezone
            if date.date.date() in available_dates and date.type == type:
                available_dates.pop(date.date.date())

        # show a list of available dates
        buttons = [
            [Button.inline(f"{format_date_by_language(date, language)} {'1️⃣' if available_dates[date]['cleaning'] == 1 else '2️⃣' if available_dates[date]['cleaning'] == 2 else '🆓'}",
                           data=f'add_schedule;{date};;{type}' if type == 'steril_acceptance' else f'set_schedule_time;{date};{type}')] for date in available_dates
        ]
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(new_schedule_prompt[language].format(
                                button_type_cleaning[language] if type == 'cleaning' else
                                button_type_medical[language] if type == 'medical' else
                                button_type_steril_acceptance[language] if type == 'steril_acceptance' else
                                button_type_steril_release[language]
                            ),
                            buttons=buttons
                        )

    # Ask for the time of the scheduled date
    if data.startswith('set_schedule_time') and data.split(';')[2] not in ['steril_acceptance']:
        if len(data.split(';')) < 4:
            _, date, type = data.split(';')
            extra = ''
        else:
            _, date, type, extra = data.split(';')

        date = datetime.strptime(date, '%Y-%m-%d').date()
        # Get current time
        current_time = datetime.now()

        # Determine the starting hour (next hour if today, 0 otherwise)
        start_hour = current_time.hour + 1 if date == current_time.date() else 0

        # Create buttons for available hours
        buttons = []
        for j in range(0, 24, 4):
            row = []
            for i in range(j, min(j + 4, 24)):
                if i >= start_hour:
                    row.append(Button.inline(f"{i:02d}:00", data=f'add_schedule;{date};{i:02d}:00;{type};{extra}'))
            if row:  # Only add non-empty rows
                buttons.append(row)
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(set_schedule_time_prompt[language].format(format_date_by_language(date, language)), buttons=buttons)

    # Write a new scheduled date to Airtable
    if data.startswith('add_schedule'):
        # Show loading state while saving to Airtable
        await show_loading_state(event, language)

        if len(data.split(';')) < 5:
            _, date, time, type = data.split(';')
            extra = ''
        else:
            _, date, time, type, extra = data.split(';')
        if time == '':
            time = '00:00'  # default time if not set
        date = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M').astimezone(datetime.now().astimezone().tzinfo) # convert date to local timezone
        # add a new record to the Schedule table
        Schedule(
            telegram_chat_id=event.sender.id,
            date=date,
            telegram='@'+str(event.sender.username).lower(),
            volunteer=user,
            type=type
        ).save()
        await update_volunteers('add_schedule')
        if type == 'steril_acceptance':
            # If steril acceptance, send a special message
            await event.edit(
                add_schedule_success_steril_acceptance[language].format(
                    button_type_steril_acceptance[language],
                    format_date_by_language(date, language)
                ),
                buttons=[Button.inline(button_back[language], data='back')]
            )

            if not topic_input_entity:
                logging.error("Topic chat ID is not set, please set it in the settings.")
                return

            await bot.send_message(
                topic_input_entity,
                add_schedule_topic_steril_acceptance_message.format(
                    '😸⬇️',
                    user.telegram,
                    'сегодня' if date == datetime.now().date() else 'завтра' if date == datetime.now().date() + timedelta(days=1) else format_date_by_language(date, 'ru'),
                ),
                reply_to=steril_cat_topic_id
            )
            return

        await event.edit(
            add_schedule_success[language].format(
                button_type_cleaning[language] if type == 'cleaning' \
                else button_type_medical[language] if type == 'medical' \
                else button_type_steril_release[language],
                format_date_by_language(date, language),
                date.strftime('%H:%M')
            ),
            buttons=[Button.inline(button_back[language], data='back')]
        )
        if not topic_input_entity:
            logging.error("Topic chat ID is not set, please set it in the settings.")
            return
        await bot.send_message(
            topic_input_entity,
            add_schedule_topic_message.format(
                '🏥' if type == 'medical' \
                else '🧹' if type == 'cleaning' \
                else '😸⬆️',
                user.telegram,
                'медуходу' if type == 'medical' \
                else 'уборке' if type == 'cleaning' \
                else 'выдаче кошков',
                'сегодня' if date == datetime.now().date() else 'завтра' if date == datetime.now().date() + timedelta(days=1) else format_date_by_language(date, 'ru'),
                date.strftime('%H:%M')
            ),
            reply_to=cleaning_topic_id if type == 'cleaning' \
                else medical_topic_id if type == 'medical' \
                else steril_cat_topic_id
        )

        if extra:
            # send the message to the curator if extra is set
            curator = int(extra)
            await bot.send_message(
                curator,
                f"🔔 Новая запись на {'приёмку' if type == 'steril_acceptance' else 'выдачу'} кошков от {user.telegram} на {format_date_by_language(date, language)}."
            )

    # View my scheduled dates
    if data == 'my_schedule':
        # Show loading state while fetching data from Airtable
        await show_loading_state(event, language)

        # get a list of scheduled dates
        scheduled_dates = Schedule.all(fields=['date', 'type'], formula=match({'telegram_chat_id': event.sender.id, 'date': ('>=', datetime.now().date())}), sort=['date'])
        for date in scheduled_dates:
            date.date = date.date.astimezone(datetime.now().astimezone().tzinfo)
        buttons = [
            [
                Button.inline(f"{format_date_by_language(date.date, language)}: { \
                button_type_cleaning[language] if date.type == 'cleaning' \
                else button_type_medical[language] if date.type == 'medical' \
                else button_type_steril_release[language] if date.type == 'steril_release' \
                else button_type_steril_acceptance[language]}" + (f" ({(date.date).strftime('%H:%M')})" if date.type != 'steril_acceptance' else ''),
                           data=f'my_schedule_delete;{date.date.strftime('%Y-%m-%d %H:%M')};{date.type}')
            ] for date in scheduled_dates
        ]
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(my_schedule_prompt[language], buttons=buttons)

    # Ask to confirm the deletion of a scheduled date
    if data.startswith('my_schedule_delete'):
        _, _date, type = data.split(';')
        date = datetime.strptime(_date, '%Y-%m-%d %H:%M')
        logging.info(f"Deleting schedule: {date}, {type}")
        buttons = [
            [Button.inline(button_yes[language], data=f'delete_schedule;{date};{type}')],
            [Button.inline(button_back[language], data='back')]
        ]

        if type == 'steril_acceptance':
            await event.edit(
                my_schedule_delete_prompt_steril_acceptance[language].format(
                    button_type_steril_acceptance[language],
                    format_date_by_language(date, language),
                ),
                buttons=buttons
            )
            return

        await event.edit(
            my_schedule_delete_prompt[language].format(
                button_type_cleaning[language] if type == 'cleaning'
                else button_type_medical[language] if type == 'medical'
                else button_type_steril_release[language] if type == 'steril_release'
                else button_type_steril_acceptance[language],
                format_date_by_language(date, language),
                date.strftime('%H:%M')
            ),
            buttons=buttons
        )

    # Delete a scheduled date from Airtable
    if data.startswith('delete_schedule'):
        # Show loading state while deleting from Airtable
        await show_loading_state(event, language)

        _, _date, type = data.split(';')
        date = datetime.strptime(_date, '%Y-%m-%d %H:%M:%S').astimezone(datetime.now().astimezone().tzinfo) # convert date to local timezone
        # delete a record from the Schedule table
        unwanted_schedule = Schedule.first(formula=match({'telegram_chat_id': event.sender.id, 'date': date, 'type': type}))
        if unwanted_schedule:
            unwanted_schedule.delete()
        else:
            logging.error(f"Record not found: {event.sender.id}, {date}, {type}; probably already deleted.")
        await update_volunteers('delete_schedule')

        if not topic_input_entity:
            logging.error("Topic chat ID is not set, please set it in the settings.")
            return

        if type == 'steril_acceptance':
            # If steril acceptance, send a special message
            await event.edit(
                delete_schedule_success_steril_acceptance[language].format(
                    button_type_steril_acceptance[language],
                    format_date_by_language(date, language)
                ),
                buttons=[Button.inline(button_back[language], data='back')]
            )

            await bot.send_message(
                topic_input_entity,
                delete_schedule_topic_steril_acceptance_message.format(
                    '😿⬇️',
                    user.telegram,
                    'сегодня' if date == datetime.now().date() else 'завтра' if date == datetime.now().date() + timedelta(days=1) else format_date_by_language(date, 'ru'),
                ),
                reply_to=steril_cat_topic_id
            )
            return

        await event.edit(
            delete_schedule_success[language].format(
                button_type_cleaning[language] if type == 'cleaning'
                else button_type_medical[language] if type == 'medical'
                else button_type_steril_release[language],
                format_date_by_language(date, language),
                date.strftime('%H:%M')
            ),
            buttons=[Button.inline(button_back[language], data='back')]
        )

        await bot.send_message(
            topic_input_entity,
            delete_schedule_topic_message.format(
                '🏥' if type == 'medical'
                else '🧹' if type == 'cleaning'
                else '😿⬆️',
                user.telegram,
                'медуходу' if type == 'medical'
                else 'уборке' if type == 'cleaning'
                else 'выдаче кошков',
                'сегодня' if date == datetime.now().date() else 'завтра' if date == datetime.now().date() + timedelta(days=1) else format_date_by_language(date, 'ru'),
                date.strftime('%H:%M')
            ),
            reply_to=cleaning_topic_id if type == 'cleaning'
            else medical_topic_id if type == 'medical'
            else steril_cat_topic_id
        )

    # View all scheduled dates
    if data == 'general_schedule':
        # show a list of all scheduled dates
        if language == 'ru':
            translated_dates = []
            for item in dates_list:
                for key, value in localized_dates['ru'].items():
                    item = item.replace(key, value)
                translated_dates.append(item)
        await event.edit(
            general_schedule[language].format(
                today,
                ', '.join(today_volunteers_list) if today_volunteers_list else '😿',
                '\n'.join(dates_list if language == 'en' else translated_dates)),
            buttons=[Button.inline(button_back[language], data='back')]
        )

    #--------------------------------------------------------------------------
    # Admin menu
    #--------------------------------------------------------------------------
    if data.startswith('notifications;;') or data.startswith('notifications;unset;') or data.startswith('notifications;reset;'):
        _, action, type = data.split(';')
        logging.info(f"Notifications settings: {action}, {type}")
        if action == 'unset':
            custom_text_setting.pop(event.sender.id)

        # show current notifications settings
        currect_settings = Notification.first(fields=['admin_curator', 'notify_at', 'custom_text_cleaning', 'custom_text_medical', 'date_threshold'], formula=match({'telegram_chat_id': event.sender.id}))
        if not currect_settings:
            currect_settings = Notification(
                admin_curator=event.sender.username,
                volunteer=user,
                telegram_chat_id=event.sender.id,
                notify_at='12:00',
                date_threshold='+1')
            currect_settings.save()

        if action == 'reset':
            if type == 'cleaning':
                currect_settings.custom_text_cleaning = ''
            elif type == 'medical':
                currect_settings.custom_text_medical = ''
            currect_settings.save()
            custom_text_setting.pop(event.sender.id)

        buttons = [
            [Button.inline(button_notifications_settings_text_menu[language], data=f'notifications_settings_text_menu')],
            [Button.inline(button_notifications_settings_notify_at[language], data='notifications_settings_notify_at')],
            [Button.inline(button_notifications_settings_date_threshold[language], data='notifications_settings_date_threshold')],
            [Button.inline(button_notifications_send_menu[language], data='notifications_send_menu')],
            [Button.inline(button_back[language], data='back')]
        ]
        notification_date = datetime.now().date() + timedelta(days=int(str(currect_settings.date_threshold).split('+')[1]))
        await event.edit(
            notifications_menu[language].format(
                str(currect_settings.custom_text_cleaning).format(format_date_by_language(notification_date, language)) if currect_settings.custom_text_cleaning != '' else default_cleaning_notification_text[language].format(format_date_by_language(notification_date, language)),
                str(currect_settings.custom_text_medical).format(format_date_by_language(notification_date, language)) if currect_settings.custom_text_medical != '' else default_medical_notification_text[language].format(format_date_by_language(notification_date, language)),
                currect_settings.notify_at,
                currect_settings.date_threshold,
                format_date_by_language(notification_date, language)
            ),
            buttons=buttons
        )

    if data == 'notifications_settings_text_menu':
        # show prompt to select the type of notification
        buttons = [
            [Button.inline(button_notifications_settings_cleaning_text[language], data='notifications_settings_text;cleaning')],
            [Button.inline(button_notifications_settings_medical_text[language], data='notifications_settings_text;medical')],
            [Button.inline(button_back[language], data='notifications;;')]
        ]
        await event.edit(notifications_settings_text_menu[language], buttons=buttons)

    if data.startswith('notifications_settings_text;'):
        _, type = data.split(';')
        # show prompt to set custom text
        custom_text_setting[event.sender.id] = {}
        custom_text_setting[event.sender.id]['type'] = type
        custom_text_setting[event.sender.id]['prompt'] = await event.edit(
            notifications_settings_text_prompt[language],
            buttons=[Button.inline(button_back[language], data='notifications;unset;'), Button.inline(button_notifications_text_reset[language], data=f'notifications;reset;{type}')]
        )

    if data == 'notifications_settings_notify_at':
        # prepare a list of available hours
        hours = [f"{i:02d}:00" for i in range(24)]
        # show buttons 4 in a row
        buttons = [
            [Button.inline(hour, data=f'notifications_settings_notify_at;{hour}') for hour in hours[i:i+4]] for i in range(0, len(hours), 4)
        ]
        buttons.append([Button.inline(button_back[language], data='notifications;;')])
        await event.edit(notifications_settings_notify_at_prompt[language], buttons=buttons)

    if data.startswith('notifications_settings_notify_at;'):
        _, time_str = data.split(';')
        hour, minute = time_str.split(':')
        admin = Notification.first(formula=match({'telegram_chat_id': event.sender.id}))
        admin.notify_at = f"{hour}:{minute}"
        admin.save()
        await event.edit(notifications_settings_notify_at_success[language].format(f"{hour}:{minute}"), buttons=[Button.inline(button_back[language], data='notifications;;')])

    if data == 'notifications_settings_date_threshold':
        # prepare a list of available days
        days = [f"+{i}" for i in range(1, 7)]
        buttons = [
            [Button.inline(day, data=f'notifications_settings_date_threshold;{day}') for day in days]
        ]
        buttons.append([Button.inline(button_back[language], data='notifications;;')])
        await event.edit(notifications_settings_date_threshold_prompt[language], buttons=buttons)

    if data.startswith('notifications_settings_date_threshold;'):
        _, day = data.split(';')
        admin = Notification.first(formula=match({'telegram_chat_id': event.sender.id}))
        admin.date_threshold = day
        admin.save()

        day_variation = {
            'en': 'days' if int(day) > 1 else 'day',
            'ru': 'день' if int(day) == 1 else 'дня' if int(day) < 5 else 'дней'
        }
        await event.edit(notifications_settings_date_threshold_success[language].format(day, day_variation[language]), buttons=[Button.inline(button_back[language], data='notifications;;')])

    if data == 'notifications_send_menu':
        # show prompt to select the type of notification
        buttons = [
            [Button.inline(button_curator_notifications_send_cleaning[language], data='notifications_send;cleaning;')],
            [Button.inline(button_curator_notifications_send_medical[language], data='notifications_send;medical;')],
            [Button.inline(button_curator_notifications_send_all[language], data='notifications_send;all;')],
            [Button.inline(button_back[language], data='notifications;;')]
        ]
        await event.edit(notifications_send_menu[language], buttons=buttons)

    if data.startswith('notifications_send;'):
        _, type, date = data.split(';')
        if date != '':
            date = datetime.fromtimestamp(float(date))
        all_volunteers_count, received_notifications_count = await send_notifications(event.sender.id, type, date)
        await event.edit(notifications_send_success[language].format(received_notifications_count, all_volunteers_count), buttons=[Button.inline(button_back[language], data='back')])


    # ----------------------------------------------------------------------------
    # Cat acceptance-release notifications
    # ----------------------------------------------------------------------------
    if data.startswith('notifications_steril;;'):
        # ask for the dates
        today = datetime.now().date()
        next_saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        next_sunday = next_saturday + timedelta(days=1)
        next_next_saturday = next_saturday + timedelta(days=7)
        next_next_sunday = next_next_saturday + timedelta(days=1)

        # format dates to dd.mm
        next_saturday_str = format_date_by_language(next_saturday, language)
        next_sunday_str = format_date_by_language(next_sunday, language)
        next_next_saturday_str = format_date_by_language(next_next_saturday, language)
        next_next_sunday_str = format_date_by_language(next_next_sunday, language)

        buttons = [
            [Button.inline(f"{next_saturday_str} — {next_sunday_str}", data=f'notifications_steril;{next_saturday}')],
            [Button.inline(f"{next_next_saturday_str} — {next_next_sunday_str}", data=f'notifications_steril;{next_next_saturday}')],
        ]
        buttons.append([Button.inline(button_steril_own_dates[language], data='notifications_steril_own_dates;;')])
        buttons.append([Button.inline(button_back[language], data='back')])

        await event.edit(notifications_steril_curator_dates_prompt[language], buttons=buttons)
        return

    if data.startswith('notifications_steril_own_dates'):
        # ask for the dates
        # build dates buttons for 2 weeks in advance
        today = datetime.now().date()
        available_dates = []
        for i in range(14):
            date = today + timedelta(days=i)
            available_dates.append(date)
        buttons = [
            [Button.inline(format_date_by_language(date, language), data=f'notifications_steril;{date}') for date in available_dates[i:i+2]] for i in range(0, len(available_dates), 2)
        ]
        buttons.append([Button.inline(button_back[language], data='notifications_steril;;')])
        await event.edit(notifications_steril_curator_start_date_prompt[language], buttons=buttons)

    if data.startswith('notifications_steril;'):
        _, start = data.split(';')
        start_date = datetime.strptime(start, '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=1)

        # show confirmation prompt
        buttons = [
            [Button.inline(button_yes[language], data=f'notifications_steril_confirm;{start}')],
            [Button.inline(button_back[language], data='notifications_steril;;')]
        ]

        formatted_start_date = format_date_by_language(start_date, language)
        formatted_end_date = format_date_by_language(end_date, language)

        await event.edit(
            notifications_steril_curator_confirm_prompt[language].format(
                notifications_steril_message[language].format(
                    formatted_start_date, formatted_end_date,
                    formatted_start_date,
                    f"{formatted_start_date} и {formatted_end_date}" if language == 'ru' else f"{formatted_start_date} and {formatted_end_date}",
                    formatted_end_date
                )
            ),
            buttons=buttons
        )

    if data.startswith('notifications_steril_confirm;'):
        _, start = data.split(';')
        start_date = datetime.strptime(start, '%Y-%m-%d')

        # Show loading state while sending notifications
        await show_loading_state(event, language)

        # send notifications to all volunteers with 'steril_cat_in_out' duty
        all_volunteers_count, received_notifications_count = await send_notifications(event.sender.id, 'steril', start_date)
        await event.edit(
            notifications_send_success[language].format(
                received_notifications_count, all_volunteers_count
            ), buttons=[
                [Button.inline(button_back[language], data='back')]
            ]
        )

    if data.startswith('new_steril_'):
        type = data.split('_')[2].split(';')[0]  # 'acceptance' or 'release'
        curator = data.split(';')[1]
        date = datetime.fromtimestamp(float(data.split(';')[2])).date()
        # show prompt to choose date
        if type == 'acceptance':
            buttons = [
                [Button.inline(format_date_by_language(date, language), data=f'add_schedule;{date};;steril_{type};{curator}')],
                [Button.inline(format_date_by_language(date + timedelta(days=1), language), data=f'add_schedule;{date + timedelta(days=1)};;steril_{type};{curator}')]
            ]
        # or time if it's release shift
        else:
            buttons = [
                [Button.inline(format_date_by_language(date, language), data=f'set_schedule_time;{date};steril_{type};{curator}')],
                [Button.inline(format_date_by_language(date + timedelta(days=1), language), data=f'set_schedule_time;{date + timedelta(days=1)};steril_{type};{curator}')]
            ]

        buttons.append([Button.inline(button_back[language], data='back_steril')])

        await event.edit(
            notifications_steril_volunteer_acceptance_prompt[language] if type == 'acceptance' else notifications_steril_volunteer_release_date_prompt[language],
            buttons=buttons
        )

    # ----------------------------------------------------
    # Settings section
    # ----------------------------------------------------
    if data == 'change_language':
        await start_handler(event, check_user=False, language=language)

    if data.startswith('change_view;'):
        _, view = data.split(';')

        current_view = settings_view[view][language]

        buttons = [
            [Button.inline(type[language], data=f'change_view_to;{name}') for name, type in settings_view.items()],
            [Button.inline(button_back[language], data='back_settings')]
        ]

        await event.edit(
            settings_view_prompt[language].format(current_view),
            buttons=buttons
        )

    if data.startswith('change_view_to;'):
        _, new_view = data.split(';')
        user.schedule_view = new_view
        user.save()

        await event.edit(
            settings_view_success[language].format(settings_view[new_view][language]),
            buttons=[
                [Button.inline(button_back[language], data='back')]
            ]
        )

    # Get back

    if data == 'back_steril':
        # Go back to the steril notification for choosing another shift type
        await event.edit(
            steril_notification_message.message,
            buttons=steril_notification_message.buttons,
            formatting_entities=steril_notification_message.entities
        )

    if data == 'back_settings':
        await settings_handler(event, edit=True)

    if data == 'back':
        await schedule_handler(event, language, update=True)

async def main():
    asyncio.Task(update_volunteers('startup'))
    await bot.run_until_disconnected()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())