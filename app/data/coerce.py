from datetime import datetime


def coerce_lookup(value, default=None):
    if isinstance(value, list) and len(value) > 0:
        return str(value[0])
    elif value is not None:
        return str(value)
    else:
        return default


def coerce_text(value, default=None):
    if isinstance(value, list) and len(value) > 0:
        return str(value[0])
    elif value:
        return str(value)
    else:
        return default


def to_local(dt: datetime) -> datetime:
    return dt.astimezone(datetime.now().astimezone().tzinfo)
