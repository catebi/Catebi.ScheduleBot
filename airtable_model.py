from pyairtable.orm import Model, fields
from settings import airtable_api_key, airtable_base_id

class Volunteer(Model):
    telegram = fields.TextField('telegram', readonly=True)
    telegram_chat_id = fields.NumberField('telegram_chat_id', readonly=True)
    language = fields.SelectField('language')
    duties = fields.LookupField('duty_codes', readonly=True)

    class Meta:
        memorize = True
        base_id = airtable_base_id
        table_name = 'volunteer'
        api_key = airtable_api_key

class Schedule(Model):
    telegram = fields.TextField('telegram')
    date = fields.DatetimeField('date')
    telegram_chat_id = fields.NumberField('telegram_chat_id')
    volunteer = fields.SingleLinkField('volunteer', Volunteer)
    type = fields.SelectField('type')

    class Meta:
        memorize = True
        base_id = airtable_base_id
        table_name = 'schedule'
        api_key = airtable_api_key

class Notification(Model):
    admin_curator = fields.TextField('admin_curator')
    volunteer = fields.SingleLinkField('volunteer', Volunteer)
    telegram_chat_id = fields.NumberField('telegram_chat_id')
    notify_at = fields.TextField('notify_at')
    custom_text_cleaning = fields.TextField('custom_text_cleaning')
    custom_text_medical = fields.TextField('custom_text_medical')
    date_threshold = fields.TextField('date_threshold')

    class Meta:
        memorize = True
        base_id = airtable_base_id
        table_name = 'notification'
        api_key = airtable_api_key

class Settings(Model):
    key = fields.TextField('key')
    value = fields.NumberField('value')
    test_value = fields.NumberField('test_value')

    class Meta:
        memorize = True
        base_id = airtable_base_id
        table_name = 'settings'
        api_key = airtable_api_key