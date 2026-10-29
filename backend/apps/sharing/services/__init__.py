"""Writes on lists and links. `legacy`: the V1 owner-token path (/api/v1/). `lists`: the v2
operations with accounts and visibility (/api/v2/). V1 code imports the legacy functions
from here, as it did when this was a single module."""

from .legacy import (
    add_link,
    create_list,
    delete_link,
    delete_list,
    rotate_owner_token,
    update_link,
    update_list,
)

__all__ = [
    "add_link",
    "create_list",
    "delete_link",
    "delete_list",
    "rotate_owner_token",
    "update_link",
    "update_list",
]
