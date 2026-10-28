# MASTER PROMPT: VERSION 2 ARCHITECTURE, RESEARCH & MIGRATION PLANNING

## PROJECT: SHAREABLE LINK COLLECTIONS — VERSION 2

You are acting as a multidisciplinary senior software engineering and product architecture team.

Your responsibilities include those of:

- Principal Software Architect
- Solution Architect
- Senior Python Backend Engineer
- Django / Django REST Framework Specialist
- Domain-Driven Design Architect
- Database Architect
- Frontend Architect
- Senior Frontend Engineer
- UI/UX Designer
- Product Designer
- DevOps / Infrastructure Engineer
- Application Security Engineer
- QA and Test Automation Engineer
- Technical Lead
- Technical Writer

Your task is to inspect the existing Version 1 application, research relevant current industry practices, evaluate the requirements described below, and produce a comprehensive, implementation-ready migration plan for Version 2.

You must approach this as an evolution of an existing application, not as a greenfield project.

**Do not immediately implement Version 2. Your primary task is research, architecture assessment, planning, documentation, and safe Git branch preparation.**

You must thoroughly understand the existing codebase before recommending architectural changes.

Do not assume the current implementation matches the intended V1 architecture described in this prompt. Inspect the repository and distinguish actual implementation from intended design.

Your final work must provide enough architectural detail and documentation for future Claude Code sessions, developers, or coding agents to implement Version 2 incrementally without repeatedly redesigning the system.

---

# PART 1 — MANDATORY ENGINEERING PRINCIPLES

Follow these principles throughout the entire analysis, design, planning, and subsequent implementation guidance.

## 1.1 SOLID

Apply all five SOLID principles where relevant:

- Single Responsibility Principle
- Open/Closed Principle
- Liskov Substitution Principle
- Interface Segregation Principle
- Dependency Inversion Principle

However, do not introduce unnecessary abstraction merely to demonstrate SOLID compliance.

An abstraction should solve a genuine problem.

## 1.2 KISS

Keep the system as simple as reasonably possible.

Prefer straightforward implementation strategies over clever or unnecessarily sophisticated solutions.

Avoid introducing architectural complexity that does not address an actual requirement.

## 1.3 YAGNI

Do not implement or design speculative features without a reasonable justification.

Avoid premature support for:

- Distributed microservices
- Multi-region deployment
- Complex event sourcing
- Distributed transactions
- Multi-parent Git-style merging
- Sophisticated message brokers
- Full distributed CQRS architectures
- Multiple read/write databases
- Kubernetes
- Unnecessary third-party services

If a feature is not required for V2, defer it unless it is essential to avoid a significant architectural flaw.

## 1.4 DRY

Avoid unnecessary duplication.

However, do not create generic abstractions prematurely.

Some duplication is preferable to the wrong abstraction.

## 1.5 Separation of Concerns

Maintain clear boundaries between:

- Domain logic
- Application orchestration
- Infrastructure
- Persistence
- HTTP/API concerns
- Authentication and authorization
- Frontend presentation
- UI state
- External integrations

## 1.6 Additional Principles

Apply where appropriate:

- High cohesion and low coupling
- Explicit domain invariants
- Secure by default
- Least privilege
- Defense in depth
- Fail safely
- Transactional consistency
- Deterministic behavior
- Idempotency
- Testability
- Maintainability
- Observability
- Backward compatibility where practical
- Progressive enhancement
- Accessibility
- Performance-conscious design

**Pragmatism takes precedence over architectural purity.**

Explain any trade-off where strict adherence to a principle would introduce unnecessary complexity.

---

# PART 2 — GIT BRANCHING STRATEGY: CRITICAL REQUIREMENT

Version 1 already exists.

We must preserve it.

## 2.1 Preserve the existing main branch

The existing `main` branch represents Version 1.

You must:

1. Inspect the repository's current Git state.
2. Identify the existing primary branch.
3. Confirm whether it is named `main`, `master`, or something else.
4. Inspect existing local and remote branches.
5. Check for uncommitted changes.
6. Check for existing worktrees.
7. Inspect the existing remote configuration.
8. Identify the correct and safe branching strategy.

**Never delete, reset, rebase, overwrite, or force-push the existing main branch.**

Do not make Version 2 commits directly to main.

Do not modify main as part of this migration-planning task.

If uncommitted changes exist, preserve them. Do not discard or automatically stash work without determining its impact.

If the repository cannot be branched safely, explain the blocker rather than using destructive commands.

## 2.2 Create a dedicated V2 integration branch

Create a long-lived Git branch named:

`v2`

This branch must originate from the appropriate current Version 1 baseline.

Treat `v2` as the new integration branch for the Version 2 development lifecycle.

Conceptually:

```text
main
 │
 ├── Version 1
 │
 └── v2
      │
      ├── feature/authentication
      ├── feature/groups
      ├── feature/revisions
      ├── feature/branching
      ├── feature/synchronization
      ├── feature/ui-redesign
      └── feature/metadata
```

This is a Git branch, not necessarily a separate GitHub repository fork.

Version 1 must remain independently available.

If `v2` already exists, inspect it before taking action. Do not recreate, overwrite, or reset it.

## 2.3 V2 pull request policy

**All Version 2 pull requests must target `v2`, not `main`.**

Examples:

Correct:

```text
feature/groups → v2
feature/revisions → v2
feature/synchronization → v2
```

Incorrect:

```text
feature/groups → main
feature/revisions → main
feature/synchronization → main
```

All V2 feature branches must be created from the current `v2` baseline, unless an explicit technical dependency justifies another strategy.

Do not change the repository's default branch from main merely to enforce this rule.

Research and recommend the best approach for preventing accidental pull requests into main.

Investigate applicable repository mechanisms, including:

- GitHub or GitLab branch protections
- Pull request templates
- CI validation of pull request targets
- GitHub Actions or equivalent workflows
- Repository rulesets
- CODEOWNERS
- Branch naming conventions
- Optional local Git hooks

Do not assume the repository uses GitHub.

Inspect its actual hosting provider and available permissions.

Where direct repository settings cannot be modified safely or programmatically, provide precise manual configuration instructions.

Do not claim a branch protection policy has been enforced unless it actually has.

## 2.4 Version 1 must remain maintainable

Version 1 may continue receiving bug fixes.

If a fix is required in both versions, recommend a controlled integration strategy.

For example:

```text
main
  |
  └── bugfix/v1-security-fix

v2
  |
  └── cherry-pick relevant fix
```

Evaluate whether cherry-picking, selective merging, or another approach is appropriate.

Avoid automatically merging every main change into v2 without reviewing compatibility.

## 2.5 Git actions allowed during this task

You are authorized to:

- Inspect repository status and history.
- Inspect branches and remotes.
- Create the dedicated `v2` branch safely.
- Work within `v2`.
- Create planning and architectural documentation.
- Add documentation directories and files.
- Prepare implementation plans.
- Recommend branch-protection configuration.

Do not:

- Implement the complete V2 application yet.
- Perform destructive Git operations.
- Force-push.
- Delete branches.
- Change repository default-branch settings without explicit approval.
- Merge into main.
- Open a pull request targeting main.
- Modify production deployment settings.
- Deploy anything.

If remote publication of `v2` is needed, distinguish local branch creation from pushing to the remote and report whether publication was performed.

The planning task must finish with Version 1 intact.

---

# PART 3 — INSPECT THE EXISTING APPLICATION FIRST

Before designing the migration, thoroughly inspect the current repository.

Do not assume any specific frontend framework, backend package layout, database configuration, or implementation details without verifying them.

