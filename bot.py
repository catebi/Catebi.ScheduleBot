from telethon import TelegramClient, events, Button, utils

import logging
import os, time
from pyairtable import Api
from pyairtable.formulas import match
from datetime import datetime, timedelta
from babel.dates import format_date

import aiocron
import asyncio

from settings import *
from translations import *
from airtable_model import *
import airtable_logger  # Import the new logging module

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
today_volunteers = None
scheduled_dates = None
today_volunteers_list = None
dates_list = None
topic_input_entity = None
cleaning_topic_id = None
medical_topic_id = None

# region Functions

# update volunteers list and schedule
async def update_volunteers(step: str):
    global today_volunteers, scheduled_dates, today_volunteers_list, dates_list, topic_input_entity, cleaning_topic_id, medical_topic_id
    today_volunteers = Schedule.all(fields=['volunteer'], formula=match({'date': datetime.now().date()}))
    scheduled_dates = Schedule.all(fields=['date', 'volunteer', 'telegram', 'type'], sort=['date'], formula=match({'date': (">=", datetime.now().date())}))

    today_volunteers_list = []
    dates_list = []
    for date in scheduled_dates:
        # aggregate volunteers if two are scheduled at the same date
        if date.date == datetime.now().date():
            today_volunteers_list.append(date.volunteer.telegram if date.type == 'cleaning' else '🏥'+date.volunteer.telegram)
            continue
        same_date = [d for d in dates_list if d.startswith(date.date.strftime('%d.%m'))]
        if same_date:
            dates_list.remove(same_date[0])
            dates_list.append(f"{date.date.strftime('%d.%m, %A')}: {same_date[0].split(': ')[1]}, {date.volunteer.telegram if date.type == 'cleaning' else '🏥'+date.volunteer.telegram}")
        else:
            dates_list.append(f"{date.date.strftime('%d.%m, %A')}: {date.volunteer.telegram if date.type == 'cleaning' else '🏥'+date.volunteer.telegram}")

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
    last_pinned_general_message_id = settings_dict.get('last_pinned_general_message_id')
    last_pinned_cleaning_message_id = settings_dict.get('last_pinned_cleaning_message_id')
    last_pinned_medical_message_id = settings_dict.get('last_pinned_medical_message_id')

    messages = [
        (last_pinned_general_message_id, 'last_pinned_general_message_id', None),
        (last_pinned_cleaning_message_id, 'last_pinned_cleaning_message_id', cleaning_topic_id),
        (last_pinned_medical_message_id, 'last_pinned_medical_message_id', medical_topic_id)
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
            pin_message = await bot.send_message(
                topic_input_entity,
                general_schedule['ru'].format(
                    ', '.join(today_volunteers_list) if today_volunteers_list else '😿',
                    '\n'.join(dates_list)
                ),
                reply_to=topic
            )
            await bot.pin_message(topic_input_entity, pin_message.id)
            setting = Settings.first(formula=match({'key': setting_key}))
            setting.value = pin_message.id
            setting.save()

    if step != 'startup':
        for id, setting_key, _ in messages:
            await bot.edit_message(topic_input_entity, id, general_schedule['ru'].format(
                ', '.join(today_volunteers_list) if today_volunteers_list else '😿',
                '\n'.join(dates_list)
            ))
            await asyncio.sleep(0.5) # avoid flood limits

    logging.info(f"<{step}> Messages in topics updated.")

# send notifications to volunteers, return the number of sent notifications and the total number of volunteers
async def send_notifications(curator_id: int):
    # send notifications to all volunteers with roles kk.cleaning
        volunteers = Volunteer.all(fields=['telegram_chat_id', 'language', 'volunteer_roles'])
        notifiable_volunteers = [volunteer for volunteer in volunteers if 'kk.cleaning' in volunteer.roles]
        curator = Volunteer.first(formula=match({'telegram_chat_id': curator_id}))
        text = Notification.first(formula=match({'telegram_chat_id': curator_id})).custom_text
        date = datetime.now().date() + timedelta(days=int(str(Notification.first(formula=match({'telegram_chat_id': curator_id})).date_threshold).split('+')[1]))
        if not text:
            text = default_notification_text[curator.language]

        # count all selected volunteers
        all_volunteers_count = len(notifiable_volunteers)
        received_notifications_count = 0
        # iterate over all volunteers and send notifications
        for volunteer in notifiable_volunteers:
            try:
                role_switch = 'none'
                if 'kk.medical' in volunteer.roles and 'kk.cleaning' in volunteer.roles:
                    role_switch = 'both'
                elif 'kk.medical' in volunteer.roles and 'kk.cleaning' not in volunteer.roles:
                    role_switch = 'medical'
                elif 'kk.cleaning' in volunteer.roles and 'kk.medical' not in volunteer.roles:
                    role_switch = 'cleaning'

                buttons = [
                    [Button.inline(button_new_schedule[volunteer.language], data=f'new_schedule:{role_switch}')],
                ]

                await bot.send_message(volunteer.telegram_chat_id, text.format(format_date_by_language(date, volunteer.language)), buttons=buttons)
                time.sleep(0.5) # avoid flood limits
                received_notifications_count += 1
            except Exception as err:
                logging.error(f"Error sending notification to {volunteer.telegram_chat_id}: {err}")

        return all_volunteers_count, received_notifications_count

# Update volunteers list and schedule at midnight
@logger
@aiocron.crontab('0 0 * * *') # every day at midnight
async def daily_schedule_update():
    await update_volunteers('daily')

# send personal notification to curators at their set time
@logger
@aiocron.crontab('* */1 * * *') # every hour
async def send_curator_notifications():
    # find all volunteers with roles that contain 'kk.admin_curator'
    volunteers = Volunteer.all(fields=['telegram', 'telegram_chat_id', 'volunteer_roles', 'language'])
    curators = [volunteer for volunteer in volunteers if 'kk.admin_curator' in volunteer.roles]
    for curator in curators:
        curator_settings = Notification.first(formula=match({'telegram_chat_id': curator.telegram_chat_id}))
        # check if the current time is equal to the time set in the notify_at field
        if datetime.now().strftime('%H:%M') == curator_settings.notify_at:
            # check if there are no volunteers scheduled for any date between today and the threshold date
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=int(str(curator_settings.date_threshold).split('+')[1]))
            for date in (start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)):
                if not Schedule.first(formula=match({'date': date})):
                    logging.info(f"No volunteers found for {date} for {curator.telegram}, sending notification.")
                    buttons = [
                        [Button.inline(button_curator_notifications_send[curator.language], data='notifications_send')],
                        [Button.inline(button_curator_ignore[curator.language], data='back')]
                    ]
                    await bot.send_message(curator.telegram_chat_id, notifications_no_volunteers[curator.language].format(format_date_by_language(date, curator.language)), buttons=buttons)
                    break  # Send only one notification for the closest date and break the loop, comment this to send notifications for all dates


