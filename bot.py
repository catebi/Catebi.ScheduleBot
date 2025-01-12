from telethon import TelegramClient, events, Button
import logging
import locale
from pyairtable import Api
from pyairtable.formulas import match
from datetime import datetime, timedelta

from settings import *
from translations import *
from airtable_model import *

logging.basicConfig(format='[%(levelname)s] %(message)s',
                    level=logging.WARNING)

# TODO:
# 0. Show a menu with language selection / done
#   - English (default) / done
#   - Russian / done
# 0.1. Read/register user with Airtable / done
#   - Check if user exists in Airtable / done
#   - Register user if not exists / not needed
#   - Get user's language from Airtable / done
# 1. Menu with inline buttons
#   - New scheduled date / done
#   - Delete scheduled date / deprecated
#   - View my scheduled dates / done
#   - View all scheduled dates / done
# 2. New scheduled date
#   - Show list of available dates with inline buttons, 2 weeks in advance / done
#   - Show number of sheduled volunteers on that date, "free" if none / done
#   - Hide dates that are already scheduled with two volunteers / done, + hide user's scheduled dates
#   - Show "Confirm" button / not needed
# 3. Delete scheduled date
#   - Show list of scheduled dates with inline buttons / done
#   - Show "Confirm" button / done
# 4. View my scheduled dates
#   - Show list of my scheduled dates / done
# 5. View all scheduled dates
#   - Show list of all scheduled dates / done
#   - Show who is scheduled on each date / done
#   - Show who is working today / done

def logger(func):
    def decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            logging.error(err, exc_info=True)
    return decorator

# Initialize Airtable API
api = Api(api_key=airtable_api_key)

bot = TelegramClient('catebi', api_id, api_hash).start(bot_token=bot_token)

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
        await event.edit("You are not a registered volunteer, please contact the administrator.")
        return

    else:
        # set user's language
        user.language = language
        user.save()

    await schedule_handler(event, language, update=True)


@bot.on(events.NewMessage(pattern='/help'))
@logger
async def help_handler(event):
    await event.respond("Help message.")

@bot.on(events.NewMessage(pattern='/settings'))
@logger
async def settings_handler(event):
    # show language selection menu
    await start_handler(event, check_user=False)

# region Menu

@bot.on(events.NewMessage(pattern='/schedule'))
@logger
async def schedule_handler(event, language: str = 'en', update: bool = False):
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    language = user.language if user else 'en'

    # get today's volunteers
    today_volunteers = Schedule.all(fields=['volunteer'], formula=match({'date': datetime.now().date()}))
    today_volunteers = ', '.join([volunteer.volunteer.telegram for volunteer in today_volunteers])

    buttons = [
        [Button.inline(button_new_schedule[language], data=f'new_schedule')],
        [Button.inline(button_my_schedule[language], data=f'my_schedule')],
        [Button.inline(button_general_schedule[language], data=f'general_schedule')]
    ]

    if update:
        await event.edit(main_menu[language].format(today_volunteers if today_volunteers else '😿'), buttons=buttons)
        return

    await event.respond(main_menu[language].format(today_volunteers if today_volunteers else '😿'), buttons=buttons)

# region Callbacks

