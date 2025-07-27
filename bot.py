from telethon import TelegramClient, events, Button, utils, functions, types

import logging
import os, time
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

# Helper function to show loading state and prevent multiple button presses
async def show_loading_state(event, user_language: str):
    """Show loading message and remove buttons to prevent multiple presses"""
    try:
        await event.edit(loading_text[user_language], buttons=None)
    except Exception as err:
        logging.error(f"Error showing loading state: {err}")

# region Functions

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
            today_volunteers_list.append(('🧹'+date.volunteer.telegram if date.type == 'cleaning' else '🏥'+date.volunteer.telegram) + f'({date.date.strftime('%H:%M')})')
            continue
        same_date = [d for d in dates_list if d.startswith(date.date.strftime('%d.%m'))]
        if same_date:
            dates_list.remove(same_date[0])
            dates_list.append(f"{date.date.strftime('%d.%m, %A')}: {same_date[0].split(': ')[1]}, {'🧹'+date.volunteer.telegram if date.type == 'cleaning' else '🏥'+date.volunteer.telegram} ({date.date.strftime('%H:%M')})")
        else:
            dates_list.append(f"{date.date.strftime('%d.%m, %A')}: {'🧹'+date.volunteer.telegram if date.type == 'cleaning' else '🏥'+date.volunteer.telegram} ({date.date.strftime('%H:%M')})")

    logging.info(f"<{step}> Volunteers list and schedule updated.")

    # update messages in topics
    settings = Settings.all()
    settings_dict = {setting.key: setting.test_value for setting in settings}

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
        search_message = await bot.get_messages(topic_input_entity, ids=message_id)
        if not message_id or not search_message:
            if not message_id:
                logging.info(f"<{step}> Message ID is not set, creating a new message.")
            if not search_message:
                logging.info(f"<{step}> Message not found in topic {topic}, creating a new message.")
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
            setting.test_value = pin_message.id
            setting.save()

    # update messages in topics
    if step != 'startup':
        for id, setting_key, _ in messages:
            await bot.edit_message(topic_input_entity, id, general_schedule['ru'].format(
                today,
                ', '.join(today_volunteers_list) if today_volunteers_list else '😿',
                '\n'.join(dates_list)
            ))
            await asyncio.sleep(0.5) # avoid flood limits

    # re-pin messages in topics if step is 'daily'
    if step == 'daily':
        # re-pin messages in topics
        for id, setting_key, topic in messages:
            if topic:
                logging.info(f"<{step}> Re-pinning message {id} in topic {topic}")
                await bot.pin_message(topic_input_entity, id)
                setting = Settings.first(formula=match({'key': setting_key}))
                setting.test_value = id
                setting.save()

    logging.info(f"<{step}> Messages in topics updated.")

# send notifications to volunteers, return the number of sent notifications and the total number of volunteers
@airtable_context('send_notifications')
async def send_notifications(curator_id: int, type: str = '', date: datetime = None):
    # send notifications to all volunteers with roles kk_cleaning
    volunteers = Volunteer.all(fields=['telegram_chat_id', 'language', 'volunteer_roles'])
    if type == 'cleaning':
        notifiable_volunteers = [volunteer for volunteer in volunteers if 'kk_cleaning' in volunteer.roles]
    elif type == 'medical':
        notifiable_volunteers = [volunteer for volunteer in volunteers if 'kk_medical' in volunteer.roles]
    else:
        notifiable_volunteers = [volunteer for volunteer in volunteers if 'kk_cleaning' in volunteer.roles or 'kk_medical' in volunteer.roles]
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
            roles_set = []
            if 'kk_cleaning' in volunteer.roles:
                roles_set.append('cln')
            if 'kk_medical' in volunteer.roles:
                roles_set.append('med')
            if 'steril_cat_in_out' in volunteer.roles:
                roles_set.append('steril')

            roles_set = '+'.join(roles_set)

            buttons = [
                [Button.inline(button_new_schedule[volunteer.language], data=f'new_schedule;{roles_set}')],
            ]

            if type != 'all':
                await bot.send_message(
                    volunteer.telegram_chat_id, 
                        text_cleaning.format(format_date_by_language(date, volunteer.language)) if type == 'cleaning' else text_medical.format(format_date_by_language(date, volunteer.language)),
                    buttons=buttons
                )
            else:
                await bot.send_message(
                    volunteer.telegram_chat_id, 
                    text_cleaning.format(format_date_by_language(date, volunteer.language)) + '\n\n' + text_medical.format(format_date_by_language(date, volunteer.language)),
                    buttons=buttons
                )

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
    # find all volunteers with roles that contain 'kk_admin_curator'
    volunteers = Volunteer.all(fields=['telegram', 'telegram_chat_id', 'volunteer_roles', 'language'])
    curators = [volunteer for volunteer in volunteers if 'kk_admin_curator' in volunteer.roles]

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
        curator_settings = curator_settings_map[curator.telegram_chat_id]
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

# function to format the date in the user's language
def format_date_by_language(date: datetime, language: str):
    formatted_date = format_date(date, format='dd.MM, EEEE', locale=language) # use generic format for all languages: 31.12, Monday
    return f"{formatted_date.split(' ')[0]} {formatted_date.split(' ')[1].capitalize()}" # capitalize the first letter of the day of the week

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
    # show language selection menu on first launch
    if not check_user:
        buttons = [
            [Button.inline(languages[lang], data=f'language:{lang}')] for lang in languages
        ]
        await event.respond(language_selection['en'], buttons=buttons)
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
async def settings_handler(event):
    # show language selection menu
    await start_handler(event, check_user=False)