## 3.1 Backend investigation

Identify:

- Programming language and version
- Django version, if present
- Django REST Framework version, if present
- Application structure
- Domain models
- ORM models
- Serializers
- ViewSets
- Routers
- Authentication
- Authorization
- Business logic placement
- Services and use cases
- Repository abstractions
- URL-shortening implementation
- Identifier generation
- Database migrations
- Configuration
- Tests
- Background jobs
- Dependencies

Pay particular attention to the existing `List` and `Link` concepts.

Determine whether they are implemented as originally intended and whether they can be extended safely.

Identify existing domain invariants.

## 3.2 Frontend investigation

Version 1 already has a working UI.

You must inspect it.

Identify:

- Framework and version
- Routing
- Component structure
- UI library
- Styling approach
- State management
- API integration
- Authentication assumptions
- Forms
- List creation workflows
- Link management workflows
- Sharing workflows
- Navigation
- Responsive behavior
- Error handling
- Existing design patterns
- Tests

Study the current UI/UX and identify which screens and components can be retained, extended, or redesigned.

**Do not propose rebuilding the frontend from scratch unless you can clearly demonstrate that it is necessary.**

Reuse existing components where practical.

Preserve the current visual identity where it remains suitable.

## 3.3 Infrastructure investigation

Inspect:

- Dockerfiles
- Docker Compose configuration
- Database services
- Cache services
- Reverse proxy
- Environment configuration
- CI/CD workflows
- Deployment configuration
- Secrets management
- Logging
- Monitoring
- Static file handling
- Media storage
- Development workflow
- Existing scripts

Preserve the Docker-based development approach.

Do not introduce Python virtual environments as the required development workflow.

## 3.4 Test coverage assessment

Identify:

- Existing unit tests
- Integration tests
- API tests
- Frontend tests
- End-to-end tests
- Coverage gaps
- Missing critical regression tests

Determine which existing tests must continue passing after the migration.

Document all findings.

---

# PART 4 — PRODUCT OVERVIEW

## 4.1 Version 1

Version 1 is a lightweight application designed around sharing collections of URLs.

The original concept includes:

- Creating collections of links.
- Adding, editing, and removing links.
- Sharing collections through URLs.
- A URL shortener.
- Stable collection identifiers.
- Creator-controlled management.
- Anonymous access to shared collections.
- Temporary collections, originally retained for one month.
- No mandatory user accounts.
- Dockerized development.
- Django REST Framework ViewSets.
- Separation between business logic and API concerns.

Version 1 was initially conceived as a simple team-bonding application.

Its primary entities are:

```text
List
 ├── Link
 ├── Link
 └── Link
```

The exact implementation must be verified against the repository.

## 4.2 Version 2

Version 2 evolves the original application into a collaborative platform for organizing, sharing, and synchronizing collections of links.

The application combines concepts from:

- Bookmark managers
- Web application directories
- Application launchers
- Shared workspaces
- Git-inspired version control

The central concept remains:

**A List contains Links.**

Even when the links represent web applications, do not introduce a separate `WebApp` entity without a demonstrated architectural reason.

The user has explicitly decided to preserve the original `List` and `Link` concepts.

Our goal is to evolve the application rather than replace its foundation.

---

# PART 5 — CORE DOMAIN MODEL

Use the following as the proposed domain baseline.

Validate it against the actual V1 implementation and your research.

You may recommend adjustments, but explain why they are necessary and how they affect migration complexity.

Avoid introducing additional entities without justification.

## 5.1 User

Version 2 introduces user accounts.

Users need to:

- Own multiple lists.
- Own groups.
- Collaborate.
- Manage permissions.
- Create forks and branches.
- Access private collections.
- Maintain synchronization settings.

Prefer Django's authentication system with a custom user model if it can be introduced safely.

Investigate the implications of introducing a custom user model into an existing project, especially if authentication tables or migrations already exist.

Do not casually change `AUTH_USER_MODEL` in a populated database without a migration strategy.

Domain code should not depend unnecessarily on Django's User implementation.

## 5.2 List

The List remains our central collection entity.

Proposed conceptual fields:

```text
List
----
id
owner_id

title
description
image
slug
visibility

allow_fork
allow_branch

expires_at
deleted_at

created_at
updated_at
```

Required behavior:

- The List ID remains stable.
- Its content can change independently.
- Its title and metadata can change.
- Its slug can change.
- It can belong to multiple groups.
- It can exist without a group.
- It can serve as a parent list.
- It can itself be a child branch.
- It can have multiple children.
- It can optionally expire.
- Permanent lists do not expire automatically.

Visibility options:

```text
PRIVATE
UNLISTED
PUBLIC
```

Semantics:

PRIVATE:
Only authorized users may access the resource.

UNLISTED:
Accessible through its direct sharing URL but not publicly discoverable.

PUBLIC:
Accessible publicly and discoverable in the directory.

Evaluate whether slugs should be globally unique or unique only within a namespace.

Consider slug changes, collisions, reserved names, and existing short URLs.

## 5.3 Link

Preserve the original Link entity.

Proposed conceptual fields:

```text
Link
----
id
list_id

url
title
description
icon

position
source_link_id

metadata
metadata_fetched_at

created_at
updated_at
deleted_at
```

A Link belongs to a List.

A Link represents an individual URL entry.

Do not introduce a separate global WebApp record for the MVP.

### Critical identity rule

**Updating a Link's URL must not create a new Link.**

For example:

```text
Before:

Link ID: 123
URL: https://github.com

After:

Link ID: 123
URL: https://gitlab.com
```

The Link ID remains unchanged.

Its List association remains unchanged.

Its revision history records the change.

Its source relationship remains unchanged.

If an existing short URL references the Link's identity, that short URL must continue resolving to the Link's current destination.

The URL itself is mutable data, not the identity of the Link.

### Branch origin tracking

When a branch is created, Links are copied.

Each child Link receives:

- A new Link ID.
- The original data.
- A reference to the source Link's identity.

Example:

```text
Parent Link:
    ID: A

Child Link:
    ID: B
    source_link_id: A
```

Do not make child Links depend on the ongoing existence of the parent's live database row.

Research the best way to preserve source identity across deletions and nested branches.

### Link ordering

Each Link has an explicit position within its List.

Ordering must support drag-and-drop.

Determine how to enforce ordering consistency under concurrent modifications.

Evaluate simple integer positions, fractional indexing, or another appropriate solution.

Prefer the simplest reliable approach for the expected scale.

## 5.4 Group

Groups organize multiple Lists.

Proposed conceptual fields:

```text
Group
-----
id
owner_id

title
description
image
slug
visibility

created_at
updated_at
deleted_at
```

Groups have their own:

- Visibility
- Ownership
- Permissions
- Tags
- Sharing URLs
- Metadata

A Group is a navigation and organization container.

It does not duplicate the content of its Lists.

## 5.5 GroupList

Use a many-to-many relationship:

```text
GroupList
---------
id
group_id
list_id
position
```

A List may belong to multiple Groups.

A Group may contain multiple Lists.

A List retains its identity across Groups.

Group membership must not change its underlying content.

Consider uniqueness constraints and ordering.

### Critical access rule

A public Group must not bypass the permissions of its individual Lists.

If a Group contains a private List, unauthorized visitors must not receive that List's protected data.

Also investigate whether returning the List's title or existence would itself leak private information.

## 5.6 ListMembership and GroupMembership

Use resource-specific membership models unless research demonstrates a better alternative.

Conceptually:

```text
ListMembership
--------------
id
list_id
user_id
role
```

```text
GroupMembership
---------------
id
group_id
user_id
role
```

