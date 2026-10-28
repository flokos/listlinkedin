"""Write operations on accounts. Sign-up, sign-in and passwords are handled by allauth."""

from .models import User


def update_profile(user: User, *, display_name: str) -> User:
    user.display_name = display_name
    user.save(update_fields=["display_name"])
    return user
