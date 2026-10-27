# Структура баз Airtable (восстановлено из кода)

Источники: `airtable_model.py` (типы полей ORM) и обращения к полям в `bot.py`
(значения select'ов, ключи настроек, поля базы стерилизации).

Нужны **две** базы:

1. **Основная** (`AIRTABLE_BASE_ID`) — таблицы `volunteer`, `schedule`, `notification`, `settings`.
2. **Стерилизация** (`AIRTABLE_STERILIZATION_BASE_ID`) — таблица `cat_flat_fostering`.
   Опциональна: если id не задан, catflat-функции просто выходят (`return`), бот работает.

Имена таблиц и полей должны совпадать **буквально** (включая эмодзи в базе стерилизации) —
ORM и запросы обращаются к ним по строковому имени.

---

## Основная база

### Таблица `volunteer`
Волонтёры. Бот читает (в коде поля `telegram` и `telegram_chat_id` — readonly).

| Поле (Airtable)   | Тип Airtable                | Заметки |
|-------------------|-----------------------------|---------|
| `telegram`        | Single line text            | username без `@` |
| `telegram_chat_id`| Number (integer)            | числовой Telegram user id |
| `language`        | Single select               | опции: `en`, `ru` |
| `schedule_view`   | Single select               | опции: `today`, `general` |
| `duty_codes`      | Lookup (или Multiple select)| см. ниже — «Дежурства» |

**Дежурства (`duty_codes`).** В коде это lookup, но читается только как список строк
(`'kk_cleaning' in volunteer.duties`). Возможные коды:

- `kk_cleaning` — уборка
- `kk_medical` — медуход
- `kk_admin_curator` — куратор (получает алерты о пустых днях)
- `steril_cat_in_out` — приём/выписка со стерилизации

Два способа сделать поле:
- **Просто (для теста):** `duty_codes` = *Multiple select* с этими 4 опциями. Код делает
  только проверку вхождения — этого достаточно, поле нигде не пишется.
- **Как на проде:** отдельная таблица `duty` (поле-код + строки выше), link-поле на
  `volunteer` и lookup `duty_codes`, который тянет код из связанных записей.

### Таблица `schedule`
Записи на дежурства. Бот **читает и пишет**.

| Поле               | Тип Airtable        | Заметки |
|--------------------|---------------------|---------|
| `telegram`         | Single line text    | username |
| `telegram_chat_id` | Number (integer)    | |
| `date`             | Date (с временем)   | «Include time» = ON |
| `volunteer`        | Link → `volunteer`  | одиночная связь |
| `type`             | Single select       | опции ниже |

Опции `type`: `cleaning`, `cleaning_catloft`, `medical`, `steril_acceptance`, `steril_release`.

### Таблица `notification`
Настройки уведомлений кураторов. Бот читает и пишет.

| Поле                   | Тип Airtable        | Заметки |
|------------------------|---------------------|---------|
| `admin_curator`        | Single line text    | |
| `volunteer`            | Link → `volunteer`  | одиночная связь |
| `telegram_chat_id`     | Number (integer)    | chat id куратора |
| `notify_at`            | Single line text    | время в формате `HH:MM`, напр. `09:00` |
| `custom_text_cleaning` | Long text           | кастомный текст для уборки |
| `custom_text_medical`  | Long text           | кастомный текст для медухода |
| `date_threshold`       | Single line text    | содержит `+N` дней, напр. `today+3` (код берёт число после `+`) |

### Таблица `settings`
Хранилище «ключ-значение». Все значения — числа (Telegram id / message id).

| Поле         | Тип Airtable | Заметки |
|--------------|--------------|---------|
| `key`        | Single line text | имя параметра |
| `value`      | Number (integer) | значение (боевое) |
| `test_value` | Number (integer) | тестовое значение (есть в модели) |

Каждый параметр — отдельная строка. Ключи, которые читает код:

| `key`                             | Что это |
|-----------------------------------|---------|
| `topic_chat_id`                   | id супергруппы **без префикса `-100`** (код сам добавляет `-100`) — обязателен, иначе `update_volunteers` выходит с ошибкой |
| `cleaning_topic_id`               | id топика «уборка» |
| `medical_topic_id`                | id топика «медуход» |
| `steril_cat_topic_id`             | id топика «стерилизация/котодом» |
| `process_notification_topic_id`   | id топика для catflat-уведомлений |
| `last_pinned_general_message_id`  | id последнего закреплённого сообщения (общее) |
| `last_pinned_cleaning_message_id` | то же для уборки |
| `last_pinned_medical_message_id`  | то же для медухода |
| `last_pinned_steril_message_id`   | то же для стерилизации |

`last_pinned_*` бот выставляет сам. Для старта достаточно задать `topic_chat_id`
(и id топиков, если хотите проверять постинг в темы).

---

## База стерилизации (опционально)

### Таблица `cat_flat_fostering`
Только чтение. Запрашиваемые поля:

| Поле                | Тип Airtable      | Заметки |
|---------------------|-------------------|---------|
| `request_id`        | Number или text   | номер заявки |
| `request_record_id` | Single line text  | id записи заявки (для ссылки в softr) |
| `record_id`         | Single line text  | |
| `status`            | Single select     | опции ниже |
| `room`              | Single line text  | комната котодома (группировка) |
| `in_date`           | Date (с временем)  | дата приёма |
| `sterilization_date`| Date (с временем)  | дата стерилизации |
| `required_vaccination` | text/number    | |
| `is_test`           | Checkbox          | тестовые записи отфильтровываются (`is_test = false`) |
| `💊 med_care`       | Checkbox          | имя поля с эмодзи и пробелом — буквально |
| `🦟is_deflead`      | Checkbox          | |
| `💉is_vaccinated`   | Checkbox          | |
| `𓆑is_dewormed`     | Checkbox          | |

Опции `status` (по ним идёт фильтр): `принята в кд`, `ожидает стерилизацию`,
`готова к выписке`, `назначен медуход`.

---

## Минимум, чтобы бот поднялся

- `volunteer` — добавьте себя: `telegram` (ваш username), `telegram_chat_id` (ваш id),
  `language` = `ru`/`en`, `schedule_view` = `today`, `duty_codes` = нужные роли.
- `settings` — как минимум строка `topic_chat_id` = id вашей тестовой супергруппы (без `-100`).
- `schedule` / `notification` — можно оставить пустыми, наполнятся при использовании.
- База стерилизации — можно не создавать (не задавайте `AIRTABLE_STERILIZATION_BASE_ID`).