Supported roles:

```text
OWNER
EDITOR
VIEWER
```

List ownership may be represented directly through `owner_id`, with membership roles implemented without duplicating the authoritative owner relationship.

Define precise permission rules for:

- Viewing
- Creating
- Editing
- Deleting
- Sharing
- Managing members
- Changing visibility
- Forking
- Branching
- Synchronizing
- Restoring revisions

Avoid ambiguous permission inheritance.

Anonymous users may still view appropriate public and unlisted collections.

Determine the safest migration path from V1's creator-specific management links to authenticated ownership.

Do not allow a public sharing link to grant edit privileges accidentally.

## 5.7 ListRevision

Introduce immutable revision history.

Conceptual fields:

```text
ListRevision
------------
id
list_id

revision_number
snapshot

created_by_id
created_at
```

Each revision represents a complete, immutable state of the List at a particular point in time.

Research and compare:

- Full JSON snapshots
- Change-based history
- Event sourcing
- Hybrid snapshots and change records

**Our preferred starting point is immutable full snapshots stored in PostgreSQL.**

Do not introduce event sourcing unless there is a compelling reason.

Snapshots must include enough information to reconstruct deleted Links.

Include an explicit snapshot schema version for future evolution.

Revisions must be created atomically with their corresponding modifications.

A failed mutation must not create a revision.

Restoring an old revision must create a new revision.

Never rewrite historical revisions.

Determine how to handle metadata-only updates, reordering, and no-op operations without creating unnecessary revisions.

## 5.8 ListBranch

A branch is an ordinary List connected to another List.

Do not create a separate `BranchedList` model.

Conceptual fields:

```text
ListBranch
----------
id

parent_list_id
child_list_id

base_revision_id

created_at
last_synced_at
```

Required rules:

- Each child has at most one direct parent.
- A parent can have many children.
- A branch has independent Links.
- Parent changes never automatically overwrite the child.
- Child changes never modify the parent.
- Circular ancestry is forbidden.
- Nested branches are permitted.
- Synchronization occurs only with the immediate parent.
- The child survives parent deletion.

Do not implement multi-parent merging.

Branch creation must use a consistent snapshot of the parent.

The creation of the child, copied Links, initial revision, and branch relationship must be atomic.

## 5.9 BranchExclusion

Introduce persistent exclusions.

Conceptual fields:

```text
BranchExclusion
---------------
id
branch_id
source_link_id
created_at
```

An exclusion means that a particular source Link should be ignored during future synchronizations.

Exclusions are based on stable source identities, not URLs.

If the source Link's URL changes, it remains excluded.

If the source Link is deleted and later recreated as a new Link, the new entry has a distinct identity.

The user can remove exclusions.

For the MVP, exclusions operate at Link level, not individual field level.

## 5.10 ShortURL

Preserve the original URL-shortening concept and existing implementation wherever possible.

Proposed conceptual structure:

```text
ShortURL
--------
id
code

target_type
target_reference
destination_url

expires_at
created_at
```

Supported targets:

```text
LIST
GROUP
LINK
EXTERNAL_URL
```

Use appropriate database constraints and referential integrity.

Avoid unconstrained generic references if a simpler relational design is available.

### Critical short URL behavior

Short URLs must remain stable when:

- A List title changes.
- A List slug changes.
- A List's Links change.
- A Link's URL changes.
- A Group's content changes.

For a short URL referencing a Link, the redirect destination must be resolved from the current Link value.

A short URL must not bypass resource visibility or authorization rules.

### Identifier generation

Research the best practical strategies for collision-resistant short URLs.

Compare:

- Random Base62 or similar codes
- UUID-derived identifiers
- Obfuscated UUIDs
- Sequential IDs with reversible encoding
- Hash-based approaches

Consider:

- Collision probability
- Predictability
- Enumeration risks
- Database uniqueness
- Retry behavior
- Maintenance
- Redirect performance
- Code length
- Security

Our preferred approach is cryptographically secure random codes, database uniqueness constraints, and collision retries.

Do not introduce unnecessary cryptographic obfuscation.

Document the rationale.

---

# PART 6 — BRANCHING AND SYNCHRONIZATION

This is the most important and highest-risk subsystem in Version 2.

Treat synchronization as domain logic, not as ordinary CRUD.

Research established approaches to three-way merging and revision control.

Study relevant implementation patterns from Git-inspired systems, synchronization engines, and versioned data management.

Adapt the ideas to collections of Links.

**Do not attempt to recreate Git internally.**

We only need the subset of Git-like behavior required by this application.

## 6.1 Required operations

The domain must support:

```text
create_revision()
restore_revision()

create_branch()
create_fork()

calculate_diff()
preview_merge()
apply_merge()

add_exclusion()
remove_exclusion()

get_sync_status()
```

These names are illustrative.

Define suitable domain interfaces.

## 6.2 Fork versus Branch

A Fork creates an independent copy without an ongoing synchronization relationship.

A Branch creates an independent copy that retains a synchronization relationship with its parent.

Both are ordinary Lists.

Forks must not accidentally continue receiving parent updates.

## 6.3 Three-way merge

Every merge compares:

```text
BASE
PARENT
CHILD
```

BASE:
The parent state at the synchronization baseline.

PARENT:
The parent's current revision.

CHILD:
The child's current revision.

Example:

```text
BASE
----
GitHub
Docker
Postman
```

```text
PARENT
------
GitHub
Docker Hub
Postman
Redis
```

```text
CHILD
-----
GitHub
Docker Desktop
Postman
ChatGPT
```

Expected analysis:

```text
GitHub:
    unchanged

Docker:
    conflicting title changes

Postman:
    unchanged

Redis:
    new parent Link

ChatGPT:
    local child addition
```

## 6.4 Conflict detection

Support the following scenarios:

1. Parent adds a Link.
2. Parent deletes a Link.
3. Parent changes a Link's URL.
4. Parent changes a Link's title.
5. Parent changes its description.
6. Parent changes its icon.
7. Child modifies an inherited Link.
8. Parent and Child modify the same field differently.
9. Parent and Child modify different fields.
10. Parent deletes a Link that Child modified.
11. Child deletes a Link that Parent modified.
12. Both delete the same inherited Link.
13. Child adds a local Link.
14. Parent and Child independently add the same URL.
15. Parent changes a previously excluded Link.
16. User removes an exclusion.
17. Parent changes after a previous Keep Local decision.
18. Parent is deleted.
19. Child is restored to an earlier revision.
20. Branches exist across multiple generations.

Research and explicitly define any missing scenarios.

## 6.5 Field-level merging

Changes to different fields of the same Link should not necessarily conflict.

Example:

```text
BASE:
    title: Docker
    icon: original.png

PARENT:
    title: Docker Hub
    icon: original.png

CHILD:
    title: Docker
    icon: custom.png
```

Expected behavior:

```text
MERGED CHILD:
    title: Docker Hub
    icon: custom.png
```

Do not report unnecessary conflicts when independent modifications can be safely combined.

Potential mergeable fields:

```text
url
title
description
icon
metadata overrides
```

Consider which metadata fields should be excluded from synchronization, such as automatically refreshed timestamps or extraction status.

Avoid making background metadata refreshes produce surprising conflicts.

## 6.6 Ordering

Ordering deserves separate treatment.

For the MVP, prefer:

**Preserve the child's local order by default.**

When accepting new parent Links, append them deterministically.

Do not automatically overwrite the child's arrangement.

Research alternative ordering merge strategies, but avoid implementing a complex sequence-merging algorithm unless needed.

Document that parent-only reorder changes are not synchronized in the initial version if this policy is retained.

