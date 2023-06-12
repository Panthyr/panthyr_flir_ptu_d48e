#! /usr/bin/python3
# -*- coding: utf-8 -*-
# Authors: Dieter Vansteenwegen
# Institution: VLIZ (Vlaams Instituut voor de Zee)

__author__ = 'Dieter Vansteenwegen'
__email__ = 'dieter.vansteenwegen@vliz.be'
__project__ = 'Panthyr'
__project_link__ = 'https://waterhypernet.org/equipment/'

__all__ = [
    'PTHeadIncorrectReply', 'PTHeadNotInitialized', 'PTHeadReplyTimeout',
    'PTHeadInvalidTargetPosition', 'PTHeadMoveError'
]


class PTHeadException(Exception):
    pass


class PTHeadReplyTimeout(PTHeadException):
    """Timeout waiting for reply from head"""
    pass


class PTHeadConnectionError(PTHeadException):
    """Could not connect to head"""
    pass


class PTHeadNotInitialized(PTHeadException):
    """Trying to perform an action, but head is not yet initialized"""
    pass


class PTHeadIncorrectReply(PTHeadException):
    """Head returned an incorrect reply to a command or query"""
    pass


class PTHeadInvalidTargetPosition(PTHeadException):
    """
    Requested target position is not valid.

    Position might be in an invalid format or out of hardware/user limits.
    """
    pass


class PTHeadMoveError(PTHeadException):
    """Head is not where it should be after a move action."""
    pass
