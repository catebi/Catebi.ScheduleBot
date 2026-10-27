# region Messages
help_message = {
    "ru": """Этот бот поможет вам записываться и отслеживать дежурства в Catebi.

Функции бота:
📝 Записаться на дежурство - выберите дату и запишитесь на желаемую смену! Дата недоступна для записи, если вы на неё уже записаны, или на неё зарегистрированы 2 смены уборки.
📅 Посмотреть свое расписание - нажмите на дату в списке чтобы удалить её из расписания.
📋 Посмотреть общее расписание - ознакомьтесь с общим расписанием и спланируйте когда хотите заступить на смену.

Эмодзи 🏥 в расписании значит, что это смена на медуход.

Команды бота:
/schedule - главное меню
/settings - настройки бота (язык, вид расписания)
/help - это сообщение
""",
    "en": """This bot will help you sign up and track your shifts at Catebi.

Bot functions:
📝 Sign up for a shift - choose a date and sign up for the desired shift! The date is unavailable for registration if you are already signed up for it, or if there are 2 cleaning shifts registered for it.
📅 View your schedule - click on a date in the list to delete it from the schedule.
📋 View the general schedule - check the general schedule and plan when you want to take a shift.

The 🏥 emoji in the schedule means that it is a medical shift.

Bot commands:
/schedule - main menu
/settings - bot settings (language, default view)
/help - this message
""",
}

language_selection = {"en": "Please select your language.", "ru": "Пожалуйста, выберите язык."}

languages = {"en": "🇺🇸 English", "ru": "🇷🇺 Русский"}

settings_overview = {
    "en": "Your current settings are:\n\n__Language:__ {}\n__Default view:__ **{}**",
    "ru": "Ваши текущие настройки:\n\n__Язык:__ {}\n__Вид расписания:__ **{}**",
}

settings_view = {
    "today": {"en": "Today only", "ru": "Только сегодня"},
    "general": {"en": "General schedule", "ru": "Общее расписание"},
}

settings_view_prompt = {
    "en": "Please select the view you want to switch to.\n\n__Today only__ - shows only today's date (default).\n__General schedule__ - shows the full schedule with all dates.\n\nYour current view is: **{}**",
    "ru": "Пожалуйста, выберите вид, на который хотите переключиться.\n\n__Только сегодня__ - показывает только сегодняшнюю дату (по-умолчанию).\n__Общее расписание__ - показывает полное расписание со всеми датами.\n\nВаш текущий вид: **{}**",
}

settings_view_success = {
    "en": "Your view has been successfully changed to: **{}**",
    "ru": "Ваш вид был успешно изменен на: **{}**",
}

# Loading messages
loading_text = {"en": "⏳ Loading...", "ru": "⏳ Загрузка..."}

main_menu_header = {"en": "Main menu 😽", "ru": "Главное меню 😽"}

todays_volunteers = {"en": "Today's volunteers, {}: {}", "ru": "Дежурные сегодня, {}: {}"}

new_schedule_type_prompt = {
    "en": "❓ Choose a type of duty you want to sign up for.",
    "ru": "❓ Выберите тип дежурства, на которое хотите записаться.",
}

new_schedule_cleaning_location_prompt = {"en": "Where do you want to clean?", "ru": "Где вы хотите провести уборку?"}

new_schedule_prompt = {
    "en": "Choose a date you want to sign up for **{}**\n\nP.S. The date is hidden if there's enough volunteers already signed up for it.",
    "ru": "Выберите дату для смены **{}**, на которую хотите записаться.\n\nP.S. Дата скрыта, если на нее уже записались достаточно волонтёров.",
}

set_schedule_time_prompt = {
    "en": "Please choose the time you want to sign up on **{}**",
    "ru": "Пожалуйста, выберите время, на которое хотите записаться на **{}**",
}

add_schedule_success = {
    "en": "Yay! You have successfully signed up for: **{}** on **{}** on **{}**!",
    "ru": "Ура! Вы записаны: **{}** на **{}** в **{}**!",
}

add_schedule_success_steril_acceptance = {
    "en": "Yay! You have successfully signed up for: **{}** on **{}**!",
    "ru": "Ура! Вы записаны: **{}** на **{}**!",
}

add_schedule_topic_message = {
    "en": "{} {} signed up for {} duty on **{}** at **{}** 🎉",
    "ru": "{} {} записалась/ся на дежурство по {} на **{}** в **{}** 🎉",
}

add_schedule_topic_steril_acceptance_message = {
    "en": "{} {} signed up for cat acceptance on **{}** 🎉",
    "ru": "{} {} записалась/ся на приемку кошек на **{}** 🎉",
}