## 6.7 Merge decisions

Support:

```text
ACCEPT
KEEP_LOCAL
EXCLUDE
```

### ACCEPT

Apply the incoming parent change.

### KEEP_LOCAL

Preserve the child's local value for the current incoming change.

Acknowledge the processed parent revision so the same change does not reappear indefinitely.

Future parent modifications may produce new synchronization proposals.

### EXCLUDE

Persistently ignore the source Link.

The exclusion remains in effect until explicitly removed.

Define how Exclude behaves for additions, edits, and deletions.

Do not leave these semantics ambiguous.

## 6.8 Merge preview

The backend must calculate a preview without changing persisted data.

The preview should include:

- Parent revision
- Child revision
- Baseline revision
- Incoming changes
- Local changes
- Conflicts
- Available decisions
- Exclusions
- Proposed result

The preview should be structured for the frontend to display clearly.

Use stable identifiers for each proposed change so decisions cannot accidentally apply to the wrong Link or field.

## 6.9 Applying a merge

Applying a merge must:

1. Validate authorization.
2. Verify relevant revisions.
3. Reject outdated merge plans.
4. Validate decisions.
5. Execute the merge atomically.
6. Preserve unrelated local changes.
7. Maintain source identities.
8. Persist exclusions.
9. Create a child revision when content changes.
10. Advance synchronization state correctly.
11. Avoid duplicate Links.
12. Preserve parent data.

## 6.10 Race conditions

Research and address:

- Concurrent edits to the same List.
- Concurrent merges.
- Parent changes during merge preview.
- Child changes during merge preview.
- Simultaneous reorder requests.
- Duplicate branch creation requests.
- Duplicate Link insertion requests.
- Duplicate short-code generation.
- Revision-number conflicts.
- Concurrent expiration and synchronization.
- Metadata updates during manual editing.

Evaluate:

- PostgreSQL transactions
- `SELECT FOR UPDATE`
- Optimistic concurrency control
- Revision preconditions
- Unique constraints
- Idempotency keys
- Retry strategies

Prefer PostgreSQL's existing capabilities before introducing external infrastructure.

Explain when row-level locking is preferable and when optimistic concurrency is preferable.

## 6.11 Idempotency

A completed merge must not be applied again accidentally.

Repeated identical requests must not:

- Duplicate Links.
- Produce unnecessary revisions.
- Corrupt branch ancestry.
- Repeat deletions incorrectly.
- Recreate excluded Links unexpectedly.

Design and test explicit idempotency behavior.

## 6.12 Synchronization baseline

Pay particular attention to baseline advancement.

Example:

```text
BASE:
    GitHub

PARENT:
    GitLab

CHILD:
    Bitbucket
```

The user chooses Keep Local.

Child remains Bitbucket.

The current incoming change is acknowledged.

If Parent later becomes Azure DevOps, the new parent change must be detectable.

Document precisely how baselines and local divergence are tracked.

## 6.13 Deletion and restoration

Research and define:

- Parent deletion.
- Child deletion.
- Parent expiration.
- Link deletion.
- Link restoration.
- Branch restoration.
- Restoring a parent to an older revision.
- Restoring a child to a previous revision.
- Reintroducing excluded Links.
- Changes to a source Link that no longer exists.

Deletion should not accidentally destroy required historical information.

Consider soft deletion and tombstones where appropriate.

Do not introduce unnecessary historical tables if revision snapshots already provide the required information.

---

# PART 7 — DOMAIN-DRIVEN DESIGN AND CLEAN ARCHITECTURE

The original architectural direction favors Onion/Hexagonal Architecture.

Maintain that direction where compatible with the existing implementation.

Prefer:

```text
API / Presentation
        |
        v
Application Layer
        |
        v
Domain Layer
        ^
        |
Infrastructure Adapters
```

The domain layer should not depend on Django.

Application services should coordinate business operations.

Infrastructure adapters should implement persistence, metadata extraction, and other technical concerns.

DRF should remain responsible for HTTP concerns.

## 7.1 Proposed domain areas

```text
domain/
    lists/
    links/
    groups/
    branching/
    permissions/
    shortening/
```

This is a conceptual structure.

Inspect the existing codebase before deciding on the final directories.

Do not reorganize the entire project merely for cosmetic consistency.

## 7.2 Application use cases

Examples:

```text
CreateList
UpdateList
DeleteList

AddLink
UpdateLink
DeleteLink
ReorderLinks

CreateGroup
UpdateGroup
AddListToGroup
RemoveListFromGroup

CreateRevision
RestoreRevision

CreateBranch
CreateFork

PreviewMerge
ApplyMerge

ManageMembership
ManageExclusions
```

Define responsibilities and transaction boundaries.

## 7.3 Domain services

Examples:

```text
MergeService
DiffService
PermissionPolicy
RevisionService
```

Only introduce these abstractions when they provide meaningful separation.

Do not turn every simple operation into a separate class unless the existing architecture already uses that convention consistently.

## 7.4 Repositories

Keep interfaces close to the use cases that need them.

Avoid generic repositories that duplicate the entire Django ORM.

Use repository abstractions where they meaningfully isolate the domain or simplify testing.

## 7.5 CQRS

Separating commands and queries is acceptable.

However:

**Do not introduce a separate read database, event bus, or distributed CQRS architecture unless justified.**

A single PostgreSQL database should remain the default source of truth.

## 7.6 Django REST Framework

Continue using DRF ViewSets.

Do not replace them with simple function-based views merely for convenience.

Use custom ViewSet actions where appropriate.

Keep:

- Serializers
- Permissions
- Pagination
- Filtering
- Validation
- Exception handling

well-organized.

Domain validation must not be duplicated unnecessarily inside serializers.

Infrastructure errors and domain errors should map to appropriate HTTP responses.

---

# PART 8 — FRONTEND AND UI/UX MIGRATION

Version 1 already has a UI.

**You must inspect the current frontend before proposing any redesign.**

Our goal is to extend and improve the existing user experience while preserving useful components and familiar workflows.

The new application should remain simple, fast, and intuitive.

Do not turn the UI into a complicated enterprise dashboard.

## 8.1 Preserve existing workflows

Identify and preserve or improve:

- Creating a collection.
- Adding links.
- Editing links.
- Removing links.
- Sharing collections.
- Copying short URLs.
- Viewing a shared collection.
- Managing an existing collection.

Existing features must not disappear during the transition.

## 8.2 New List presentation

Links should be presented as application-style tiles.

Each tile should support:

- A 128×128 px icon or image.
- Application name.
- Optional description.
- Context menu using three dots.
- Open link.
- Edit.
- Remove.
- Reorder.
- Move, where permitted.

The description must remain available to authorized viewers.

Decide whether this is best implemented using a grid, list, or switchable view based on the current UI.

Do not assume a complete redesign is necessary.

## 8.3 Groups and navigation

Groups combine multiple Lists into a unified workspace.

The intended desktop experience includes a left sidebar.

Example:

```text
+----------------------+-----------------------------+
| Development Portal   |                             |
|                      |     Current List            |
| Backend Tools        |                             |
| AI Tools             |     [App] [App] [App]       |
| Database Tools       |                             |
| Productivity         |     [App] [App] [App]       |
|                      |                             |
+----------------------+-----------------------------+
```

Investigate how this should adapt to tablets and mobile devices.

Consider:

- Collapsible sidebars
- Mobile navigation drawers
- Keyboard navigation
- Accessible focus management
- Responsive tile grids
- Navigation state persistence

A Group is a portal containing Lists, not a duplicated copy of their Links.

