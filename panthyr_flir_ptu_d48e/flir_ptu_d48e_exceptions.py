class PTHeadReplyTimeout(Exception):
    """Timeout waiting for reply from head"""
    pass


class PTHeadNotInitialized(Exception):
    pass


class PTHeadIncorrectReply(Exception):
    pass
