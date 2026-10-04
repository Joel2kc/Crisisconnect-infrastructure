from enum import Enum


class VolunteerAssignmentStatus(str, Enum):
    """
    The life of one volunteer invitation.

    Kept separate from ResponderAssignmentStatus on purpose. A responder
    is staff and is dispatched; a volunteer is a member of the public and
    is invited, which means 'declined' has to be a first-class outcome
    rather than an error. That single difference is why the two flows do
    not share a table.
    """

    # Sent to the volunteer, waiting on them.
    invited = "invited"
    accepted = "accepted"
    # Set by the geofence, not by hand: the volunteer has left the place
    # they accepted from, and is travelling.
    en_route = "en_route"
    # Set by the geofence: they are within the arrival radius of the
    # incident.
    on_scene = "on_scene"
    declined = "declined"
    # The agency withdrew the invitation.
    stood_down = "stood_down"
    completed = "completed"
