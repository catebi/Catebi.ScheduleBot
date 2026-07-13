# Catebi.ScheduleBot

Telegram bot for scheduling volunteer shifts at the Catebi cat shelter. Volunteers
sign up for cleaning / medical / cat acceptance-release shifts; curators get
shift-shortage reminders; and the bot posts daily cat-flat status/medical/changes
notifications to group topics. Built on [Telethon](https://docs.telethon.dev/)
(MTProto) with [Airtable](https://pyairtable.readthedocs.io/) as the data store.

## Project layout

The entrypoint is a thin `bot.py`; all logic lives in the `app` package:

```
bot.py                 # entrypoint -> app.main.run()
app/
  config.py            # env-var configuration
  constants.py         # shift/duty codes, cat-flat schema names, magic numbers
  logging_setup.py     # single logging config + the `logger` decorator
  state.py             # shared in-memory runtime state
  models.py            # pyairtable ORM models
  airtable_logger.py   # Airtable request logging (patched onto the models)
  translations.py      # all user-facing strings (en/ru)
  bot_client.py        # the Telethon client + raw Airtable API
  data/                # Airtable access: coercion, settings, cat-flat repo
  text/                # formatting: dates, labels, cat-flat entries
  services/            # schedule refresh, notifications, cat-flat overview
  handlers/            # /commands and the free-text input handler
  flows/               # callback-query dispatcher + per-feature flows
  jobs/                # aiocron scheduled jobs
  main.py              # wires it together and runs the bot
```

See [AIRTABLE_SCHEMA.md](AIRTABLE_SCHEMA.md) for the Airtable tables/fields, and
[scripts/create_airtable_schema.py](scripts/create_airtable_schema.py) to bootstrap them.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # or requirements-dev.txt for ruff
cp .env.example .env                      # then fill in the values
python bot.py
```

Requires Python 3.12+. Configuration is read from environment variables (see
`.env.example`); in production docker-compose injects them via `env_file`.

## Development

```bash
ruff check .        # lint
ruff format .       # format
```

## Deployment

`docker compose up --build -d` builds the image (`python:3.12-slim`) and runs the
bot with `restart: unless-stopped`. Pushing to `main` deploys to the VPS via the
GitHub Actions workflow in `.github/workflows/deploy.yml`.
