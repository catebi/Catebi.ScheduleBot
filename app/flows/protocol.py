class CallbackContext:
    __slots__ = ("event", "data", "user", "language", "today")

    def __init__(self, event, data, user, language, today):
        self.event = event
        self.data = data
        self.user = user
        self.language = language
        self.today = today  # today's date as "dd.mm"

    @property
    def segments(self):
        return self.data.split(";")