@bot.on(events.NewMessage(pattern='/set_cleaning_topic|/set_medical_topic|/set_steril_cat_topic'))
@logger
async def set_topic_handler(event):
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    if not user:
        await event.respond(error_not_registered[user.language])
        return

    if 'kk_admin_curator' not in user.roles:
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
async def schedule_handler(event, language: str = 'en', update: bool = False):
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
    roles_set = []
    if 'kk_cleaning' in user.roles:
        roles_set.append('cln')
    if 'kk_medical' in user.roles:
        roles_set.append('med')
    if 'steril_cat_in_out' in user.roles:
        roles_set.append('steril')

    if not roles_set:
        roles_set = 'none'
    else:
        roles_set = '+'.join(roles_set)

    admin_flag = True if 'kk_admin_curator' in user.roles else False

    buttons = [
        [Button.inline(button_new_schedule[language], data=f'new_schedule;{roles_set}')],
        [Button.inline(button_my_schedule[language], data=f'my_schedule')],
        [Button.inline(button_general_schedule[language], data=f'general_schedule')]
    ]

    if admin_flag:
        buttons.append([Button.inline(button_notifications[language], data='notifications;;')])

    if update:
        await event.edit(main_menu_header[language]+'\n\n'+todays_volunteers[language].format(today, ', '.join(today_volunteers_list) if today_volunteers_list else '😿'), buttons=buttons)
        return

    await event.respond(main_menu_header[language]+'\n\n'+todays_volunteers[language].format(today, ', '.join(today_volunteers_list) if today_volunteers_list else '😿'), buttons=buttons)

# region Buttons
@bot.on(events.CallbackQuery())
@logger
@airtable_context('callback_handler')
async def callback_handler(event):
    global scheduled_dates, today_volunteers_list, dates_list, custom_text_setting, topic_input_entity, cleaning_topic_id, medical_topic_id, steril_cat_topic_id

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
        # ask for the type of schedule if role_switch is 3 (both roles are assigned)
        if data.split(';')[1] == 'none':
            await event.edit(error_no_roles[language], buttons=[Button.inline(button_back[language], data='back')])
            return
        elif len(data.split(';')[1].split('+')) > 1:
            buttons = []
            roles = data.split(';')[1].split('+')
            if 'cln' in roles:
                buttons.append([Button.inline(button_type_cleaning[language], data='new_schedule;cleaning')])
            if 'med' in roles:
                buttons.append([Button.inline(button_type_medical[language], data='new_schedule;medical')])
            if 'steril' in roles:
                buttons.append([Button.inline(button_type_steril[language], data='new_schedule;steril')])


        type = data.split(';')[1]
        if type not in ['cleaning', 'medical', 'steril']:
            if type == 'cln':
                type = 'cleaning'
            elif type == 'med':
                type = 'medical'

        # prepare a list of available dates, from today to 2 weeks in advance
        available_dates = {}
        for i in range(14):
            date = datetime.now().date() + timedelta(days=i)
            available_dates[date] = {}
            available_dates[date]['cleaning'] = 0
            available_dates[date]['medical'] = 0
            available_dates[date]['steril'] = 0

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
                           data=f'set_schedule_time;{date};{type}')] for date in available_dates
        ]
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(new_schedule_prompt_cleaning[language] if type == 'cleaning' else new_schedule_prompt_medical[language], buttons=buttons)

    # Ask for the time of the scheduled date
    if data.startswith('set_schedule_time'):
        _, date, type = data.split(';')
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
                    row.append(Button.inline(f"{i:02d}:00", data=f'add_schedule;{date};{i:02d}:00;{type}'))
            if row:  # Only add non-empty rows
                buttons.append(row)
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(set_schedule_time_prompt[language].format(format_date_by_language(date, language)), buttons=buttons)

    # Write a new scheduled date to Airtable
    if data.startswith('add_schedule'):
        # Show loading state while saving to Airtable
        await show_loading_state(event, language)
        
        _, date, time, type = data.split(';')
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
        await event.edit(
            add_schedule_success[language].format(
                button_type_cleaning[language] if type == 'cleaning' else button_type_medical[language],
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
                '🏥' if type == 'medical' else '🧹',
                user.telegram,
                'медуходу' if type == 'medical' else 'уборке',
                'сегодня' if date == datetime.now().date() else 'завтра' if date == datetime.now().date() + timedelta(days=1) else format_date_by_language(date, 'ru'),
                date.strftime('%H:%M')
            ),
            reply_to=cleaning_topic_id if type == 'cleaning' else medical_topic_id
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
            [Button.inline(f"{format_date_by_language(date.date, language)}: {button_type_cleaning[language] if date.type == 'cleaning' else button_type_medical[language]} {(date.date).strftime('%H:%M')}",
                           data=f'my_schedule_delete;{date.date.strftime('%Y-%m-%d %H:%M')};{date.type}')] for date in scheduled_dates
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
        await event.edit(
            my_schedule_delete_prompt[language].format(
                button_type_cleaning[language] if type == 'cleaning' else button_type_medical[language],
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
        await event.edit(
            delete_schedule_success[language].format(
                button_type_cleaning[language] if type == 'cleaning' else button_type_medical[language],
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
            delete_schedule_topic_message.format(
                '🏥' if type == 'medical' else '🧹',
                user.telegram,
                'медуходу' if type == 'medical' else 'уборке',
                'сегодня' if date == datetime.now().date() else 'завтра' if date == datetime.now().date() + timedelta(days=1) else format_date_by_language(date, 'ru'),
                date.strftime('%H:%M')
            ),
            reply_to=cleaning_topic_id if type == 'cleaning' else medical_topic_id
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

    # Get back
    if data == 'back':
        await schedule_handler(event, language, update=True)

async def main():
    asyncio.Task(update_volunteers('startup'))
    await bot.run_until_disconnected()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())