# function to format the date in the user's language
def format_date_by_language(date: datetime, language: str):
    formatted_date = format_date(date, format='dd.MM, EEEE', locale=language) # use generic format for all languages: 31.12, Monday
    return f"{formatted_date.split(' ')[0]} {formatted_date.split(' ')[1].capitalize()}" # capitalize the first letter of the day of the week



# handle custom notification text setting
custom_text_setting = {}
@bot.on(events.NewMessage())
@logger
async def notifications_handler(event):
    if event.sender.id not in custom_text_setting:
        return

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

    admin.custom_text = custom_text
    admin.save()

    prompt = custom_text_setting[event.sender.id]['prompt']

    await prompt.edit(prompt.message, buttons=None) # remove buttons from the prompt to avoid multiple clicks
    await event.respond(notifications_settings_text_success[admin.volunteer.language], buttons=[Button.inline(button_back[admin.volunteer.language], data='notifications')])

    custom_text_setting.pop(event.sender.id)

# region Commands

@bot.on(events.NewMessage(pattern='/start', func=lambda e: e.is_private)) # Only in private chat
@logger
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
async def help_handler(event):
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    language = user.language if user else 'en'
    version_info = f"🤖 Bot Version: `{version}`"  # Add version info here

    if not user:
        # show warning that the user is not an existing volunteer
        await event.respond(f"{error_not_registered[language]}\n\n{version_info}")
        return

    await event.respond(f"{help_message[language]}\n\n{version_info}")

