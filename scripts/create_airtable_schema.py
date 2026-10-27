#!/usr/bin/env python3
"""
Создаёт структуру Airtable для Catebi.ScheduleBot через Meta API.

Что делает:
  1. Создаёт новую базу (в указанном workspace) ИЛИ дополняет существующую.
  2. Заводит таблицы volunteer / schedule / notification / settings со всеми
     полями и select-опциями (см. AIRTABLE_SCHEMA.md).
  3. Вторым проходом добавляет link-поля `volunteer` в schedule и notification
     (в create-запросе их создать нельзя — нужен id таблицы volunteer).
  4. Опционально создаёт базу стерилизации с таблицей cat_flat_fostering.
  5. Печатает готовый фрагмент для .env.local.

Идемпотентность: существующие таблицы/поля пропускаются (не дублируются).

Требуется PAT со scope:
  - schema.bases:write   (создание таблиц/полей)
  - schema.bases:read
  - и доступ Creator к workspace, если создаёте новую базу.

Установка зависимости:  pip install requests

Примеры:
  # создать новую базу в workspace
  export AIRTABLE_PAT=patXXXX
  python scripts/create_airtable_schema.py --workspace wspXXXX --name "ScheduleBot TEST"

  # дополнить существующую базу
  python scripts/create_airtable_schema.py --base appXXXX

  # + отдельная база стерилизации
  python scripts/create_airtable_schema.py --workspace wspXXXX --with-sterilization
"""
import argparse
import os
import sys
import json

try:
    import requests
except ImportError:
    sys.exit("Нужен пакет requests:  pip install requests")

API = "https://api.airtable.com/v0/meta"


# ---------- определения полей (без link — они добавляются вторым проходом) ----------

def text(name):        return {"name": name, "type": "singleLineText"}
def longtext(name):    return {"name": name, "type": "multilineText"}
def number(name):      return {"name": name, "type": "number", "options": {"precision": 0}}
def checkbox(name):    return {"name": name, "type": "checkbox",
                               "options": {"icon": "check", "color": "greenBright"}}
def datetime_(name):   return {"name": name, "type": "dateTime",
                               "options": {"dateFormat": {"name": "iso"},
                                           "timeFormat": {"name": "24hour"},
                                           "timeZone": "client"}}
def single_select(name, choices):
    return {"name": name, "type": "singleSelect",
            "options": {"choices": [{"name": c} for c in choices]}}
def multi_select(name, choices):
    return {"name": name, "type": "multipleSelects",
            "options": {"choices": [{"name": c} for c in choices]}}


DUTY_CODES = ["kk_cleaning", "kk_medical", "kk_admin_curator", "steril_cat_in_out"]
SCHEDULE_TYPES = ["cleaning", "cleaning_catloft", "medical",
                  "steril_acceptance", "steril_release"]
STERIL_STATUSES = ["принята в кд", "ожидает стерилизацию",
                   "готова к выписке", "назначен медуход"]

# Первое поле каждой таблицы становится primary — тип должен быть допустим
# для primary (text / number и т.п., НЕ select / checkbox / link).
MAIN_TABLES = [
    {
        "name": "volunteer",
        "fields": [
            text("telegram"),                       # primary
            number("telegram_chat_id"),
            single_select("language", ["en", "ru"]),
            single_select("schedule_view", ["today", "general"]),
            multi_select("duty_codes", DUTY_CODES),  # на проде — lookup; для теста хватит multi-select
        ],
    },
    {
        "name": "schedule",
        "fields": [
            text("telegram"),                       # primary
            number("telegram_chat_id"),
            datetime_("date"),
            single_select("type", SCHEDULE_TYPES),
            # link `volunteer` -> добавляется во 2-м проходе
        ],
    },
    {
        "name": "notification",
        "fields": [
            text("admin_curator"),                  # primary
            number("telegram_chat_id"),
            text("notify_at"),                      # формат HH:MM
            longtext("custom_text_cleaning"),
            longtext("custom_text_medical"),
            text("date_threshold"),                 # содержит +N дней, напр. today+3
            # link `volunteer` -> добавляется во 2-м проходе
        ],
    },
    {
        "name": "settings",
        "fields": [
            text("key"),                            # primary
            number("value"),
            number("test_value"),
        ],
    },
]

STERIL_TABLES = [
    {
        "name": "cat_flat_fostering",
        "fields": [
            text("request_id"),                     # primary
            text("request_record_id"),
            text("record_id"),
            single_select("status", STERIL_STATUSES),
            text("room"),
            datetime_("in_date"),
            datetime_("sterilization_date"),
            text("required_vaccination"),
            checkbox("is_test"),
            checkbox("💊 med_care"),
            checkbox("🦟is_deflead"),
            checkbox("💉is_vaccinated"),
            checkbox("𓆑is_dewormed"),
        ],
    },
]