## 8.4 Branching UI

Users should be able to:

- Create a branch.
- Identify the source List.
- View parent information.
- See whether updates are available.
- Preview incoming changes.
- Review conflicts.
- Select merge decisions.
- Apply synchronization.
- Remove exclusions.

The experience must make the difference between Fork and Branch understandable.

Avoid exposing unnecessary Git terminology if simpler product language would improve usability.

## 8.5 Merge preview interface

Design a clear merge preview showing:

- Added Links
- Removed Links
- Modified Links
- Conflicting changes
- Local modifications
- Exclusions

For each incoming change, allow suitable decisions:

```text
Accept
Keep Local
Exclude
```

For field-level conflicts, clearly display:

```text
Original value
Parent value
Child value
```

Avoid presenting raw JSON to end users.

Consider visual diff cards, change indicators, comparison views, or another suitable UI.

Use the simplest interaction that adequately explains the consequences.

## 8.6 UI states

Design all important states:

- Loading
- Empty collection
- Empty group
- No search results
- Metadata extraction in progress
- Metadata unavailable
- Permission denied
- Authentication required
- Expired collection
- Deleted parent
- No synchronization updates
- Updates available
- Merge conflicts
- Stale merge preview
- Merge successful
- Merge failed
- Network failure

Avoid ambiguous or misleading success states.

## 8.7 Drag-and-drop

Research appropriate libraries for the existing frontend framework.

Evaluate:

- Accessibility
- Keyboard support
- Mobile/touch behavior
- Maintenance status
- Bundle size
- Integration complexity
- Reordering performance

Do not introduce a large dependency if an existing dependency or native implementation is sufficient.

## 8.8 Authentication UI

Determine necessary screens and flows for:

- Sign in
- Sign up, if required
- Account management
- List ownership
- Collaborator invitations
- Access denied
- Anonymous sharing

Do not overbuild identity management.

## 8.9 Design system

Audit existing:

- Components
- Colors
- Typography
- Spacing
- Buttons
- Icons
- Modals
- Forms
- Navigation
- Feedback messages

Propose incremental improvements.

Reuse the existing design system or UI component library.

Do not introduce a competing UI library without a strong reason.

## 8.10 Accessibility

Target WCAG 2.2 AA where practical.

Include:

- Keyboard operation
- Visible focus
- Screen-reader labels
- Sufficient contrast
- Accessible dialogs
- Accessible drag-and-drop alternatives
- Error announcements
- Reduced-motion preferences

## 8.11 UI/UX deliverables

Create documentation for:

- Existing screen inventory
- Reusable components
- Required new components
- Navigation changes
- User journeys
- Screen-by-screen migration
- Responsive behavior
- Merge preview UX
- Accessibility requirements
- Frontend state management changes

Use wireframes or Mermaid diagrams where helpful.

Do not generate an entirely new frontend implementation during this planning task.

---

# PART 9 — URL METADATA EXTRACTION

When a user adds a URL, the application should attempt to retrieve:

- Page title
- Description
- Favicon
- Open Graph image
- Relevant HTML metadata

The user must be able to override extracted metadata.

If metadata is unavailable, manual entry must still work.

## 9.1 Research implementation approaches

Compare:

- Standard HTTP clients
- HTML parsing
- Open Graph extraction
- Existing metadata extraction libraries
- Background workers
- Synchronous versus asynchronous extraction

Prefer lightweight approaches.

Do not introduce browser automation or headless Chromium unless there is a compelling requirement.

## 9.2 Security

User-submitted URLs are untrusted.

Investigate and mitigate SSRF vulnerabilities.

Consider:

- URL scheme restrictions
- Private/internal IP blocking
- Loopback protection
- Cloud metadata endpoints
- DNS rebinding
- Redirect validation
- DNS resolution and connection pinning
- Timeouts
- Maximum response sizes
- Content-type validation
- Rate limiting
- Unsafe HTML
- Malicious image payloads

Do not fetch arbitrary URLs without a clear security boundary.

## 9.3 Background processing

Evaluate whether Celery is justified.

If background workers are needed, consider reusing Redis if it already exists.

Do not introduce RabbitMQ merely because Celery supports it.

If a simpler solution is sufficient for the expected workload, explain the trade-offs.

## 9.4 Metadata race conditions

A delayed metadata job must not overwrite a user's manual edits.

For example:

```text
1. User creates Link.
2. Metadata extraction begins.
3. User manually changes title.
4. Metadata extraction completes.
```

The extraction result must not silently overwrite the manually edited title.

Design a safe approach using field provenance, version checks, or another appropriate mechanism.

Document retry and failure behavior.

---

# PART 10 — SEARCH AND DISCOVERY

Version 2 introduces a public directory.

Users should be able to discover public Lists and Groups.

Support:

- Search by title
- Search by description
- Filtering by tags
- Pagination
- Sorting
- Search inside Lists

Research PostgreSQL full-text search and indexing capabilities.

Prefer PostgreSQL for the initial implementation.

Do not introduce Elasticsearch, OpenSearch, or a hosted search service without demonstrating that PostgreSQL cannot meet the requirements.

Private and unlisted resources must not appear in public discovery results.

Search must not leak restricted metadata.

Evaluate appropriate database indexes.

---

# PART 11 — DATABASE AND MIGRATION STRATEGY

Produce a concrete migration strategy based on the actual database schema.

Do not assume that existing tables can be replaced without consequences.

## 11.1 Inspect current migrations

Identify:

- Existing schema
- Foreign keys
- Primary keys
- Unique constraints
- Existing data assumptions
- Migration history
- Potential data-loss risks

## 11.2 Preserve existing data

Plan how to migrate:

- Lists
- Links
- Short URLs
- Creator management tokens
- Expiration settings
- Existing metadata

Do not unnecessarily regenerate stable identifiers.

Where incompatible changes are unavoidable, document explicit migration steps.

## 11.3 Ownership transition

Version 1 may contain anonymously owned collections.

Version 2 introduces authenticated ownership.

Research suitable migration strategies.

Potential options include:

- Claiming existing Lists through verified management credentials.
- Maintaining legacy management access temporarily.
- Introducing nullable ownership during transition.
- Requiring an explicit account-claim operation.

Evaluate security risks.

Do not arbitrarily assign ownership to unrelated accounts.

## 11.4 Revision initialization

Determine how existing V1 Lists receive their initial V2 revision.

Historical changes that were never recorded cannot be reconstructed reliably.

Do not fabricate revision history.

Create a clearly identified initial baseline representing the actual migrated state.

## 11.5 Expiration

Version 1 originally retained collections for one month.

Version 2 supports permanent collections.

Preserve optional expiration.

Define the migration policy for existing expiration dates.

Do not silently convert all existing temporary collections into permanent collections or vice versa.

Document the chosen policy and its justification.

## 11.6 Database constraints

Research and propose appropriate:

- Foreign keys
- Unique constraints
- Check constraints
- Indexes
- Transaction boundaries
- Deletion policies
- Concurrency controls

Prefer database-enforced invariants where possible.

## 11.7 Rollback

Provide a realistic rollback plan.

Differentiate between:

- Rolling back an application deployment.
- Rolling back schema changes.
- Recovering data after migrations.
- Returning users to Version 1.

Do not assume all migrations are automatically reversible.

Version 1 and Version 2 share a Git history but should not be assumed to share an independently reversible production database.

Explain whether separate databases or environments are needed during migration and testing.

---

# PART 12 — API DESIGN

Inspect the existing API conventions.

Preserve compatible endpoints where practical.

Continue using Django REST Framework ViewSets.

The following endpoints are conceptual examples.