@bot.on(events.NewMessage(pattern='/settings'))
@logger
async def settings_handler(event):
    # show language selection menu
    await start_handler(event, check_user=False)

@bot.on(events.NewMessage(pattern='/set_cleaning_topic|/set_medical_topic'))
@logger
async def set_topic_handler(event):
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    if not user:
        await event.respond(error_not_registered[user.language])
        return

    if 'kk.admin_curator' not in user.roles:
        await event.respond(error_not_admin[user.language])
        return

    # set topic type
    topic_type = 'cleaning' if event.pattern_match.group(0) == '/set_cleaning_topic' else 'medical'
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
async def schedule_handler(event, language: str = 'en', update: bool = False):
    global today_volunteers, today_volunteers_list
     # check if user exists in Airtable
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    if not user:
        # show warning that the user is not an existing volunteer
        await event.respond(error_not_registered[language])
        return

    language = user.language if user else 'en'
    role_switch = 'none'
    if 'kk.medical' in user.roles and 'kk.cleaning' in user.roles:
        role_switch = 'both'
    elif 'kk.medical' in user.roles and 'kk.cleaning' not in user.roles:
        role_switch = 'medical'
    elif 'kk.cleaning' in user.roles and 'kk.medical' not in user.roles:
        role_switch = 'cleaning'

    admin_flag = True if 'kk.admin_curator' in user.roles else False

    buttons = [
        [Button.inline(button_new_schedule[language], data=f'new_schedule:{role_switch}')],
        [Button.inline(button_my_schedule[language], data=f'my_schedule')],
        [Button.inline(button_general_schedule[language], data=f'general_schedule')]
    ]

    if admin_flag:
        buttons.append([Button.inline(button_notifications[language], data='notifications')])

    if update:
        await event.edit(main_menu_header[language]+'\n\n'+todays_volunteers[language].format(', '.join(today_volunteers_list) if today_volunteers_list else '😿'), buttons=buttons)
        return

    await event.respond(main_menu_header[language]+'\n\n'+todays_volunteers[language].format(', '.join(today_volunteers_list) if today_volunteers_list else '😿'), buttons=buttons)