@bot.on(events.CallbackQuery())
@logger
async def callback_handler(event):
    data = event.data.decode("utf-8")
    user = Volunteer.first(formula=match({'telegram_chat_id': event.sender.id}))
    language = user.language if user else 'en'
    locale.setlocale(locale.LC_TIME, 'ru_RU.utf8' if language == 'ru' else 'en_US.utf8')

    # Change user's language
    if data.startswith('language'):
        _, lang = data.split(':')
        # save user's language to Airtable
        await start_handler(event, check_user=True, language=lang)

    # New scheduled date
    if data == 'new_schedule':
        # prepare a list of available dates, from today to 2 weeks in advance
        available_dates = {}
        for i in range(14):
            date = datetime.now().date() + timedelta(days=i)
            available_dates[date] = {}
            available_dates[date]['volunteers'] = 0

        # check if the date is already scheduled by two volunteers, remove it from the list
        scheduled_dates = Schedule.all(fields=['date'])
        for date in scheduled_dates:
            if date.date in available_dates:
                available_dates[date.date]['volunteers'] += 1

        for date in available_dates.copy(): # copy the list to avoid RuntimeError
            if available_dates[date]['volunteers'] == 2:
                available_dates.pop(date)

        # check if the date is already scheduled by the user, remove it from the list
        user_scheduled_dates = Schedule.all(fields=['date'], formula=match({'telegram_chat_id': event.sender.id}))
        for date in user_scheduled_dates:
            if date.date in available_dates:
                available_dates.pop(date.date)

        # show a list of available dates
        buttons = [
            [Button.inline(f"{date.strftime('%d.%m, %A')} {'1️⃣' if available_dates[date]['volunteers'] == 1 else '🆓'}", data=f'add_schedule:{date}')] for date in available_dates
        ]
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(new_schedule_prompt[language], buttons=buttons)

    # Write a new scheduled date to Airtable
    if data.startswith('add_schedule'):
        _, date = data.split(':')
        date = datetime.strptime(date, '%Y-%m-%d').date()
        # add a new record to the Schedule table
        Schedule(
            telegram_chat_id=event.sender.id,
            date=date,
            telegram='@'+str(event.sender.username).lower(),
            volunteer=user
        ).save()
        await event.edit(add_schedule_success[language].format(date.strftime('%d.%m, %A')), buttons=[Button.inline(button_back[language], data='back')])

    # Delete a scheduled date from Airtable
    if data.startswith('delete_schedule:'):
        _, date = data.split(':')
        date = datetime.strptime(date, '%Y-%m-%d').date()
        # delete a record from the Schedule table
        unwanted_schedule = Schedule.first(formula=match({'telegram_chat_id': event.sender.id, 'date': date}))
        unwanted_schedule.delete()
        await event.edit(delete_schedule_success[language].format(date.strftime('%d.%m, %A')), buttons=[Button.inline(button_back[language], data='back')])

    # View my scheduled dates
    if data == 'my_schedule':
        # get a list of scheduled dates
        scheduled_dates = Schedule.all(fields=['date'], formula=match({'telegram_chat_id': event.sender.id}), sort=['date'])
        buttons = [
            [Button.inline(f"{date.date.strftime('%d.%m, %A')}", data=f'my_schedule_delete:{date.date}')] for date in scheduled_dates
        ]
        buttons.append([Button.inline(button_back[language], data='back')])
        await event.edit(my_schedule_prompt[language], buttons=buttons)

    # Ask to confirm the deletion of a scheduled date
    if data.startswith('my_schedule_delete:'):
        _, date = data.split(':')
        date = datetime.strptime(date, '%Y-%m-%d').date()
        buttons = [
            [Button.inline(button_yes[language], data=f'delete_schedule:{date}')],
            [Button.inline(button_back[language], data='back')]
        ]
        await event.edit(my_schedule_delete_prompt[language].format(date.strftime('%d.%m, %A')), buttons=buttons)


    # View all scheduled dates
    if data == 'general_schedule':
        # get a list of volunteers for today
        today_volunteers = Schedule.all(fields=['volunteer'], formula=match({'date': datetime.now().date()}))
        today_volunteers = ', '.join([volunteer.volunteer.telegram for volunteer in today_volunteers])

        # get a list of scheduled dates
        scheduled_dates = Schedule.all(fields=['date', 'volunteer'], sort=['date'])
        dates_list = []
        for date in scheduled_dates:
            dates_list.append(f"{date.date.strftime('%d.%m, %A')}: {date.volunteer.telegram}")

        buttons = [
            [Button.inline(button_back[language], data='back')]
        ]

        await event.edit(general_schedule[language].format(today_volunteers if today_volunteers else '😿', '\n'.join(dates_list)), buttons=buttons)


    # Get back
    if data == 'back':
        await schedule_handler(event, language, update=True)

def main():
    bot.run_until_disconnected()

if __name__ == '__main__':
    main()