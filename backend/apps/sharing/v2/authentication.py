from ..selectors import Principal


def principal_of(request) -> Principal:
    """The signed-in user of a request authenticated by the session (or nobody)."""
    user = request.user if request.user and request.user.is_authenticated else None
    return Principal(user=user)