delete_schedule_success = {
    "en": "You have successfully deleted your **{}** registration for **{}** on **{}**.",
    "ru": "Вы успешно удалили свою запись **{}** на **{}** в **{}**.",
}

delete_schedule_success_steril_acceptance = {
    "en": "You have successfully deleted your **{}** registration for **{}**.",
    "ru": "Вы успешно удалили свою запись **{}** на **{}**.",
}

delete_schedule_topic_message = {
    "en": "⛔{} {} cancelled their {} duty on **{}** at **{}** 😿",
    "ru": "⛔{} {} удалил/а свою запись на дежурство по {} на **{}** в **{}** 😿",
}

delete_schedule_topic_steril_acceptance_message = {
    "en": "⛔{} {} cancelled their cat acceptance sign-up on **{}** 😿",
    "ru": "⛔{} {} удалил/а свою запись на приемку кошек на **{}** 😿",
}

my_schedule_prompt = {
    "en": "📅Your schedule.\nClick on a date to delete registration.",
    "ru": "📅Ваше расписание.\nНажмите на дату чтобы удалить регистрацию.",
}

my_schedule_delete_prompt = {
    "en": "Do you want to delete your **{}** registration for **{}** on **{}**?",
    "ru": "Вы хотите удалить свою запись **{}** на **{}** в **{}**?",
}

my_schedule_delete_prompt_steril_acceptance = {
    "en": "Do you want to delete your **{}** registration for **{}**?",
    "ru": "Вы хотите удалить свою запись **{}** на **{}**?",
}

general_schedule = {
    "en": """📆 CatFlat schedule

Today's volunteers, {}: {}

Other dates:
{}
""",
    "ru": """📆 Дежурства в кото-квартире

Дежурства сегодня, {}: {}

Другие даты:
{}
""",
}

localized_dates = {
    "ru": {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье",
    },
}

notifications_menu = {
    "en": "🔔 Notifications menu.\n\nYour current settings are:\n__Cleaning notification text:__\n{}\n\n__Medical notification text:__\n{}\n\n__Notify at: **{}**__\n__Checking date range: **{}** (between today and **{}**)__",
    "ru": "🔔 Меню уведомлений.\n\nВаши текущие настройки:\n__Текст уведомления о уборке:__\n{}\n\n__Текст уведомления о медицинских сменах:__\n{}\n\n__Время оповещения: **{}**__\n__Промежуток проверяемых дней: **{}** (между сегодня и **{}**)__",
}

notifications_settings_text_menu = {
    "en": "🔔 Custom text notifications menu.\nPlease choose the notification type you want to customize.",
    "ru": "🔔 Меню настроек текста уведомлений.\nПожалуйста, выберите тип уведомления, который хотите настроить.",
}

default_cleaning_notification_text = {
    "en": "There's no cleaning volunteer assigned for **{}**. If you have 1.5 hours, please sign up for a light cleaning. You need to clean the litter boxes, refresh the water, and add food, that's all!",
    "ru": "На дату **{}** нет дежурного по уборке. Если у тебя есть 1.5 часа, пожалуйста, запишись на лайт вариант уборки. Нужно почистить лотки, обновить воду и досыпать корм, всё!",
}

default_medical_notification_text = {
    "en": "There's no medical volunteer assigned for **{}**. Please sign up for a medical shift if you can 😸",
    "ru": "На дату **{}** нет дежурного по медуходу. Пожалуйста, запишитесь на смену, если можете 😸",
}

notifications_settings_text_prompt = {
    "en": "Please enter your custom notification text.\n\nYou can use curly braces **{}** to insert the date in your text. The date will be inserted automatically, leave curly braces empty.",
    "ru": "Пожалуйста, введите свой текст уведомления.\n\nВы можете использовать фигурные скобочки **{}** для вставки даты в ваш текст. Дата будет вставлена автоматически, оставьте фигурные скобочки пустыми.",
}

notifications_settings_text_success = {
    "en": "You have successfully set your custom notification text!",
    "ru": "Вы успешно установили свой текст уведомления!",
}

notifications_settings_notify_at_prompt = {
    "en": "Please choose the time you want to receive the notification about shift shortage.",
    "ru": "Пожалуйста, выберите время, когда вы хотите получать оповещения о недостатке дежурных.",
}

notifications_settings_notify_at_success = {
    "en": "You have successfully set the notification time to **{}**!",
    "ru": "Вы успешно установили время оповещения на **{}**!",
}

