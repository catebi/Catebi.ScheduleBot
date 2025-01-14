from pyairtable.orm import Model, fields
from settings import airtable_api_key, airtable_base_id

class Volunteer(Model):
    telegram = fields.TextField('telegram', readonly=True)
    telegram_chat_id = fields.NumberField('telegram_chat_id', readonly=True)
    language = fields.SelectField('language')

    class Meta:
        memorize = True
        base_id = airtable_base_id
        table_name = 'volunteer'
        api_key = airtable_api_key

class Schedule(Model):
    telegram = fields.TextField('telegram')
    date = fields.DateField('date')
    telegram_chat_id = fields.NumberField('telegram_chat_id')
    volunteer = fields.SingleLinkField('volunteer', Volunteer)

    class Meta:
        memorize = True
        base_id = airtable_base_id
        table_name = 'schedule'
        api_key = airtable_api_key