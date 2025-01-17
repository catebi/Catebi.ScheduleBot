from telethon import TelegramClient, events, Button
import logging
import locale, os, time
from pyairtable import Api
from pyairtable.formulas import match
from datetime import datetime, timedelta
import aiocron

from settings import *
from translations import *
from airtable_model import *

logging.basicConfig(format='[%(levelname)s] %(message)s',
                    level=logging.WARNING)

# TODO:
# - Implement an admin interface to manage notifications
# - Implement a notification system to remind volunteers about their scheduled dates
# - Implement a notification to remind admins there are no volunteers scheduled for the next day
# - Add the ability to change notification text and timing, with default fallbacks

def logger(func):
    def decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            logging.error(err, exc_info=True)
    return decorator

os.environ['TZ'] = 'Asia/Tbilisi'
time.tzset()
logging.warning(f"Timezone set to {os.environ['TZ']}, time is {datetime.now()}.")

# Initialize Airtable API
api = Api(api_key=airtable_api_key)

bot = TelegramClient('catebi', api_id, api_hash).start(bot_token=bot_token)

# Initialize global variables
today_volunteers = None
scheduled_dates = None
today_volunteers_list = None
dates_list = None

# update volunteers list and schedule
def update_volunteers(step: str):
    global today_volunteers, scheduled_dates, today_volunteers_list, dates_list
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

    logging.warning(f"Volunteers list and schedule updated ({step}).")

# populate volunteers list and schedule on bot start
update_volunteers('start')

# Update volunteers list and schedule at midnight
@aiocron.crontab('0 0 * * *')
@logger
def daily_schedule_update():
    update_volunteers('daily')

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
    if not user:
        # show warning that the user is not an existing volunteer
        await event.respond(error_not_registered[language])
        return

    await event.respond(help_message[language])

@bot.on(events.NewMessage(pattern='/settings'))
@logger
async def settings_handler(event):
    # show language selection menu
    await start_handler(event, check_user=False)

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
    roles = user.roles

    buttons = [
        [Button.inline(button_new_schedule[language], data=f'new_schedule:ask' if 'kk.medical' in roles else 'new_schedule:cleaning')],
        [Button.inline(button_my_schedule[language], data=f'my_schedule')],
        [Button.inline(button_general_schedule[language], data=f'general_schedule')]
    ]

    if update:
        await event.edit(main_menu[language].format(', '.join(today_volunteers_list) if today_volunteers_list else '😿'), buttons=buttons)
        return

    await event.respond(main_menu[language].format(', '.join(today_volunteers_list) if today_volunteers_list else '😿'), buttons=buttons)

# region Callbacks
@bot.on(events.CallbackQuery())
@logger
async def callback_handler(event):
    global today_volunteers, scheduled_dates, today_volunteers_list, dates_list

    data = event.data.decode("utf-8")
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    language = user.language
    locale.setlocale(locale.LC_TIME, 'ru_RU.utf8' if language == 'ru' else 'en_US.utf8')

    # Change user's language
    if data.startswith('language'):
        _, lang = data.split(':')
        # save user's language to Airtable
        await start_handler(event, check_user=True, language=lang)

    # New scheduled date
    if data.startswith('new_schedule'):
        if data.split(':')[1] == 'ask':
            buttons = [
                [Button.inline(button_type_cleaning[language], data='new_schedule:cleaning')],
                [Button.inline(button_type_medical[language], data='new_schedule:medical')],
                [Button.inline(button_back[language], data='back')]
            ]
            await event.edit(new_schedule_type_prompt[language], buttons=buttons)
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
            [Button.inline(f"{date.strftime('%d.%m, %A')} {'1️⃣' if available_dates[date]['cleaning'] == 1 else '2️⃣' if available_dates[date]['cleaning'] == 2 else '🆓'}",
                           data=f'add_schedule:{date}:{type}')] for date in available_dates
        ]
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(new_schedule_prompt[language], buttons=buttons)

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
        update_volunteers('add_schedule')
        await event.edit(
            add_schedule_success[language].format(
                button_type_cleaning[language] if type == 'cleaning' else button_type_medical[language],
                date.strftime('%d.%m, %A')),
            buttons=[Button.inline(button_back[language], data='back')]
        )

    # View my scheduled dates
    if data == 'my_schedule':
        # get a list of scheduled dates
        scheduled_dates = Schedule.all(fields=['date', 'type'], formula=match({'telegram_chat_id': event.sender.id}), sort=['date'])
        buttons = [
            [Button.inline(f"{date.date.strftime('%d.%m, %A')}: {button_type_cleaning[language] if date.type == 'cleaning' else button_type_medical[language]}",
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
                date.strftime('%d.%m, %A')), 
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
        update_volunteers('delete_schedule')
        await event.edit(
            delete_schedule_success[language].format(
                button_type_cleaning[language] if type == 'cleaning' else button_type_medical[language],
                date.strftime('%d.%m, %A')),
            buttons=[Button.inline(button_back[language], data='back')]
        )


    # View all scheduled dates
    if data == 'general_schedule':
        # show a list of all scheduled dates
        if locale.getlocale(locale.LC_TIME)[0] == 'ru_RU':
            translated_dates = []
            for item in dates_list:
                for key, value in localized_dates['ru'].items():
                    item = item.replace(key, value)
                translated_dates.append(item)
        await event.edit(
            general_schedule[language].format(
                ', '.join(today_volunteers_list) if today_volunteers_list else '😿',
                '\n'.join(dates_list if locale.getlocale(locale.LC_TIME)[0] == 'en_US' else translated_dates)),
            buttons=[Button.inline(button_back[language], data='back')]
        )


    # Get back
    if data == 'back':
        await schedule_handler(event, language, update=True)

def main():
    bot.run_until_disconnected()

if __name__ == '__main__':
    main()