## Lists

```text
GET    /api/lists/
POST   /api/lists/
GET    /api/lists/{id}/
PATCH  /api/lists/{id}/
DELETE /api/lists/{id}/
```

## Links

```text
GET    /api/lists/{id}/links/
POST   /api/lists/{id}/links/
PATCH  /api/lists/{id}/links/{link_id}/
DELETE /api/lists/{id}/links/{link_id}/
POST   /api/lists/{id}/reorder/
```

## Groups

```text
GET    /api/groups/
POST   /api/groups/
GET    /api/groups/{id}/
PATCH  /api/groups/{id}/
DELETE /api/groups/{id}/

POST   /api/groups/{id}/lists/
DELETE /api/groups/{id}/lists/{list_id}/
POST   /api/groups/{id}/reorder/
```

## Branches and revisions

```text
POST   /api/lists/{id}/fork/
POST   /api/lists/{id}/branches/

GET    /api/lists/{id}/revisions/
GET    /api/lists/{id}/revisions/{revision}/
POST   /api/lists/{id}/restore/

GET    /api/lists/{id}/sync-preview/
POST   /api/lists/{id}/sync/
GET    /api/lists/{id}/sync-status/

GET    /api/lists/{id}/exclusions/
DELETE /api/lists/{id}/exclusions/{exclusion_id}/
```

Evaluate these against the current API structure.

Do not introduce breaking changes unnecessarily.

Document:

- Request schemas
- Response schemas
- Error responses
- Authentication requirements
- Authorization requirements
- Pagination
- Filtering
- Versioning
- Rate limiting
- Idempotency
- Concurrency preconditions

Recommend OpenAPI documentation where appropriate.

---

# PART 13 — TESTING STRATEGY

Produce a thorough testing plan before implementation.

Use the repository's existing test tooling where practical.

For Python, prefer pytest if compatible with the codebase.

## 13.1 Unit tests

Test pure domain behavior independently of Django where possible.

Focus on:

- Link identity
- List invariants
- Branch identity
- Revision generation
- Diff calculation
- Conflict detection
- Merge decisions
- Exclusions
- Permission policies

## 13.2 Integration tests

Test:

- Django repositories
- PostgreSQL transactions
- Revision persistence
- Concurrent updates
- Branch creation
- Merge application
- Rollback behavior
- Short URL resolution
- Metadata extraction

## 13.3 API tests

Test:

- CRUD
- Authentication
- Authorization
- Visibility
- Branch actions
- Merge preview
- Merge application
- Error handling
- Pagination
- Filtering

## 13.4 Frontend tests

Test:

- Existing V1 workflows
- Group navigation
- Link tiles
- Drag-and-drop
- Authentication
- Permission-dependent actions
- Branch creation
- Merge previews
- Conflict decisions
- Responsive layouts
- Accessibility

## 13.5 End-to-end tests

Propose E2E scenarios such as:

```text
Create account
    →
Create List
    →
Add Links
    →
Create Group
    →
Add List to Group
    →
Create Branch
    →
Modify Parent
    →
Preview Changes
    →
Resolve Conflict
    →
Apply Merge
    →
Verify Child
```

Use existing E2E tooling if available.

Avoid introducing multiple overlapping testing frameworks.

## 13.6 Concurrency tests

Explicitly test:

- Simultaneous Link edits
- Concurrent reordering
- Duplicate short codes
- Simultaneous merges
- Stale revisions
- Metadata races
- Duplicate requests
- Parent deletion during synchronization
- Concurrent permission changes

## 13.7 Regression tests

All existing V1 functionality that should remain supported must continue working.

Create a V1 regression checklist.

Do not remove tests simply because they fail after introducing V2.

If expected behavior changes, document the reason and replace obsolete tests with appropriate new acceptance tests.

---

# PART 14 — SECURITY REVIEW

Perform a focused threat-modeling exercise.

Include:

- Anonymous sharing
- Private collections
- Unlisted URLs
- Creator-token migration
- Authentication
- Authorization
- IDOR vulnerabilities
- Broken object-level authorization
- Short URL enumeration
- SSRF
- XSS
- CSRF
- Malicious URL schemes
- Open redirects
- Metadata fetching
- File and image handling
- Rate limiting
- Permission escalation
- Sensitive-data leakage
- Expired and deleted resources
- Concurrent permission changes

Research current OWASP guidance and framework-specific security recommendations.

Design mitigations appropriate for the application's actual threat model.

Avoid unnecessary security infrastructure.

Security should primarily be enforced through sound application design, framework protections, database constraints, and clear authorization rules.

---

# PART 15 — INFRASTRUCTURE AND DEPLOYMENT

Our preference is a straightforward, maintainable deployment.

The initial target architecture should remain a modular monolith unless the existing codebase or concrete requirements justify something else.

Preferred baseline:

```text
Frontend
   |
   v
Django REST API
   |
   v
PostgreSQL
```

Add only what is needed.

Potential additions:

```text
Redis
Celery Worker
Media Storage
```

Research whether each component is justified.

Do not introduce additional infrastructure simply because it is commonly used in large applications.

Specifically avoid unnecessary:

- Kubernetes
- RabbitMQ
- Kafka
- Microservices
- Separate search clusters
- Dedicated event stores
- Multiple databases
- Distributed caches

If Redis and Celery are needed, explain which concrete workloads require them.

For example, asynchronous metadata extraction may justify a worker.

Ordinary List CRUD does not.

## 15.1 Docker

Maintain Docker-based development.

Do not make Python virtual environments a required local workflow.

Inspect and extend existing Docker configuration.

Document:

- Services
- Dependencies
- Environment variables
- Volumes
- Health checks
- Startup order
- Database migrations
- Development commands
- Test commands

Avoid unnecessary duplicate Docker configurations.

## 15.2 Performance

Consider:

- N+1 queries
- Efficient List retrieval
- Group navigation queries
- Pagination
- Database indexing
- Revision snapshot size
- Merge computation complexity
- Background job throughput
- Redirect performance
- Caching

Do not optimize for hypothetical millions of users without evidence.

Identify realistic initial performance targets and assumptions.

## 15.3 Observability

Recommend lightweight, appropriate:

- Structured logging
- Error reporting
- Health checks
- Operational metrics
- Background task visibility
- Merge failure diagnostics

Avoid introducing a large observability stack unnecessarily.

---

# PART 16 — INTERNET RESEARCH REQUIREMENTS

**You must conduct current internet research before finalizing the architecture and migration plan.**

Do not rely exclusively on prior training knowledge.

Research relevant engineering patterns, security recommendations, framework documentation, maintained libraries, and real-world implementation approaches.

Prioritize:

1. Official documentation
2. Maintainer documentation
3. Established engineering references
4. High-quality technical articles
5. Well-maintained open-source implementations
6. Relevant community discussions

Research at least the following areas:

### Architecture

- Practical Onion Architecture in Django
- Hexagonal Architecture with Django REST Framework
- Domain-Driven Design for modular monoliths
- Transaction boundaries and aggregate consistency
- Pragmatic CQRS

### Versioning and synchronization

- Three-way merge algorithms
- Versioned collection management
- Conflict detection
- Tombstones and deletions
- Immutable snapshots
- Synchronization baselines
- Idempotent operations
- Optimistic concurrency control

### Database

- PostgreSQL JSONB snapshots
- PostgreSQL locking
- Transaction isolation
- Race-condition prevention
- Efficient ordered collections
- Migration best practices

### URL shortening

- Collision-resistant short IDs
- Random identifier strategies
- Redirect security
- URL normalization
- Stable resource mappings

