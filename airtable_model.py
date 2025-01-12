from pyairtable.orm import Model, fields
from settings import airtable_api_key, airtable_base_id

class Volunteer(Model):
    telegram = fields.TextField('telegram')
    name = fields.TextField('name')
    telegram_chat_id = fields.NumberField('telegram_chat_id')
    language = fields.SelectField('language')

    class Meta:
        base_id = airtable_base_id
        table_name = 'volunteer'
        api_key = airtable_api_key

class Schedule(Model):
    telegram = fields.TextField('telegram')
    date = fields.DateField('date')
    telegram_chat_id = fields.NumberField('telegram_chat_id')
    volunteer = fields.SingleLinkField('volunteer', Volunteer)
    name = fields.LookupField('name')

    class Meta:
        base_id = airtable_base_id
        table_name = 'schedule'
        api_key = airtable_api_key