notifications_settings_date_threshold_prompt = {
    "en": "Select the number of days in advance you want to receive a notification if there are no shifts scheduled.\nThis is a range between today and the selected threshold, you will receive a noification for the earliest empty date in this range.",
    "ru": "Выберите количество дней, за которые вы хотите получать оповещение если нет назначенных смен.\nЭто диапазон между сегодняшней датой и выбранным остатком, вы получите уведомление для ближайшей незанятой даты в этом диапазоне.",
}

notifications_settings_date_threshold_success = {
    "en": "You have successfully set the date threshold to **{}** {}!",
    "ru": "Вы успешно установили остаток дней до дежурства на **{}** {}!",
}

notifications_send_menu = {
    "en": "🔔 Notifications send menu.\n\nPlease choose the type of volunteers you want to notify.\n\n__NOTE: If date is set in the notification text, notifications sent from this menu will contain **your threshold** date!__",
    "ru": "🔔 Меню отправки уведомлений.\n\nПожалуйста, выберите тип волонтеров, которых хотите уведомить.\n\n__ПРИМЕЧАНИЕ: Если в тексте уведомления установлена дата, то уведомление, разосланное из этого меню, будет содержать дату **вашего остатка дней** до дежурства!__",
}

notifications_send_success = {
    "en": "The notification has been sent successfully!\n\nSent to **{}** volunteers out of **{}**.",
    "ru": "Уведомление успешно отправлено!\n\nОтправлено **{}** волонтерам из **{}**.",
}

notifications_no_volunteers_at_all = {
    "en": "There are no volunteers registered for **{}**!",
    "ru": "На дату **{}** нет зарегистрированных волонтеров!",
}

notifications_no_cleaning_volunteers = {
    "en": "There are no cleaning volunteers registered for **{}**!",
    "ru": "На дату **{}** нет зарегистрированных волонтеров по уборке!",
}

notifications_no_medical_volunteers = {
    "en": "There are no medical volunteers registered for **{}**!",
    "ru": "На дату **{}** нет зарегистрированных волонтеров по медуходу!",
}

notifications_steril_message = {
    "en": "Volunteers needed for **🔃 Cat acceptance-release** on **{}** and **{}**!\n\n**{}** — 2 volunteers for acceptance\n**{}** — 1 volunteer for release, any time!\n**{}** — 3 volunteers for acceptance of cats from the clinic",
    "ru": "Нужны дежурные для **🔃 Приемки-выдачи кошек** на **{}** и **{}**!\n\n**{}** — 2 волонтера для приемки\n**{}** — 1 волонтер для выдачи, в любое время!\n**{}** — 3 волонтера для приемки кошек из клиники",
}

notifications_steril_curator_dates_prompt = {
    "en": "Please choose the dates for **🔃 Cat acceptance-release**.\n\nYou can choose given dates or choose your own dates.",
    "ru": "Пожалуйста, выберите даты для **🔃 Приемки-выдачи кошек**.\n\nВы можете выбрать предложенные даты или выбрать свои собственные.",
}

notifications_steril_curator_confirm_prompt = {
    "en": "Your notification will look like this:\n\n{}\n\nPlease confirm to send, or go back to edit the dates.",
    "ru": "Ваше уведомление будет выглядеть так:\n\n{}\n\nПожалуйста, подтвердите отправку, или вернитесь назад, чтобы изменить даты.",
}

notifications_steril_curator_start_date_prompt = {
    "en": "Please choose the start date for **🔃 Cat acceptance-release**.\nThe end date will be **+1** day of the chosen date.",
    "ru": "Пожалуйста, выберите начальную дату для **🔃 Приемки-выдачи кошек**.\nДата окончания будет **+1** день от выбранной даты.",
}

notifications_steril_volunteer_acceptance_prompt = {
    "en": "Please choose the date you want to sign up for **⬇️ Cat acceptance**.",
    "ru": "Пожалуйста, выберите дату, на которую вы хотите записаться для **⬇️ Приемки кошек**.",
}

notifications_steril_volunteer_release_date_prompt = {
    "en": "Please choose the date you want to sign up for **⬆️ Cat release**.",
    "ru": "Пожалуйста, выберите дату, на которую вы хотите записаться для **⬆️ Выдачи кошек**.",
}

# region Buttons

button_new_schedule = {"en": "📝 Sign up", "ru": "📝 Записаться"}

button_type_cleaning = {"en": "🧹 Cleaning", "ru": "🧹 Уборка"}

button_type_cleaning_location = {
    "en": {"catflat": "🧹🏠 CatFlat", "catloft": "🧹🪜 CatLoft"},
    "ru": {"catflat": "🧹🏠 Котоквартира", "catloft": "🧹🪜 Котолофт"},
}

