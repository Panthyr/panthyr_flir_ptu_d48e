__all__ = [
    'PTHeadIncorrectReply', 'PTHeadNotInitialized', 'PTHeadReplyTimeout',
    'PTHeadInvalidTargetPosition', 'PTHeadMoveError'
]


class PTHeadReplyTimeout(Exception):
    """Timeout waiting for reply from head"""
    pass


class PTHeadNotInitialized(Exception):
    """Trying to perform an action, but head is not yet initialized"""
    pass


class PTHeadIncorrectReply(Exception):
    """Head returned an incorrect reply to a command or query"""
    pass


class PTHeadInvalidTargetPosition(Exception):
    """
    Requested target position is not valid.
    
    Position might be in an invalid format or out of hardware/user limits.
    """
    pass


class PTHeadMoveError(Exception):
    """Head is not where it should be after a move action."""
    pass