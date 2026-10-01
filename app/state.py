# Cached schedule / volunteer views, refreshed by services.update_volunteers.
scheduled_dates = []
today_volunteers_list = []
dates_list = []

# Resolved Telegram topic chat entity and per-topic message ids.
topic_input_entity = None
cleaning_topic_id = None
medical_topic_id = None
steril_cat_topic_id = None

# Destination for the WARNING/ERROR alert mirror (see app.alerts).
# alert_chat_id is stored without the "-100" supergroup prefix; alert_topic_id
# is the topic's root message id (None => the group's General topic).
alert_chat_id = None
alert_topic_id = None

# The last steril notification message, re-rendered by the "back" button.
steril_notification_message = None

# Poor-man's FSM for the "set custom notification text" flow:
# {sender_id: {"type": "cleaning"|"medical", "prompt": <Message>}}.
# Mutated in place — never reassigned — so the NewMessage filter can close over it.
custom_text_setting = {}