# link-поля: (таблица, имя поля, целевая таблица)
LINK_FIELDS = [
    ("schedule", "volunteer", "volunteer"),
    ("notification", "volunteer", "volunteer"),
]


# ---------------------------- HTTP-обёртка ----------------------------

def call(method, path, token, body=None):
    r = requests.request(
        method, f"{API}{path}",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        data=json.dumps(body) if body is not None else None,
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"[{r.status_code}] {method} {path}\n{r.text}")
    return r.json() if r.text else {}


def get_schema(base_id, token):
    """Вернуть {table_name: {'id':..., 'fields': set(field_names)}}."""
    data = call("GET", f"/bases/{base_id}/tables", token)
    out = {}
    for t in data.get("tables", []):
        out[t["name"]] = {"id": t["id"],
                          "fields": {f["name"] for f in t.get("fields", [])}}
    return out


# ---------------------------- логика ----------------------------

def ensure_base(token, tables, base_id, workspace_id, name):
    """Создать базу с таблицами ИЛИ дополнить существующую. Вернуть base_id."""
    if base_id:
        print(f"→ Дополняю существующую базу {base_id}")
        existing = get_schema(base_id, token)
        for tbl in tables:
            if tbl["name"] in existing:
                print(f"  = таблица '{tbl['name']}' уже есть — пропуск")
                continue
            call("POST", f"/bases/{base_id}/tables", token,
                 {"name": tbl["name"], "fields": tbl["fields"]})
            print(f"  + таблица '{tbl['name']}' создана")
        return base_id

    if not workspace_id:
        raise SystemExit("Укажите либо --base appXXXX, либо --workspace wspXXXX")

    print(f"→ Создаю новую базу '{name}' в workspace {workspace_id}")
    resp = call("POST", "/bases", token,
                {"name": name, "workspaceId": workspace_id, "tables": tables})
    print(f"  + база создана: {resp['id']}")
    return resp["id"]


def ensure_links(token, base_id, link_fields):
    schema = get_schema(base_id, token)
    for src_table, field_name, target_table in link_fields:
        if src_table not in schema or target_table not in schema:
            continue
        if field_name in schema[src_table]["fields"]:
            print(f"  = link '{src_table}.{field_name}' уже есть — пропуск")
            continue
        call("POST", f"/bases/{base_id}/tables/{schema[src_table]['id']}/fields", token,
             {"name": field_name, "type": "multipleRecordLinks",
              "options": {"linkedTableId": schema[target_table]["id"]}})
        print(f"  + link '{src_table}.{field_name}' → {target_table}")


def main():
    ap = argparse.ArgumentParser(description="Создать структуру Airtable для ScheduleBot")
    ap.add_argument("--pat", default=os.getenv("AIRTABLE_PAT"),
                    help="Personal Access Token (или env AIRTABLE_PAT)")
    ap.add_argument("--base", help="ID существующей основной базы (appXXXX)")
    ap.add_argument("--workspace", help="ID workspace для создания новой базы (wspXXXX)")
    ap.add_argument("--name", default="ScheduleBot TEST", help="Имя новой базы")
    ap.add_argument("--with-sterilization", action="store_true",
                    help="Также создать базу стерилизации")
    ap.add_argument("--steril-base", help="ID существующей базы стерилизации")
    ap.add_argument("--steril-workspace", help="Workspace для базы стерилизации (по умолчанию как --workspace)")
    ap.add_argument("--steril-name", default="ScheduleBot Sterilization TEST")
    args = ap.parse_args()

    if not args.pat:
        raise SystemExit("Не задан PAT: --pat или env AIRTABLE_PAT")

    print("== Основная база ==")
    main_base = ensure_base(args.pat, MAIN_TABLES, args.base, args.workspace, args.name)
    ensure_links(args.pat, main_base, LINK_FIELDS)

    steril_base = None
    if args.with_sterilization or args.steril_base:
        print("\n== База стерилизации ==")
        steril_base = ensure_base(args.pat, STERIL_TABLES, args.steril_base,
                                  args.steril_workspace or args.workspace, args.steril_name)

    print("\n✅ Готово. Фрагмент для .env.local:\n")
    print("AIRTABLE_API_KEY=" + args.pat)
    print("AIRTABLE_BASE_ID=" + main_base)
    print("AIRTABLE_STERILIZATION_BASE_ID=" + (steril_base or "   # не создавалась"))


if __name__ == "__main__":
    main()