### Metadata extraction

- Safe URL fetching
- Open Graph metadata
- Favicons
- SSRF prevention
- Background execution
- Metadata race-condition prevention

### Frontend

- Current best practices for the actual installed framework
- Accessible drag-and-drop
- Responsive sidebar navigation
- Conflict-resolution UI
- Design-system reuse
- Frontend state management
- API integration

### Security

- OWASP guidance
- Django security
- DRF object-level permissions
- Authentication strategies
- Safe media handling

### Git workflow

- Long-lived integration branches
- Pull request target enforcement
- Branch protection
- CI validation
- Maintaining parallel application versions

## 16.1 Research reporting

For every significant architectural recommendation:

- Identify the problem.
- Describe the recommended solution.
- Explain alternatives considered.
- Explain trade-offs.
- State the reason for the decision.
- Link to relevant sources.
- Include source publication or update dates when available.
- Identify whether the information was verified recently.

Distinguish:

- Verified facts
- Existing repository observations
- Architectural assumptions
- Recommendations
- Open questions

Do not invent citations or claim to have verified documentation that you could not access.

If internet access is unavailable, clearly document the limitation and identify the research that remains outstanding.

Do not silently substitute outdated knowledge.

---

# PART 17 — REQUIRED DOCUMENTATION

Create an organized documentation structure in the `v2` branch.

The exact filenames may be adapted to existing repository conventions.

Recommended structure:

```text
docs/
└── v2/
    │
    ├── README.md
    │
    ├── 01-V1-AUDIT.md
    ├── 02-PRODUCT-REQUIREMENTS.md
    ├── 03-ARCHITECTURE.md
    ├── 04-DOMAIN-MODEL.md
    ├── 05-DATABASE-DESIGN.md
    ├── 06-MIGRATION-PLAN.md
    ├── 07-REVISION-SPEC.md
    ├── 08-SYNCHRONIZATION-SPEC.md
    ├── 09-API-DESIGN.md
    ├── 10-FRONTEND-ARCHITECTURE.md
    ├── 11-UI-UX-MIGRATION.md
    ├── 12-AUTHORIZATION.md
    ├── 13-SECURITY.md
    ├── 14-INFRASTRUCTURE.md
    ├── 15-TEST-STRATEGY.md
    ├── 16-GIT-WORKFLOW.md
    ├── 17-IMPLEMENTATION-ROADMAP.md
    ├── 18-RISKS-AND-MITIGATIONS.md
    ├── 19-RESEARCH-REFERENCES.md
    ├── 20-DECISIONS-AND-OPEN-QUESTIONS.md
    │
    ├── adr/
    │   ├── README.md
    │   └── ...
    │
    └── diagrams/
        └── ...
```

Do not create empty placeholder files.

Each document must contain useful, concrete information.

Use Mermaid diagrams where appropriate.

## 17.1 V1 audit

Document the actual existing implementation.

Include:

- Existing architecture
- Models
- APIs
- Frontend components
- Infrastructure
- Tests
- Technical debt
- Reuse opportunities
- Compatibility risks

## 17.2 Product requirements

Document the full V2 feature set.

Differentiate:

- Mandatory MVP requirements
- Later enhancements
- Explicitly deferred features

Do not silently omit any feature from the supplied requirements.

## 17.3 Architecture

Provide:

- Component diagram
- Layer boundaries
- Dependency direction
- Module responsibilities
- Major interactions
- Justification for architectural decisions

## 17.4 Domain model

Document:

- Entities
- Aggregate roots
- Relationships
- Value objects
- Invariants
- Domain events, only if necessary
- Domain services
- Ownership rules

## 17.5 Database design

Provide:

- Proposed schema
- Foreign keys
- Indexes
- Unique constraints
- Deletion semantics
- Migration considerations
- Transaction boundaries

Use a Mermaid ER diagram.

## 17.6 Migration plan

Describe how Version 1 evolves into Version 2.

Include:

- Schema migrations
- Data migrations
- Authentication migration
- Short URL compatibility
- Revision initialization
- Frontend transition
- Deployment strategy
- Rollback strategy

## 17.7 Revision specification

Define:

- Snapshot schema
- Revision numbering
- Mutation rules
- Restoration
- Immutable history
- Metadata handling
- Atomicity
- Concurrency

## 17.8 Synchronization specification

This document must be especially detailed.

Define:

- Branch creation
- Source identities
- Three-way diff
- Field-level merge
- Conflict detection
- Accept
- Keep Local
- Exclude
- Baseline advancement
- Ordering
- Deletions
- Restoration
- Idempotency
- Concurrency
- Error scenarios

Include concrete examples and test scenarios.

## 17.9 API design

Describe endpoints, payloads, authorization, and responses.

## 17.10 Frontend architecture

Document:

- Current frontend structure
- Reusable components
- New components
- State management
- API integration
- UI migration dependencies

## 17.11 UI/UX migration

Document:

- Current screens
- New screens
- Modified screens
- User journeys
- Responsive layouts
- Merge preview experience
- Accessibility
- Error states

## 17.12 Security

Include a threat model and mitigations.

## 17.13 Infrastructure

Document required services and why they are necessary.

Provide minimal and optional infrastructure alternatives.

## 17.14 Test strategy

Provide a comprehensive acceptance test matrix.

Include unit, integration, API, frontend, E2E, and concurrency tests.

## 17.15 Git workflow

Document exactly how Version 1 and Version 2 coexist.

Include:

- `main` protection
- `v2` integration branch
- Feature branch creation
- Pull request targets
- CI checks
- Commit strategy
- Handling shared bug fixes

## 17.16 Implementation roadmap

Create an actionable implementation plan.

Each phase must include:

- Goals
- Dependencies
- Backend work
- Frontend work
- Database changes
- Infrastructure changes
- Tests
- Acceptance criteria
- Risks
- Definition of Done

Break phases into manageable tasks suitable for individual Claude Code sessions or pull requests.

Identify tasks that can be performed in parallel.

Avoid creating feature branches that become unnecessarily large.

## 17.17 Architecture Decision Records

Create ADRs for important decisions.

For example:

```text
ADR-001: Preserve List and Link
ADR-002: Modular Monolith
ADR-003: Immutable Revision Snapshots
ADR-004: Three-Way Merge
ADR-005: Child Ordering Policy
ADR-006: URL Shortening Strategy
ADR-007: Authentication Migration
ADR-008: Background Metadata Extraction
ADR-009: Git V2 Integration Branch
```

Use appropriate ADR conventions.

Each ADR should contain:

- Context
- Decision
- Alternatives
- Consequences
- Status

---

# PART 18 — IMPLEMENTATION ROADMAP

The implementation roadmap should be optimized for incremental delivery.

Use the following as an initial candidate, then refine it based on the actual repository.

## Phase 0 — Repository and baseline

- Inspect V1.
- Verify test baseline.
- Establish `v2`.
- Document architecture.
- Define compatibility requirements.

## Phase 1 — Domain evolution

- Extend List.
- Extend Link.
- Introduce User.
- Introduce memberships.
- Preserve short URLs.
- Make expiration optional.
- Update existing frontend workflows.

## Phase 2 — Groups

- Introduce Group.
- Introduce GroupList.
- Add Group permissions.
- Add APIs.
- Add Group frontend.
- Add sidebar navigation.

## Phase 3 — Revision history

- Introduce ListRevision.
- Implement immutable snapshots.
- Make mutations revision-aware.
- Implement restoration.
- Add history UI.

## Phase 4 — Branching

- Introduce ListBranch.
- Implement independent branch creation.
- Preserve source Link identity.
- Implement Fork.
- Add branch management UI.

