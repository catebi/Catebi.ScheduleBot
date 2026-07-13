from telethon import Button

from app import state
from app.handlers.commands import schedule_handler, settings_handler, start_handler
from app.translations import (
    button_back,
    settings_view,
    settings_view_prompt,
    settings_view_success,
)


async def change_language(ctx):
    await start_handler(ctx.event, check_user=False, language=ctx.language)


async def change_view(ctx):
    event, language = ctx.event, ctx.language
    _, view = ctx.data.split(";")
    current_view = settings_view[view][language]

    buttons = [
        [Button.inline(label[language], data=f"change_view_to;{name}") for name, label in settings_view.items()],
        [Button.inline(button_back[language], data="back_settings")],
    ]
    await event.edit(settings_view_prompt[language].format(current_view), buttons=buttons)


async def change_view_to(ctx):
    event, user, language = ctx.event, ctx.user, ctx.language
    _, new_view = ctx.data.split(";")
    user.schedule_view = new_view
    user.save()

    await event.edit(
        settings_view_success[language].format(settings_view[new_view][language]),
        buttons=[[Button.inline(button_back[language], data="back")]],
    )


async def back_steril(ctx):
    await ctx.event.edit(
        state.steril_notification_message.message,
        buttons=state.steril_notification_message.buttons,
        formatting_entities=state.steril_notification_message.entities,
    )


async def back_settings(ctx):
    await settings_handler(ctx.event, edit=True)


async def back(ctx):
    await schedule_handler(ctx.event, ctx.language, update=True)
