# Cached schedule / volunteer views, refreshed by services.update_volunteers.
scheduled_dates = None
today_volunteers_list = None
dates_list = None

# Resolved Telegram topic chat entity and per-topic message ids.
topic_input_entity = None
cleaning_topic_id = None
medical_topic_id = None
steril_cat_topic_id = None

# The last steril notification message, re-rendered by the "back" button.
steril_notification_message = None

# Poor-man's FSM for the "set custom notification text" flow:
# {sender_id: {"type": "cleaning"|"medical", "prompt": <Message>}}.
# Mutated in place — never reassigned — so the NewMessage filter can close over it.
custom_text_setting = {}