# region Buttons
@bot.on(events.CallbackQuery())
@logger
async def callback_handler(event):
    global today_volunteers, scheduled_dates, today_volunteers_list, dates_list, custom_text_setting, topic_input_entity, cleaning_topic_id, medical_topic_id

    data = event.data.decode("utf-8")
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))

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
        if data.split(':')[1] == 'both':
            buttons = [
                [Button.inline(button_type_cleaning[language], data='new_schedule:cleaning')],
                [Button.inline(button_type_medical[language], data='new_schedule:medical')],
                [Button.inline(button_back[language], data='back')]
            ]
            await event.edit(new_schedule_type_prompt[language], buttons=buttons)
            return
        elif data.split(':')[1] == 'none':
            await event.edit(error_no_roles[language], buttons=[Button.inline(button_back[language], data='back')])
            return

        type = data.split(':')[1]
        # prepare a list of available dates, from today to 2 weeks in advance
        available_dates = {}
        for i in range(14):
            date = datetime.now().date() + timedelta(days=i)
            available_dates[date] = {}
            available_dates[date]['cleaning'] = 0
            available_dates[date]['medical'] = 0

        # check if the date is already scheduled by two volunteers, remove it from the list
        scheduled_dates = Schedule.all(fields=['date', 'type'])
        for date in scheduled_dates:
            if date.date in available_dates:
                available_dates[date.date][date.type] += 1

        for date in available_dates.copy(): # copy the list to avoid RuntimeError
            if (available_dates[date][type] == 2 and type == 'cleaning') or (available_dates[date][type] == 1 and type == 'medical'):
                available_dates.pop(date)

        # check if the date is already scheduled by the user, remove it from the list
        user_scheduled_dates = Schedule.all(fields=['date', 'type'], formula=match({'telegram_chat_id': event.sender.id}))
        for date in user_scheduled_dates:
            if date.date in available_dates and date.type == type:
                available_dates.pop(date.date)

        # show a list of available dates
        buttons = [
            [Button.inline(f"{format_date_by_language(date, language)} {'1️⃣' if available_dates[date]['cleaning'] == 1 else '2️⃣' if available_dates[date]['cleaning'] == 2 else '🆓'}",
                           data=f'add_schedule:{date}:{type}')] for date in available_dates
        ]
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(new_schedule_prompt_cleaning[language] if type == 'cleaning' else new_schedule_prompt_medical[language], buttons=buttons)

    # Write a new scheduled date to Airtable
    if data.startswith('add_schedule'):
        _, date, type = data.split(':')
        date = datetime.strptime(date, '%Y-%m-%d').date()
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
                format_date_by_language(date, language)),
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
                'сегодня' if date == datetime.now().date() else 'завтра' if date == datetime.now().date() + timedelta(days=1) else format_date_by_language(date, 'ru')
            ),
            reply_to=cleaning_topic_id if type == 'cleaning' else medical_topic_id
        )

    # View my scheduled dates
    if data == 'my_schedule':
        # get a list of scheduled dates
        scheduled_dates = Schedule.all(fields=['date', 'type'], formula=match({'telegram_chat_id': event.sender.id, 'date': ('>=', datetime.now().date())}), sort=['date'])
        buttons = [
            [Button.inline(f"{format_date_by_language(date.date, language)}: {button_type_cleaning[language] if date.type == 'cleaning' else button_type_medical[language]}",
                           data=f'my_schedule_delete:{date.date}:{date.type}')] for date in scheduled_dates
        ]
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(my_schedule_prompt[language], buttons=buttons)

    # Ask to confirm the deletion of a scheduled date
    if data.startswith('my_schedule_delete:'):
        _, date, type = data.split(':')
        date = datetime.strptime(date, '%Y-%m-%d').date()
        buttons = [
            [Button.inline(button_yes[language], data=f'delete_schedule:{date}:{type}')],
            [Button.inline(button_back[language], data='back')]
        ]
        await event.edit(
            my_schedule_delete_prompt[language].format(
                button_type_cleaning[language] if type == 'cleaning' else button_type_medical[language],
                format_date_by_language(date, language)),
            buttons=buttons
        )

    # Delete a scheduled date from Airtable
    if data.startswith('delete_schedule:'):
        _, date, type = data.split(':')
        date = datetime.strptime(date, '%Y-%m-%d').date()
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
                format_date_by_language(date, language)),
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
                'сегодня' if date == datetime.now().date() else 'завтра' if date == datetime.now().date() + timedelta(days=1) else format_date_by_language(date, 'ru')
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
                ', '.join(today_volunteers_list) if today_volunteers_list else '😿',
                '\n'.join(dates_list if language == 'en' else translated_dates)),
            buttons=[Button.inline(button_back[language], data='back')]
        )



    #--------------------------------------------------------------------------
    # Admin menu
    #--------------------------------------------------------------------------
    if data == 'notifications' or data == 'notifications:unset' or data == 'notifications:reset':
        if 'unset' in data:
            custom_text_setting.pop(event.sender.id)

        if 'reset' in data:
            admin = Notification.first(formula=match({'telegram_chat_id': event.sender.id}))
            admin.custom_text = ''
            admin.save()

        # show current notifications settings
        currect_settings = Notification.first(fields=['admin_curator', 'notify_at', 'custom_text', 'date_threshold'], formula=match({'telegram_chat_id': event.sender.id}))
        if not currect_settings:
            currect_settings = Notification(
                admin_curator=event.sender.username,
                volunteer=user,
                telegram_chat_id=event.sender.id,
                notify_at='12:00',
                date_threshold='+1')
            currect_settings.save()

        buttons = [
            [Button.inline(button_notifications_settings_text[language], data='notifications_settings_text')],
            [Button.inline(button_notifications_settings_notify_at[language], data='notifications_settings_notify_at')],
            [Button.inline(button_notifications_settings_date_threshold[language], data='notifications_settings_date_threshold')],
            [Button.inline(button_notifications_send[language], data='notifications_send')],
            [Button.inline(button_back[language], data='back')]
        ]
        notification_date = datetime.now().date() + timedelta(days=int(str(currect_settings.date_threshold).split('+')[1]))
        await event.edit(
            notifications_menu[language].format(
                str(currect_settings.custom_text).format(format_date_by_language(notification_date, language)) if currect_settings.custom_text != '' else default_notification_text[language].format(format_date_by_language(notification_date, language)),
                currect_settings.notify_at,
                currect_settings.date_threshold,
                format_date_by_language(notification_date, language)
            ),
            buttons=buttons
        )






    if data == 'notifications_settings_text':
        # show prompt to set custom text
        custom_text_setting[event.sender.id] = {}
        custom_text_setting[event.sender.id]['prompt'] = await event.edit(
            notifications_settings_text_prompt[language],
            buttons=[Button.inline(button_back[language], data='notifications:unset'), Button.inline(button_notifications_text_reset[language], data='notifications:reset')]
        )






    if data == 'notifications_settings_notify_at':
        # prepare a list of available hours
        hours = [f"{i:02d}:00" for i in range(24)]
        # show buttons 4 in a row
        buttons = [
            [Button.inline(hour, data=f'notifications_settings_notify_at:{hour}') for hour in hours[i:i+4]] for i in range(0, len(hours), 4)
        ]
        buttons.append([Button.inline(button_back[language], data='notifications')])
        await event.edit(notifications_settings_notify_at_prompt[language], buttons=buttons)

    if data.startswith('notifications_settings_notify_at:'):
        _, hour, minute = data.split(':')
        admin = Notification.first(formula=match({'telegram_chat_id': event.sender.id}))
        admin.notify_at = f"{hour}:{minute}"
        admin.save()
        await event.edit(notifications_settings_notify_at_success[language].format(f"{hour}:{minute}"), buttons=[Button.inline(button_back[language], data='notifications')])







    if data == 'notifications_settings_date_threshold':
        # prepare a list of available days
        days = [f"+{i}" for i in range(1, 7)]
        buttons = [
            [Button.inline(day, data=f'notifications_settings_date_threshold:{day}') for day in days]
        ]
        buttons.append([Button.inline(button_back[language], data='notifications')])
        await event.edit(notifications_settings_date_threshold_prompt[language], buttons=buttons)

    if data.startswith('notifications_settings_date_threshold:'):
        _, day = data.split(':')
        admin = Notification.first(formula=match({'telegram_chat_id': event.sender.id}))
        admin.date_threshold = day
        admin.save()

        day_variation = {
            'en': 'days' if int(day) > 1 else 'day',
            'ru': 'день' if int(day) == 1 else 'дня' if int(day) < 5 else 'дней'
        }
        await event.edit(notifications_settings_date_threshold_success[language].format(day, day_variation[language]), buttons=[Button.inline(button_back[language], data='notifications')])






    if data == 'notifications_send':
        all_volunteers_count, received_notifications_count = await send_notifications(event.sender.id)
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