button_type_medical = {"en": "🏥 Medical", "ru": "🏥 Медуход"}

button_type_steril_acceptance = {"en": "⬇️ Cat acceptance", "ru": "⬇️ Приемка кошек"}

button_type_steril_release = {"en": "⬆️ Cat release", "ru": "⬆️ Выдача кошек"}

button_my_schedule = {"en": "📅 My schedule", "ru": "📅 Мое расписание"}

button_general_schedule = {"en": "📋 General schedule", "ru": "📋 Общее расписание"}

button_notifications = {"en": "🔔 Notifications", "ru": "🔔 Уведомления"}

button_notifications_steril = {
    "en": "🔔 Create new accept-release notification",
    "ru": "🔔 Создать новое уведомление по приему-выдаче",
}

button_steril_accept_acceptance = {"en": "⬇️ Sign up for a cat acceptance", "ru": "⬇️ Записаться на приемку кошек"}

button_steril_accept_release = {"en": "⬆️ Sign up for a cat release", "ru": "⬆️ Записаться на выдачу кошек"}

button_steril_own_dates = {"en": "📅 Choose your own dates", "ru": "📅 Выбрать свои даты"}

button_back = {"en": "⬅️ Back", "ru": "⬅️ Назад"}

button_yes = {"en": "✅ Yes", "ru": "✅ Да"}

button_notifications_settings_text_menu = {
    "en": "📝 Custom text notifications menu",
    "ru": "📝 Меню настроек текста уведомлений",
}

button_notifications_settings_cleaning_text = {
    "en": "📝 Set custom text for cleaning",
    "ru": "📝 Установить свой текст для уборки",
}

button_notifications_settings_medical_text = {
    "en": "📝 Set custom text for medical",
    "ru": "📝 Установить свой текст для медухода",
}

button_notifications_text_reset = {"en": "🔄 Reset to default text", "ru": "🔄 Сбросить текст на стандартный"}

button_notifications_settings_notify_at = {"en": "⏰ Set notify time", "ru": "⏰ Установить время оповещения"}

button_notifications_settings_date_threshold = {"en": "📅 Set date threshold", "ru": "📅 Установить остаток дней"}

button_notifications_send_menu = {"en": "📤 Send now menu", "ru": "📤 Меню отправки"}

button_curator_notifications_send_all = {"en": "📤 Notify all volunteers", "ru": "📤 Уведомить всех"}

button_curator_notifications_send_cleaning = {
    "en": "📤 Notify cleaning volunteers",
    "ru": "📤 Уведомить волонтеров по уборке",
}

button_curator_notifications_send_medical = {
    "en": "📤 Notify medical volunteers",
    "ru": "📤 Уведомить волонтеров по медуходу",
}

button_curator_ignore = {"en": "🚫 Ignore", "ru": "🚫 Игнорировать"}

button_change_language = {"en": "🌐 Change language", "ru": "🌐 Изменить язык"}

button_change_view = {"en": "📆 Change default schedule view", "ru": "📆 Изменить вид расписания по-умолчанию"}

# region Error messages
error_not_registered = {
    "en": "You are not a registered volunteer. Please contact the administrator.",
    "ru": "Вы не зарегистрированный волонтер. Пожалуйста, свяжитесь с администратором.",
}

error_no_duties = {
    "en": "Oh! Looks like you don't have the necessary duties to use this bot.\nPlease check in with the [volunteer bot](https://t.me/catebi_volunteer_bot) to get started!",
    "ru": "Ой! Похоже, у вас нет необходимых ролей для использования этого бота.\nПожалуйста, отметьтесь в [волонтерском боте](https://t.me/catebi_volunteer_bot), чтобы начать!",
}

error_not_admin = {
    "en": "This command is only available to administrators.",
    "ru": "Эта команда доступна только администраторам.",
}

error_custom_text = {
    "en": "Your message can't start with a slash, please try again.",
    "ru": "Ваше сообщение не может начинаться со слеша, пожалуйста, попробуйте еще раз.",
}

# Generic fallback shown when a callback handler fails unexpectedly. Bilingual
# because the user's language may not be resolved at the point of failure.
error_generic = "⚠️ Что-то пошло не так, попробуйте ещё раз.\n⚠️ Something went wrong, please try again."

# region Topic message fragments
# These plug into the *_topic_message templates above. The topic messages are
# posted to shared Russian-language group topics, so call sites use the "ru"
# variant; the "en" values are provided for consistency.

