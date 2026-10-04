from enum import Enum


class AssigneeKind(str, Enum):
    """
    Which kind of person a location ping belongs to.

    Responders and volunteers have separate assignment tables for good
    reason - a responder is dispatched, a volunteer is invited and may
    decline - so a ping has to say which table its assignment_id points
    into.
    """

    responder = "responder"
    volunteer = "volunteer"