## Phase 5 — Synchronization

- Implement diff engine.
- Implement conflict detection.
- Implement merge preview.
- Implement Accept.
- Implement Keep Local.
- Implement Exclude.
- Implement baseline advancement.
- Add merge UI.

## Phase 6 — Metadata and discovery

- Implement safe metadata extraction.
- Add background processing if justified.
- Implement tags.
- Implement public directory.
- Implement search and filtering.

## Phase 7 — Hardening

- Security tests.
- Concurrency tests.
- Regression tests.
- Performance review.
- Accessibility review.
- Documentation verification.
- Deployment readiness.

You may recommend a different ordering if technical dependencies justify it.

For example, metadata extraction may be implemented earlier if it provides immediate user value and does not block revision development.

**Do not turn this roadmap into an unnecessarily rigid waterfall process.**

Each phase should deliver a coherent, testable increment.

---

# PART 19 — RISKS AND PITFALLS

Explicitly identify and investigate potential problems.

At minimum, examine:

1. Accidental changes to main.
2. Pull requests targeting the wrong branch.
3. Database migration data loss.
4. Breaking V1 short URLs.
5. Authentication migration failures.
6. Unauthorized ownership claims.
7. Permission escalation.
8. Private-data leakage through Groups.
9. Revisions becoming inconsistent with Lists.
10. Concurrent revisions receiving duplicate numbers.
11. Branch ancestry corruption.
12. Cyclic branch relationships.
13. Lost local modifications.
14. Incorrect synchronization baselines.
15. Duplicate Links after repeated merges.
16. Incorrect deletion handling.
17. Restoring deleted Links.
18. Parent expiration with active children.
19. Background metadata overwriting manual edits.
20. SSRF.
21. Malicious redirects.
22. Broken mobile drag-and-drop.
23. Inaccessible conflict-resolution UI.
24. Unnecessary infrastructure.
25. Overengineering.
26. N+1 database queries.
27. Excessively large revision snapshots.
28. Stale frontend state.
29. Inconsistent API error handling.
30. Incomplete regression coverage.

For each risk, describe:

- Likelihood
- Impact
- Mitigation
- Test or validation strategy

Prioritize risks rather than treating all of them as equally important.

---

# PART 20 — EXPECTED EXECUTION PROCESS

Follow this order.

## Step 1 — Repository reconnaissance

Inspect the repository.

Record the current implementation.

Identify any critical discrepancies between the requirements and the existing application.

## Step 2 — Git safety

Inspect Git state.

Safely establish or reuse the `v2` integration branch.

Do not modify main.

Verify the active branch before writing files.

## Step 3 — Research

Perform internet research.

Prioritize up-to-date official and technical sources.

Record findings and references.

## Step 4 — Architecture evaluation

Compare multiple reasonable design approaches.

Identify which V1 components can remain unchanged.

Determine exactly what must evolve.

Avoid unnecessary rewrites.

## Step 5 — Domain and database design

Refine the models, relationships, invariants, and migration requirements.

Pay particular attention to immutable revision history and branch ancestry.

## Step 6 — Synchronization design

Produce the complete synchronization specification.

Resolve major correctness questions.

Use deterministic examples.

## Step 7 — Frontend/UI assessment

Inspect the actual existing UI.

Design a realistic V2 evolution.

Identify reusable components and necessary new flows.

## Step 8 — Infrastructure assessment

Determine whether additional services are necessary.

Justify each new dependency.

Prefer the current infrastructure whenever sufficient.

## Step 9 — Testing and security

Define acceptance criteria, security controls, regression coverage, and concurrency tests.

## Step 10 — Documentation

Create the required documentation in the `v2` branch.

Ensure the documents are consistent with one another.

Avoid contradictory assumptions.

## Step 11 — Roadmap

Produce an implementation sequence broken into manageable pull requests.

Every V2 pull request must target `v2`.

## Step 12 — Review

Perform a final architectural review from the perspectives of:

- Backend maintainability
- Domain correctness
- Database integrity
- Frontend maintainability
- User experience
- Security
- Performance
- Infrastructure simplicity
- Migration safety
- Testability

Identify unresolved decisions.

Make sensible recommendations rather than leaving every minor question unanswered.

## Step 13 — Final report

Produce a concise executive summary that includes:

1. Current V1 architecture.
2. Proposed V2 architecture.
3. What can be reused.
4. What must change.
5. Biggest technical risks.
6. Key research findings.
7. Recommended infrastructure.
8. Frontend/UI migration scope.
9. Proposed implementation phases.
10. Documentation created.
11. Git branch status.
12. Remaining decisions.
13. Recommended first implementation pull request.

Include a file tree showing the documentation produced.

Distinguish completed actions from recommendations and unperformed changes.

---

# PART 21 — DEFINITION OF DONE

The planning task is complete only when:

- [ ] V1 has been inspected.
- [ ] Existing backend architecture has been documented.
- [ ] Existing frontend architecture has been documented.
- [ ] Existing infrastructure has been documented.
- [ ] Existing tests have been assessed.
- [ ] The `main` branch remains untouched.
- [ ] A safe `v2` integration branch exists.
- [ ] V2 Git workflow is documented.
- [ ] Research has been completed or limitations explicitly reported.
- [ ] Relevant sources are recorded.
- [ ] The V2 domain model is documented.
- [ ] Database changes are planned.
- [ ] Authentication migration is planned.
- [ ] Existing short URLs are accounted for.
- [ ] Revision behavior is precisely specified.
- [ ] Branch creation is precisely specified.
- [ ] Three-way merge behavior is specified.
- [ ] Conflict resolution is specified.
- [ ] Concurrency and idempotency are addressed.
- [ ] UI/UX changes are documented.
- [ ] Existing UI components have been evaluated for reuse.
- [ ] Security risks are documented.
- [ ] Infrastructure additions are justified.
- [ ] A comprehensive testing strategy exists.
- [ ] A phased implementation roadmap exists.
- [ ] Feature branches and PRs are explicitly required to target `v2`.
- [ ] No Version 2 implementation has been prematurely started.
- [ ] No destructive Git operation has been performed.
- [ ] Documentation is internally consistent.
- [ ] The first implementation phase can begin without major architectural ambiguity.

---

# FINAL INSTRUCTIONS

Treat this as a real software architecture and migration assignment.

Do not merely summarize the requirements.

Investigate the actual repository.

Research alternative solutions.

Challenge assumptions when necessary.

Make technically justified decisions.

Preserve the existing application.

Avoid needless rewrites.

Avoid introducing dependencies and infrastructure without clear benefits.

Design against data corruption, race conditions, broken authorization, and synchronization inconsistencies.

Keep the application as a modular monolith unless there is a demonstrable need to change that.

Preserve `List` and `Link` as our central concepts.

Preserve the URL shortener.

Preserve stable resource identities.

Retain Django REST Framework ViewSets if the existing backend uses them.

Preserve Docker-based development.

Extend the existing frontend rather than automatically replacing it.

Treat version-control and synchronization correctness as higher priorities than architectural sophistication.

**Most importantly: Version 2 development belongs to the `v2` integration branch. Version 1 remains on `main`. Future V2 commits and pull requests must integrate into `v2`, never directly into `main`.**

Your immediate goal is to deliver a complete research-backed architectural plan and documentation.

Do not begin full implementation until the planning phase is complete and explicitly approved.

When the work is complete, report what you actually inspected, researched, created, and verified.

Do not claim that a Git policy, test, migration, or repository setting is complete unless you have verified it.

Begin by inspecting the existing repository and Git state.