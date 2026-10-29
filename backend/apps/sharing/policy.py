"""Who may do what to a list (docs/v2/12-AUTHORIZATION.md). Pure: no Django, no database.

Every permission decision about a list goes through `can()`. Selectors load the facts it
needs in one query; services re-check it under the list's row lock before writing.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Visibility(StrEnum):
    PRIVATE = "private"  # members only
    UNLISTED = "unlisted"  # anyone with the URL
    PUBLIC = "public"  # anyone, and listed in the directory


class Role(StrEnum):
    OWNER = "owner"  # only ever from SharedList.owner, never a membership row
    EDITOR = "editor"
    VIEWER = "viewer"


class Action(StrEnum):
    VIEW = "view"
    VIEW_HISTORY = "view_history"
    EDIT = "edit"  # content: title, description, links, order, restore
    UPLOAD = "upload"  # list image, link icons: editors and owners, never an edit link
    SETTINGS = "settings"  # visibility, expiry, allow_fork, allow_branch
    VIEW_MEMBERS = "view_members"  # see who the list is shared with
    MEMBERS = "members"  # add people, change roles, remove people
    DELETE = "delete"
    ROTATE_TOKEN = "rotate_token"
    CLAIM = "claim"
    FORK = "fork"
    BRANCH = "branch"
    LEAVE = "leave"


@dataclass(frozen=True)
class Actor:
    """Who is asking. `legacy_list_id` is set only once an owner token has been verified
    against that list, so it can never authorize anything on another list (A3)."""

    user_id: UUID | None = None
    legacy_list_id: UUID | None = None
    email_verified: bool = False

    @property
    def is_signed_in(self) -> bool:
        return self.user_id is not None


ANONYMOUS = Actor()


@dataclass(frozen=True)
class ListFacts:
    """What `can()` needs to know about one list, as seen by one actor."""

    id: UUID
    owner_id: UUID | None
    visibility: Visibility
    allow_fork: bool = False
    allow_branch: bool = False
    member_role: Role | None = None  # the actor's membership on this list, if any

    @property
    def is_legacy(self) -> bool:
        return self.owner_id is None


def role_of(actor: Actor, facts: ListFacts) -> Role | None:
    if actor.user_id is not None and facts.owner_id == actor.user_id:
        return Role.OWNER
    return facts.member_role if actor.user_id is not None else None


def holds_token(actor: Actor, facts: ListFacts) -> bool:
    """The actor presented this unclaimed list's owner token (V1-equivalent rights)."""
    return facts.is_legacy and actor.legacy_list_id == facts.id


def can_view(actor: Actor, facts: ListFacts) -> bool:
    if facts.visibility in (Visibility.UNLISTED, Visibility.PUBLIC):
        return True
    return role_of(actor, facts) is not None or holds_token(actor, facts)


def can(actor: Actor, action: Action, facts: ListFacts) -> bool:
    role = role_of(actor, facts)
    token = holds_token(actor, facts)
    match action:
        case Action.VIEW:
            return can_view(actor, facts)
        case Action.VIEW_HISTORY | Action.EDIT:
            return role in (Role.OWNER, Role.EDITOR) or token
        case Action.VIEW_MEMBERS | Action.UPLOAD:
            return role in (Role.OWNER, Role.EDITOR)
        case Action.SETTINGS | Action.MEMBERS:
            return role is Role.OWNER
        case Action.DELETE:
            return role is Role.OWNER or token
        case Action.ROTATE_TOKEN:
            return token
        case Action.CLAIM:
            return token and actor.is_signed_in
        case Action.FORK:
            return actor.is_signed_in and (
                role is Role.OWNER or (can_view(actor, facts) and facts.allow_fork)
            )
        case Action.BRANCH:
            return actor.is_signed_in and (
                role is Role.OWNER or (can_view(actor, facts) and facts.allow_branch)
            )
        case Action.LEAVE:
            return role in (Role.EDITOR, Role.VIEWER)
    return False


def can_set_visibility(actor: Actor, facts: ListFacts, visibility: Visibility) -> bool:
    """Owners choose visibility; making a list public also needs a verified email (D20)."""
    if not can(actor, Action.SETTINGS, facts):
        return False
    return visibility is not Visibility.PUBLIC or actor.email_verified


def permissions(actor: Actor, facts: ListFacts) -> list[str]:
    """The actions this actor may take, for API representations (the UI shows only these)."""
    return [action.value for action in Action if can(actor, action, facts)]
