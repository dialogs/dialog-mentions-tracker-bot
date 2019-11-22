class User:
    def __init__(self, outpeer, groups):
        self.outpeer = outpeer
        self.groups = groups
        self.mentions = {}
        self.reminder = []
        self.buttons_mids = []
        self.remind_time = None
