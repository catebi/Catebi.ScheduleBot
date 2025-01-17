# region Messages
start_message = {
    'en': "Start message.",
    'ru': "Стартовое сообщение."
}

help_message = {
    'ru': """Этот бот поможет вам записываться и отслеживать дежурства в Catebi.

Функции бота:
📝 Записаться на дежурство - выберите дату и запишитесь на желаемую смену! Дата недоступна для записи, если вы на неё уже записаны, или на неё зарегистрированы 2 смены уборки.
📅 Посмотреть свое расписание - нажмите на дату в списке чтобы удалить её из расписания.
📋 Посмотреть общее расписание - ознакомьтесь с общим расписанием и спланируйте когда хотите заступить на смену.

Эмодзи 🏥 в расписании значит, что это смена на медуход.

Команды бота:
/schedule - главное меню
/settings - настройки бота (язык)
/help - это сообщение
""",
    'en': """This bot will help you sign up and track your shifts at Catebi.

Bot functions:
📝 Sign up for a shift - choose a date and sign up for the desired shift! The date is unavailable for registration if you are already signed up for it, or if there are 2 cleaning shifts registered for it.
📅 View your schedule - click on a date in the list to delete it from the schedule.
📋 View the general schedule - check the general schedule and plan when you want to take a shift.

The 🏥 emoji in the schedule means that it is a medical shift.

Bot commands:
/schedule - main menu
/settings - bot settings (language)
/help - this message
"""
}

language_selection = {
    'en': "Please select your language.",
    'ru': "Пожалуйста, выберите язык."
}

languages = {
    'en': "🇺🇸 English",
    'ru': "🇷🇺 Русский"
}

main_menu = {
    'en': "Main menu 😽\n\nToday's volunteers: {}",
    'ru': "Главное меню 😽\n\nДежурства сегодня: {}"
}

new_schedule_type_prompt = {
    'en': "❓ Choose a type of duty you want to sign up for.",
    'ru': "❓ Выберите тип дежурства, на которое хотите записаться."
}

new_schedule_prompt = {
    'en': "Choose a date you want to sign up for.\n\nP.S. The date is hidden if there's two volunteers already signed up for it.",
    'ru': "Выберите дату, на которую хотите записаться.\n\nP.S. Дата скрыта, если на нее уже записались два волонтера."
}

add_schedule_success = {
    'en': "Yay! You have successfully signed up for: **{}** on **{}**!",
    'ru': "Ура! Вы записаны: **{}** на **{}**!"
}

delete_schedule_prompt = {
    'en': "Choose a date you want to delete.",
    'ru': "Выберите дату, которую хотите удалить."
}

delete_schedule_success = {
    'en': "You have successfully deleted your **{}** registration for **{}**.",
    'ru': "Вы успешно удалили свою запись **{}** на **{}**."
}

my_schedule_prompt = {
    'en': "📅Your schedule.\nClick on a date to delete registration.",
    'ru': "📅Ваше расписание.\nНажмите на дату чтобы удалить регистрацию."
}

my_schedule_delete_prompt = {
    'en': "Do you want to delete your **{}** registration for **{}**?",
    'ru': "Вы хотите удалить свою запись **{}** на **{}**?"
}

general_schedule = {
    'en': """📋General schedule:

Today's volunteers: {}

Other dates:
{}
""",

    'ru': """📋Общее расписание:

Дежурства сегодня: {}

Другие даты:
{}
"""
}

localized_dates = {
    'ru': {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье"
    },
}

# region Buttons

button_new_schedule = {
    'en': "📝 Sign up",
    'ru': "📝 Записаться"
}

button_type_cleaning = {
    'en': "🧹 Cleaning",
    'ru': "🧹 Уборка"
}

button_type_medical = {
    'en': "🏥 Medical",
    'ru': "🏥 Медуход"
}

button_my_schedule = {
    'en': "📅 My schedule",
    'ru': "📅 Мое расписание"
}

button_general_schedule = {
    'en': "📋 General schedule",
    'ru': "📋 Общее расписание"
}

button_back = {
    'en': "⬅️ Back",
    'ru': "⬅️ Назад"
}

button_yes = {
    'en': "✅ Yes",
    'ru': "✅ Да"
}


# region Error messages
error_not_registered = {
    'en': "You are not a registered volunteer. Please contact the administrator.",
    'ru': "Вы не зарегистрированный волонтер. Пожалуйста, свяжитесь с администратором."
}