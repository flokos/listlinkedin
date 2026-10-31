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
    UPLOAD = "upload"  # list image, link icons: editors and owners
    SETTINGS = "settings"  # visibility, expiry, allow_fork, allow_branch
    TAGS = "tags"  # editors and owners (since 8.1)
    VIEW_MEMBERS = "view_members"  # see who the list is shared with
    MEMBERS = "members"  # add people, change roles, remove people
    DELETE = "delete"
    FORK = "fork"
    BRANCH = "branch"
    LEAVE = "leave"
    REPORT = "report"  # tell the operator about abuse: anyone who can view it but its owner


@dataclass(frozen=True)
class Actor:
    """Who is asking: a signed-in account, or nobody."""

    user_id: UUID | None = None
    email_verified: bool = False

    @property
    def is_signed_in(self) -> bool:
        return self.user_id is not None


ANONYMOUS = Actor()


@dataclass(frozen=True)
class ListFacts:
    """What `can()` needs to know about one list, as seen by one actor."""

    id: UUID
    owner_id: UUID
    visibility: Visibility
    allow_fork: bool = False
    allow_branch: bool = False
    member_role: Role | None = None  # the actor's membership on this list, if any


def role_of(actor: Actor, facts: ListFacts) -> Role | None:
    if actor.user_id is not None and facts.owner_id == actor.user_id:
        return Role.OWNER
    return facts.member_role if actor.user_id is not None else None


def can_view(actor: Actor, facts: ListFacts) -> bool:
    if facts.visibility in (Visibility.UNLISTED, Visibility.PUBLIC):
        return True
    return role_of(actor, facts) is not None


def can(actor: Actor, action: Action, facts: ListFacts) -> bool:
    role = role_of(actor, facts)
    match action:
        case Action.VIEW:
            return can_view(actor, facts)
        case Action.VIEW_HISTORY | Action.EDIT:
            return role in (Role.OWNER, Role.EDITOR)
        case Action.VIEW_MEMBERS | Action.UPLOAD | Action.TAGS:
            return role in (Role.OWNER, Role.EDITOR)
        case Action.SETTINGS | Action.MEMBERS:
            return role is Role.OWNER
        case Action.DELETE:
            return role is Role.OWNER
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
        case Action.REPORT:
            return can_view(actor, facts) and role is not Role.OWNER
    return False


def can_set_visibility(actor: Actor, facts: ListFacts, visibility: Visibility) -> bool:
    """Owners choose visibility; making a list public also needs a verified email (D20)."""
    if not can(actor, Action.SETTINGS, facts):
        return False
    return visibility is not Visibility.PUBLIC or actor.email_verified


def permissions(actor: Actor, facts: ListFacts) -> list[str]:
    """The actions this actor may take, for API representations (the UI shows only these)."""
    return [action.value for action in Action if can(actor, action, facts)]


# Groups (docs/v2/12-AUTHORIZATION.md#group-permission-matrix). Group roles grant nothing on
# the lists in a group, and list roles grant nothing on groups.


class GroupAction(StrEnum):
    VIEW = "view"
    EDIT = "edit"  # title, description, image, order of lists, and removing lists
    ADD_LIST = "add_list"  # also needs a share right on the list: see can_add_list()
    VIEW_MEMBERS = "view_members"
    SETTINGS = "settings"  # visibility
    MEMBERS = "members"
    DELETE = "delete"
    LEAVE = "leave"
    REPORT = "report"  # as for lists: anyone who can view the group but its owner


@dataclass(frozen=True)
class GroupFacts:
    """What `can_group()` needs to know about one group, as seen by one actor."""

    id: UUID
    owner_id: UUID
    visibility: Visibility
    member_role: Role | None = None  # the actor's membership on this group, if any


def group_role_of(actor: Actor, facts: GroupFacts) -> Role | None:
    if actor.user_id is None:
        return None
    return Role.OWNER if facts.owner_id == actor.user_id else facts.member_role


def can_group(actor: Actor, action: GroupAction, facts: GroupFacts) -> bool:
    role = group_role_of(actor, facts)
    match action:
        case GroupAction.VIEW:
            return facts.visibility is not Visibility.PRIVATE or role is not None
        case GroupAction.EDIT | GroupAction.ADD_LIST | GroupAction.VIEW_MEMBERS:
            return role in (Role.OWNER, Role.EDITOR)
        case GroupAction.SETTINGS | GroupAction.MEMBERS | GroupAction.DELETE:
            return role is Role.OWNER
        case GroupAction.LEAVE:
            return role in (Role.EDITOR, Role.VIEWER)
        case GroupAction.REPORT:
            return can_group(actor, GroupAction.VIEW, facts) and role is not Role.OWNER
    return False


def can_set_group_visibility(actor: Actor, facts: GroupFacts, visibility: Visibility) -> bool:
    """As for lists: the owner chooses, and public needs a verified email (D20)."""
    if not can_group(actor, GroupAction.SETTINGS, facts):
        return False
    return visibility is not Visibility.PUBLIC or actor.email_verified


def can_add_list(actor: Actor, group: GroupFacts, shared_list: ListFacts) -> bool:
    """A group editor may add a list they could share themselves: one they edit or own, or a
    public one. Nobody can put another person's unlisted or private list in their group."""
    if not can_group(actor, GroupAction.ADD_LIST, group):
        return False
    role = role_of(actor, shared_list)
    return role in (Role.OWNER, Role.EDITOR) or shared_list.visibility is Visibility.PUBLIC


def shown_in_group(
    *, has_list_role: bool, list_visibility: Visibility, group_visibility: Visibility
) -> bool:
    """Whether a group shows one of its lists to a viewer who can view the group
    (docs/v2/12-AUTHORIZATION.md#which-lists-a-group-shows-to-a-viewer). A list that isn't
    shown is omitted entirely: no title, no placeholder, no count.

    `groups.selectors.shown_lists_q` is the same rule in SQL; a test checks they agree.
    """
    return (
        has_list_role
        or list_visibility is Visibility.PUBLIC
        or (list_visibility is Visibility.UNLISTED and group_visibility is not Visibility.PUBLIC)
    )


def group_permissions(actor: Actor, facts: GroupFacts) -> list[str]:
    return [action.value for action in GroupAction if can_group(actor, action, facts)]