# Relative-day words for the topic messages.
topic_relative_day = {
    "en": {"today": "today", "tomorrow": "tomorrow"},
    "ru": {"today": "сегодня", "tomorrow": "завтра"},
}

# Duty descriptions (dative case in ru) for the schedule topic messages.
topic_duty_word = {
    "en": {
        "medical": "medical care",
        "cleaning": "cleaning the cat flat",
        "cleaning_catloft": "cleaning the cat loft",
        "steril": "cat release",
    },
    "ru": {
        "medical": "медуходу",
        "cleaning": "уборке в котоквартире",
        "cleaning_catloft": "уборке в котолофте",
        "steril": "выдаче кошков",
    },
}

# DM sent to the curator when a volunteer signs up for acceptance/release.
curator_new_steril_signup = {
    "en": "🔔 New sign-up for cat {} from {} on {}.",
    "ru": "🔔 Новая запись на {} кошков от {} на {}.",
}
curator_steril_word = {
    "en": {"acceptance": "acceptance", "release": "release"},
    "ru": {"acceptance": "приёмку", "release": "выдачу"},
}

# region Cat-flat overview texts (posted to a Russian-language topic)
catflat_days_in = {"en": "{} days in ", "ru": "{} дн в "}
catflat_days_unknown = {"en": "time in ", "ru": "срок пребывания в "}
catflat_link_label = {"en": "cf", "ru": "кд"}
catflat_overview_header = {
    "en": "📋 {} cats in the cat flat ({}/{}, {}%🪫)",
    "ru": "📋 {} кошек в котодоме ({}/{}, {}%🪫)",
}
catflat_overview_empty = {"en": "📋 no cats in the cat flat (0%)", "ru": "📋 нет кошек в котодоме (0%)"}
catflat_schedule_cleaning = {"en": "🧹 cleaning today: {}", "ru": "🧹 уборка сегодня: {}"}
catflat_schedule_cleaning_none = {"en": "🧹 cleaning today: ❗️no volunteers", "ru": "🧹 уборка сегодня: ❗️нет дежурных"}
catflat_schedule_medical = {"en": "🏥 medical today: {}", "ru": "🏥 медуход сегодня: {}"}
catflat_schedule_medical_none = {"en": "🏥 medical today: ❗️no volunteer", "ru": "🏥 медуход сегодня: ❗️нет дежурного"}

# Full "days in cat flat" phrases (кд is inline text, not a link, in these).
catflat_days_in_full = {"en": "{} days in cf", "ru": "{} дн в кд"}
catflat_days_unknown_full = {"en": "time in cf unknown", "ru": "срок пребывания в кд неизвестен"}

# region Medical notification (posted to a Russian-language topic)
medical_duty_today = {"en": "medical volunteer today {}, at {}", "ru": "дежурный медухода сегодня {}, в {}"}
medical_duty_none = {"en": "❗️no medical volunteer for today", "ru": "❗️на сегодня нет дежурного по медуходу"}
medical_attention_header = {
    "en": "⚠️ cats in the cat flat untreated or needing medical care",
    "ru": "⚠️ кошки в котодоме без обработки или на медуход",
}
medical_all_clear = {
    "en": "🎉 all cats in the cat flat are treated and need no medical care",
    "ru": "🎉 все кошки в котодоме обработаны и не нуждаются в медуходе",
}

# region Cat-flat changes notification (posted to a Russian-language topic)
changes_no_prev_state = {
    "en": "ℹ️ Changes can't be determined: no previous state found. This may be the first run.",
    "ru": "ℹ️ Изменения не могут быть определены: предыдущее состояние не найдено. Это может быть первый запуск.",
}
changes_bad_prev_state = {
    "en": "❌ Error reading the previous state. Check the cat_flat_state.json file.",
    "ru": "❌ Ошибка при чтении предыдущего состояния. Проверьте файл cat_flat_state.json.",
}
changes_header = {"en": "📊 changes in the cat flat", "ru": "📊 изменения в котоквартире"}
changes_none = {"en": "✅ no changes detected", "ru": "✅ изменений не обнаружено"}
changes_new = {"en": "🆕 <b>arrived in the cat flat:</b>", "ru": "🆕 <b>появились в котоквартире:</b>"}
changes_departed = {"en": "🚙 <b>left the cat flat:</b>", "ru": "🚙 <b>выехали из котоквартиры:</b>"}
changes_status = {"en": "🔄 <b>status changes:</b>", "ru": "🔄 <b>изменения статуса:</b>"}
changes_medical = {"en": "💊 <b>medical treatment:</b>", "ru": "💊 <b>медобработка:</b>"}
