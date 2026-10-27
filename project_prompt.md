# Project: Temporary Link Sharing & URL Shortening Service

## Your Role

Act as a Senior Python Software Engineer and Software Architect.

Your task is to design, implement, test, and Dockerize a complete backend application for a lightweight, anonymous, temporary link-sharing service.

The application is intended for team bonding. Someone creates a temporary list, adds interesting links, and shares the list's URL with colleagues.

Anyone with the shared URL can view the list, but only its creator can modify its contents.

The entire list expires after 30 days.

The application must also provide its own URL-shortening functionality.

**You must implement the actual application, not merely produce an architectural design or implementation plan.**

Follow clean architecture principles where appropriate, but avoid overengineering.

Prioritize:
- Maintainability
- Simplicity
- Security
- Performance
- Testability
- Clear separation of responsibilities
- Production-oriented engineering practices

---

# 1. CRITICAL REQUIREMENT: DOCKER-ONLY DEVELOPMENT

This is a non-negotiable architectural requirement.

**The entire project must be Dockerized.**

We do not want to use Python virtual environments.

DO NOT:
- Create `.venv` directories.
- Use `python -m venv`.
- Use `virtualenv`.
- Require Poetry or pip to be installed on the host.
- Install Python packages directly on the host machine.
- Require a locally installed PostgreSQL server.
- Require developers to execute Python scripts outside Docker.
- Depend on any host-installed Python interpreter.

All Python dependencies, application processes, database services, migrations, management commands, and automated tests must run inside Docker containers.

The developer should only need:
- Docker Engine or Docker Desktop
- Docker Compose
- Git
- A code editor

## Required Docker Services

Implement at least:

### `api`

The Django application.

Responsibilities:
- Serve REST API endpoints.
- Handle URL redirects.
- Execute business logic.
- Connect to PostgreSQL.

### `db`

PostgreSQL database.

Requirements:
- Use an official PostgreSQL Docker image.
- Configure persistence using Docker volumes.
- Configure health checks.
- Use environment variables for database credentials.

### `cleanup`

A lightweight container responsible for periodically deleting expired lists and their associated data.

Requirements:
- Reuse the application Docker image.
- Execute a Django management command.
- Run automatically on a daily schedule.
- Do not introduce Celery or Redis merely for scheduling.

You may use a minimal scheduler appropriate for a Docker Compose deployment.

## Development Experience

The following commands must work:

Start the application:

```bash
docker compose up --build -d
```

Stop the application:

```bash
docker compose down
```

Inspect logs:

```bash
docker compose logs -f api
```

Execute migrations:

```bash
docker compose exec api python manage.py migrate
```

Run automated tests:

```bash
docker compose run --rm api pytest
```

Create new migrations:

```bash
docker compose exec api python manage.py makemigrations
```

Run Django system checks:

```bash
docker compose exec api python manage.py check
```

These commands are illustrative of the required developer experience. Ensure the final configuration supports them correctly.

Use bind mounts where appropriate to enable automatic code reloading during development.

Provide a production-oriented application configuration separately from development settings.

The resulting repository must be reproducible from a clean checkout.

---

# 2. TECHNOLOGY STACK

Use:

| Component | Technology |
|---|---|
| Language | Python |
| Web framework | Django |
| REST API | Django REST Framework |
| Database | PostgreSQL |
| ORM | Django ORM |
| Testing | pytest + pytest-django |
| API Documentation | drf-spectacular / OpenAPI |
| Containerization | Docker |
| Orchestration | Docker Compose |
| HTTP server | Gunicorn for production |
| Dependency management | pyproject.toml or an equivalent lockable approach |

Use modern, stable, mutually compatible versions of these technologies.

Avoid unnecessary dependencies.

Do not introduce:
- Microservices
- Kubernetes
- Redis
- Celery
- Kafka
- RabbitMQ
- External URL-shortening services

The initial implementation should be a **modular monolith**.

---

# 3. APPLICATION REQUIREMENTS

The application provides temporary collections of links.

A creator can:

1. Create a list.
2. Receive a public sharing URL.
3. Receive a private ownership token.
4. Add links to the list.
5. Edit existing links.
6. Remove links.
7. Update the list's title.
8. Delete the entire list.

Anyone possessing the public sharing URL can:

1. Retrieve the list.
2. View its title.
3. View its links.
4. Access individual shortened URLs.

Visitors cannot modify anything.

There are no user accounts.

There is no registration.

There is no login system.

There is no concept of teams or memberships in the database.

Ownership is controlled entirely by a private token generated when the list is created.

---

# 4. LIST IDENTITY AND IMMUTABILITY

This is one of the most important business requirements.

**A list's identity must remain unchanged throughout its lifetime.**

When a list is created, it receives:

- An internal UUID.
- A public short code.
- A private ownership secret.
- A creation timestamp.
- An expiration timestamp.

The internal UUID and public short code must never change.

For example:

```text
List UUID:
550e8400-e29b-41d4-a716-446655440000

Public URL:
https://go.example.com/l/X7pKm2Qv8Nw4Rs6A
```

A creator can repeatedly add, update, and remove links.

The public list URL remains identical.

Visitors accessing the same URL must always retrieve the current contents of the list.

**Never recreate a list simply because its contents change.**

Use ordinary relational updates to manage its contents.

The list's expiration must not reset when content is modified.

---

# 5. URL SHORTENING STRATEGY

Implement an internal URL shortener.

Do not integrate with Bitly, TinyURL, or any other third-party shortening service.

## Internal Database Identifiers

Use UUIDs as primary keys.

UUIDv4 is acceptable.

UUIDv7 may be considered if supported cleanly by the selected technology stack, but its use must not unnecessarily complicate the application.

## Public Short Codes

Generate cryptographically secure random identifiers.

Recommended strategy:

- Generate 12 cryptographically random bytes.
- Encode them using URL-safe Base64.
- Remove Base64 padding.
- Produce a 16-character public code.

Use Python's `secrets` module.

Example:

```python
import base64
import secrets


def generate_short_code() -> str:
    random_bytes = secrets.token_bytes(12)

    return base64.urlsafe_b64encode(
        random_bytes
    ).decode("ascii").rstrip("=")
```

The resulting codes have 96 bits of entropy.

Do not use:
- Sequential public IDs.
- Truncated hashes without collision handling.
- Predictable random-number generators.
- Encryption of UUIDs merely to make them appear random.

There is no need to encrypt or cryptographically obfuscate UUIDs if the public codes are already generated securely.

## Collision Prevention

Enforce uniqueness at the database level.

Implement collision handling that:

1. Generates a random code.
2. Attempts insertion.
3. Detects a uniqueness violation for the code.
4. Generates another code.
5. Retries a bounded number of times.

The implementation must be safe when multiple application instances generate identifiers concurrently.

Avoid relying on a simple `SELECT` followed by `INSERT` as the only uniqueness mechanism.

Write automated tests that simulate collisions.

## Short URL Namespaces

List URLs:

```text
/l/{list_code}
```

Individual shortened URLs:

```text
/r/{redirect_code}
```

The namespaces must be distinct.

Use a configurable application base URL when constructing absolute links.

Never hardcode a production domain.

---

# 6. ANONYMOUS OWNERSHIP MODEL

When someone creates a list, generate two independent secrets:

### Public List Code

Used to access the list.

Can be shared freely.

### Private Ownership Token

Used to manage the list.

Generate at least 256 bits of cryptographically secure randomness.

Return the plaintext ownership token only in the successful list-creation response.

Never return it from public read endpoints.

Never store the plaintext ownership token in PostgreSQL.

Instead, store a SHA-256 digest of the generated token.

Since the token is already a high-entropy randomly generated secret, SHA-256 is appropriate.

Use constant-time digest comparison during verification.

Owner-only API operations must require:

```http
Authorization: Bearer <owner_token>
```

The ownership token must be validated against the specific list being modified.

A token belonging to one list must not authorize changes to another list.

Avoid including ownership tokens in:
- URLs
- Query parameters
- Logs
- Exception messages
- Public API responses
- Generated API documentation examples containing real secrets

There is no ownership recovery mechanism in the MVP.

Document clearly that a lost ownership token cannot be recovered.

---

# 7. DATABASE DESIGN

Design the following three entities.

## 7.1 SharedList

Recommended fields:

```text
id                  UUID (PK)
public_code         VARCHAR(16), UNIQUE
owner_token_hash    CHAR(64)
title               VARCHAR(255)
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
expires_at          TIMESTAMPTZ
```

Requirements:

- UUID primary key.
- Immutable public code.
- Immutable creation and expiration timestamps.
- Mutable title.
- Database index supporting expiration cleanup.
- Correct timezone-aware timestamps.

## 7.2 SharedLink

Recommended fields:

```text
id                  UUID (PK)
list_id             UUID (FK)
destination_url     TEXT
title               VARCHAR(255), NULL
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

Requirements:

- Every link belongs to exactly one list.
- A list can contain multiple links.
- Destination URLs can be edited.
- Deleting a list must delete its links.
- Provide appropriate foreign-key indexes.

Prevent duplicate destination URLs within the same list using a clearly defined normalization strategy.

Avoid unexpectedly modifying URL semantics during normalization.

## 7.3 ShortRedirect

Recommended fields:

```text
code                VARCHAR(16), UNIQUE
link_id             UUID (FK)
is_active           BOOLEAN
created_at          TIMESTAMPTZ
```

This entity maps a public short code to a `SharedLink`.

Its purpose is to separate public URL identity from the underlying destination.

The short code must remain unchanged when the creator edits the original link's destination.

For the MVP, create exactly one active short redirect for each shared link.

The schema may support multiple aliases in the future, but do not implement alias-management functionality now.

Deleting a link must invalidate and remove its associated redirect mapping.

Deleting a list must cascade through its links and redirect mappings.

Choose appropriate database indexes and uniqueness constraints.

Use Django migrations to create the schema.

---

# 8. URL MAINTENANCE RULES

Public identifiers must remain stable.

Consider this example:

Original destination:

```text
https://example.com/old-article
```

Generated short URL:

```text
https://go.example.com/r/Ab3Kp7Nq2Wz8Lm5R
```

Later, the creator changes the destination to:

```text
https://example.com/new-article
```

The short URL must remain:

```text
https://go.example.com/r/Ab3Kp7Nq2Wz8Lm5R
```

Only the destination mapping changes.

The short code must not be regenerated.

If a shared link is deleted:

- Its short URL stops working.
- Its redirect mapping is deleted.
- It must not silently point to another existing link.
- Recreating the same destination later produces a new link record and a new short code.

Do not intentionally reuse previously generated short codes.

For the MVP, storing a permanent registry of expired codes is unnecessary because the 96-bit code space makes accidental reuse extremely unlikely.

Document that without permanent reservations, mathematical non-reuse cannot be guaranteed after deletion.

---

# 9. LIST EXPIRATION AND RETENTION

Every list expires exactly 30 days after creation.

Use:

```python
expires_at = created_at + timedelta(days=30)
```

Use UTC-aware datetimes.

The expiration timestamp must remain immutable.

Activity must not extend the lifetime.

Changing the title must not extend the lifetime.

Adding or removing links must not extend the lifetime.

## API-Level Expiration

Every operation involving an existing list must verify that the list has not expired.

Expired lists must become inaccessible immediately, regardless of whether cleanup has executed.

Return:

```http
410 Gone
```

for an expired list or redirect when the expired record still exists.

Return:

```http
404 Not Found
```

for unknown or already physically deleted resources.

## Scheduled Cleanup

Implement:

```bash
python manage.py cleanup_expired
```

The management command must:

1. Find expired lists.
2. Delete them.
3. Cascade deletion to associated links.
4. Remove associated redirect mappings.
5. Report the number of deleted records.
6. Be safe to execute repeatedly.

The cleanup operation must be idempotent.

Run it automatically through the Dockerized cleanup service, approximately once per day.

Do not require host-level cron installation.

The cleanup process must not block API requests.

Use reasonable batching or another appropriate strategy so the cleanup remains maintainable as data volume increases.

Physical deletion may occur up to roughly 24 hours after expiration, while API access must stop at the exact expiration timestamp.

---

# 10. REST API CONTRACTS

Use versioned API endpoints.

Base path:

```text
/api/v1/
```

## 10.1 Create List

```http
POST /api/v1/lists/
```

Public endpoint.

Example request:

```json
{
  "title": "Friday Team Bonding"
}
```

Example response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "public_code": "X7pKm2Qv8Nw4Rs6A",
  "public_url": "https://go.example.com/l/X7pKm2Qv8Nw4Rs6A",
  "owner_token": "<secure-random-token>",
  "created_at": "2026-10-27T20:00:00Z",
  "expires_at": "2026-11-26T20:00:00Z"
}
```

Return HTTP `201 Created`.

This must be the only API response containing the ownership token.

## 10.2 Retrieve List

```http
GET /api/v1/lists/{list_code}/
```

Public endpoint.

Return:

- List ID.
- Title.
- Public code.
- Creation timestamp.
- Expiration timestamp.

Never return the ownership token or its hash.

## 10.3 Retrieve List Links

```http
GET /api/v1/lists/{list_code}/links/
```

Public endpoint.

Requirements:

- Paginated.
- Newest first by default.
- Stable deterministic ordering.
- Return both destination URLs and short URLs.
- No ownership token required.

Example link representation:

```json
{
  "id": "8f6d9f1c-20a2-4c95-a038-69190c848e8a",
  "title": "Interesting Article",
  "destination_url": "https://example.com/article",
  "short_url": "https://go.example.com/r/Ab3Kp7Nq2Wz8Lm5R",
  "created_at": "2026-10-27T20:10:00Z"
}
```

## 10.4 Update List

```http
PATCH /api/v1/lists/{list_code}/
```

Creator only.

Allow changing the title.

Do not allow changing:

- UUID
- Public code
- Ownership hash
- Creation timestamp
- Expiration timestamp

## 10.5 Delete List

```http
DELETE /api/v1/lists/{list_code}/
```

Creator only.

Return HTTP `204 No Content`.

Delete associated data through properly configured cascade relationships.

## 10.6 Add Link

```http
POST /api/v1/lists/{list_code}/links/
```

Creator only.

Example request:

```json
{
  "title": "Interesting Article",
  "destination_url": "https://example.com/article"
}
```

Requirements:

- Validate destination.
- Enforce per-list link limits.
- Prevent duplicates.
- Create a `SharedLink`.
- Generate its short redirect.
- Return the created link.

Creating the link and its redirect mapping must be atomic.

Use a database transaction.

## 10.7 Update Link

```http
PATCH /api/v1/lists/{list_code}/links/{link_id}/
```

Creator only.

Allow updating:

- Title.
- Destination URL.

Never modify the existing short code as a side effect.

Ensure the link belongs to the specified list.

## 10.8 Delete Link

```http
DELETE /api/v1/lists/{list_code}/links/{link_id}/
```

Creator only.

Return HTTP `204 No Content`.

Invalidate its redirect mapping.

## 10.9 Resolve Short URL

```http
GET /r/{redirect_code}
```

Public endpoint.

Behavior:

1. Find the redirect mapping.
2. Resolve the associated link.
3. Resolve its parent list.
4. Verify the list is active.
5. Verify the redirect is active.
6. Return a temporary HTTP redirect.

Use:

```http
302 Found
```

Response headers:

```http
Location: https://example.com/article
Cache-Control: no-store
Referrer-Policy: no-referrer
```

Do not use permanent redirects.

The destination may change during the lifetime of a list.

## 10.10 Public List Short URL

```http
GET /l/{list_code}
```

Provide a backend-only resolution strategy.

Because we are not building a frontend, this endpoint may return the list's JSON representation or redirect to its public API representation.

Choose one consistent behavior and document it.

Do not build HTML templates or frontend views.

---

# 11. VALIDATION AND BUSINESS RULES

Implement the following constraints.

### List Constraints

- Maximum title length: 255 characters.
- Maximum 100 links per list.
- Fixed lifetime: 30 days.
- Immutable identity.
- No anonymous modifications without an ownership token.

### Link Constraints

- Only HTTP and HTTPS destination URLs are allowed.
- Reject malformed URLs.
- Reject URLs containing embedded credentials.
- Reject unsupported schemes.
- Enforce a reasonable maximum URL length.
- Reject duplicates within the same list.
- Ensure redirects never point to a different list's links accidentally.

Use a consistent URL normalization policy.

Avoid aggressive transformations that could change the meaning of destinations.

For example, do not reorder query parameters or remove query parameters without an explicit business reason.

### Concurrent Requests

Consider race conditions.

In particular:

- Concurrent list creation.
- Concurrent short-code generation.
- Concurrent link creation near the 100-link limit.
- Concurrent deletion and modification.
- Expiration occurring during a request.

Use appropriate database transactions, constraints, and locking where necessary.

---

# 12. SECURITY REQUIREMENTS

Although the application has no accounts, it must still follow sound security practices.

Implement:

- Cryptographically secure identifier generation.
- Secure ownership-token generation.
- Ownership-token hashing.
- Constant-time token verification.
- List-scoped authorization.
- URL input validation.
- Protection against mass assignment.
- Appropriate request-size limits.
- Maximum links per list.
- Rate limiting for anonymous list creation.
- Rate limiting for sensitive management operations.
- Safe HTTP redirect handling.
- No logging of ownership credentials.
- Environment-based secrets.
- Sensible production security settings.

Do not trust client-provided list IDs, expiration values, or ownership identifiers.

The backend must determine ownership and expiration from its own stored state.

For the MVP, do not automatically fetch arbitrary destination URLs to generate previews.

This avoids introducing unnecessary server-side request forgery risks.

Do not introduce a Redis dependency solely for rate limiting.

Use a suitable simple implementation, clearly documenting any limitations in distributed deployments.

Because this is an anonymous URL-sharing service, document risks related to phishing, abusive redirects, public token exposure, and bearer-token theft.

All management actions must take place over HTTPS in production.

---

# 13. SOFTWARE ARCHITECTURE

Use a modular monolith.

Prefer a clear separation between:

1. HTTP/API layer.
2. Application services.
3. Domain rules.
4. Persistence.
5. Infrastructure utilities.

Do not unnecessarily reproduce Java-style enterprise architecture in Python.

Do not create abstractions that have no practical value.

## Suggested Project Structure

```text
backend/
├── config/
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── sharing/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   ├── selectors.py
│   │   ├── services/
│   │   │   ├── lists.py
│   │   │   └── links.py
│   │   ├── management/
│   │   │   └── commands/
│   │   │       └── cleanup_expired.py
│   │   └── tests/
│   │
│   └── shortener/
│       ├── __init__.py
│       ├── models.py
│       ├── generators.py
│       ├── services.py
│       ├── views.py
│       ├── urls.py
│       └── tests/
│
├── tests/
│   ├── conftest.py
│   └── integration/
│
├── docker/
│   ├── entrypoint.sh
│   └── Dockerfile
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── decisions.md
│   └── security.md
│
├── manage.py
├── pyproject.toml
├── compose.yaml
├── compose.prod.yaml
├── .env.example
├── .dockerignore
├── .gitignore
├── README.md
└── Makefile
```

This structure is a starting point, not a requirement to create unnecessary files.

Adjust it where doing so produces a cleaner, more idiomatic Django implementation.

Do not duplicate models or business logic between applications.

The sharing application should own lists and their content.

The shortener application should own short-code generation, mappings, and redirect resolution.

Keep boundaries between the modules explicit.

Use dependency injection only where it adds practical value.

Prefer Django ORM rather than creating a redundant generic repository abstraction.

---

# 14. TESTING REQUIREMENTS

Use pytest and pytest-django.

Provide comprehensive automated tests.

## List Tests

Test:

1. Creating a list.
2. Generating a UUID.
3. Generating a public short code.
4. Generating a private ownership token.
5. Hashing the ownership token.
6. Reading a list anonymously.
7. Rejecting unauthorized updates.
8. Accepting authorized updates.
9. Preventing changes to immutable fields.
10. Deleting a list.
11. Preventing access after expiration.

## Link Tests

Test:

1. Adding links.
2. Editing links.
3. Removing links.
4. Rejecting unauthorized changes.
5. Rejecting duplicate URLs.
6. Rejecting invalid URL schemes.
7. Enforcing the maximum link count.
8. Preventing modifications across lists.
9. Handling concurrent operations correctly.
10. Preserving short codes after destination updates.

## Shortener Tests

Test:

1. Generating 16-character Base64URL codes.
2. Resolving valid codes.
3. Redirecting with HTTP 302.
4. Returning 404 for unknown codes.
5. Returning 410 for expired resources.
6. Handling simulated identifier collisions.
7. Enforcing database uniqueness.
8. Preventing redirects after link deletion.
9. Preserving existing codes during destination changes.
10. Rejecting inactive redirects.

## Expiration Tests

Test:

1. Exact 30-day expiration.
2. Expiration with timezone-aware timestamps.
3. Editing contents does not extend expiration.
4. Expired lists become inaccessible before cleanup.
5. Cleanup deletes expired lists.
6. Cleanup cascades to related records.
7. Cleanup never deletes active lists.
8. Running cleanup repeatedly is safe.

## Integration Tests

Use PostgreSQL as the test database.

Test the complete workflow:

```text
Create List
    ↓
Receive Public URL + Owner Token
    ↓
Add Links
    ↓
Retrieve List Anonymously
    ↓
Resolve Short URLs
    ↓
Update Link Destination
    ↓
Verify Short URL Is Unchanged
    ↓
Delete Link
    ↓
Verify Redirect Is Invalid
    ↓
Expire List
    ↓
Verify 410 Response
    ↓
Execute Cleanup
    ↓
Verify Records Deleted
```

Do not rely exclusively on mocked database interactions.

Test actual Django ORM operations and database constraints.

All tests must be executable inside Docker.

---

# 15. API DOCUMENTATION

Integrate drf-spectacular.

Expose:

```text
/api/schema/
/api/docs/
/api/redoc/
```

Document:
- Endpoints.
- Authentication requirements.
- Request schemas.
- Response schemas.
- Error responses.
- Pagination.
- Expiration behavior.
- Ownership-token behavior.
- URL-shortening behavior.

Mark the ownership-token authorization requirements correctly in OpenAPI.

Do not accidentally mark public read endpoints as authenticated.

---

# 16. DOCKER AND DEPLOYMENT DETAILS

Implement a high-quality Docker configuration.

## Dockerfile

Requirements:

- Use an official Python base image.
- Prefer a slim image.
- Install only required system dependencies.
- Use a reproducible dependency installation process.
- Optimize layer caching.
- Avoid unnecessary build tools in the final image.
- Run the application as a non-root user in production.
- Exclude development files and secrets from the image.
- Support development and production configurations cleanly.

## Docker Compose

Requirements:

- API container.
- PostgreSQL container.
- Cleanup container.
- Persistent database volume.
- Health checks.
- Environment variable configuration.
- Proper service dependencies.
- Appropriate restart policies.

Ensure that the application does not attempt to connect to PostgreSQL before it is ready.

Do not treat a running database container as proof that PostgreSQL is ready to accept connections.

## Environment Configuration

Provide:

```text
.env.example
```

Include at least:

```text
DJANGO_SETTINGS_MODULE
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS

POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_HOST
POSTGRES_PORT

DATABASE_URL

PUBLIC_BASE_URL
```

Feel free to improve this configuration and remove redundant variables where appropriate.

Do not commit real secrets.

Ensure `.gitignore` excludes `.env`.

## Production Considerations

Provide production-oriented settings covering:

- HTTPS.
- Secure cookies where relevant.
- Trusted hosts.
- Proxy headers.
- Database connection management.
- Gunicorn workers.
- Appropriate request timeouts.
- Structured or reasonably consistent logging.

The production deployment must not use Django's development server.

---

# 17. DOCUMENTATION

Create a comprehensive README.

The README should explain:

### Overview

What the application does.

### Architecture

How its components interact.

### Database

Relationships between SharedList, SharedLink, and ShortRedirect.

### Docker Setup

How to start the entire environment from a clean checkout.

### Development

How to run Django commands inside Docker.

### Testing

How to run tests inside Docker.

### Migrations

How to generate and apply migrations.

### API

How to access OpenAPI and Swagger documentation.

### Ownership

How the creator stores and submits the private ownership token.

### Expiration

How the 30-day expiration and scheduled cleanup operate.

### Deployment

How to configure production settings and start the application.

Provide concrete curl examples showing:

1. Creating a list.
2. Extracting the ownership token.
3. Adding a link.
4. Viewing a list anonymously.
5. Updating a destination.
6. Resolving its shortened URL.
7. Deleting a link.

Clearly distinguish public and private information in examples.

---

# 18. IMPLEMENTATION PROCESS

Work incrementally.

Before writing application code:

1. Inspect the existing repository.
2. Identify whether a Django project already exists.
3. Preserve relevant existing files.
4. Present a concise implementation plan.
5. Establish the final database relationships.
6. Identify any architectural conflicts in the requirements.

Then implement in this order:

## Phase 1: Project Infrastructure

- Django project.
- Configuration.
- Dependencies.
- Dockerfile.
- Docker Compose.
- PostgreSQL.
- Health checks.
- Application startup.

## Phase 2: Domain Models

- SharedList.
- SharedLink.
- ShortRedirect.
- Database migrations.
- Constraints.
- Indexes.

## Phase 3: Security and Identification

- Secure token generation.
- Ownership-token hashing.
- Ownership verification.
- Short-code generation.
- Collision handling.

## Phase 4: Business Logic

- List creation.
- List updates.
- Link management.
- Expiration checks.
- Redirect mapping management.

## Phase 5: REST API

- Serializers.
- Permissions.
- ViewSets or API views.
- Routing.
- Pagination.
- Error handling.

## Phase 6: URL Resolution

- Short redirect endpoint.
- List short URL endpoint.
- Cache-control headers.
- Expiration handling.

## Phase 7: Cleanup

- Management command.
- Dockerized periodic execution.
- Cascade deletion.

## Phase 8: Testing

- Unit tests.
- Integration tests.
- Security tests.
- Collision tests.
- Expiration tests.

## Phase 9: Documentation and Verification

- OpenAPI.
- README.
- Architecture documentation.
- Docker verification.
- Test execution.
- Django system checks.

Proceed through all phases. Do not stop after producing the plan unless a genuine blocking issue prevents implementation.

---

# 19. CODE QUALITY STANDARDS

Use idiomatic, maintainable Python.

Requirements:

- PEP 8 compliance.
- Type hints where useful.
- Clear function and class names.
- Small, cohesive functions.
- Explicit error handling.
- Transactional integrity.
- Testable business logic.
- Minimal duplication.
- Consistent formatting.
- Sensible logging.
- No hardcoded credentials.
- No unnecessary abstraction layers.
- No speculative features.

Use tools such as Ruff where appropriate.

Avoid building an unnecessarily complicated Clean Architecture framework.

The project should remain understandable to an experienced Django engineer who joins the project later.

---

# 20. IMPORTANT ARCHITECTURAL INVARIANTS

The following rules must never be violated.

**Invariant 1: Stable List Identity**

A list's UUID and public short code never change during its lifetime.

**Invariant 2: Mutable List Contents**

The creator may add, update, and delete links without changing the list's identity.

**Invariant 3: Stable Short URLs**

Updating a link's destination never changes its existing short URL.

**Invariant 4: Anonymous Public Read Access**

Anyone with the public list URL can retrieve its contents.

**Invariant 5: Creator-Only Modification**

Only a request containing the correct private ownership token may modify a list or its links.

**Invariant 6: Fixed Expiration**

Every list expires 30 days after creation. Activity never renews its lifetime.

**Invariant 7: Inherited Link Expiration**

All links and short redirects become inaccessible when their parent list expires.

**Invariant 8: Secure Code Generation**

Public short codes are cryptographically random and protected by database uniqueness constraints.

**Invariant 9: Atomic Operations**

Operations that create or modify multiple related database records must preserve consistency.

**Invariant 10: Docker-Only Execution**

All application execution, dependencies, tests, migrations, and background maintenance must operate inside Docker containers.

---

# 21. DEFINITION OF DONE

The project is complete only when:

- [ ] The application starts through `docker compose up --build -d`.
- [ ] PostgreSQL starts successfully.
- [ ] Django connects to PostgreSQL.
- [ ] Migrations execute successfully.
- [ ] Public list creation works.
- [ ] Ownership tokens are generated securely.
- [ ] Ownership authorization works.
- [ ] Anonymous read access works.
- [ ] Unauthorized modifications are rejected.
- [ ] Links can be added, edited, and removed.
- [ ] List IDs remain unchanged after edits.
- [ ] List public URLs remain unchanged after edits.
- [ ] Individual short URLs remain unchanged after destination edits.
- [ ] Redirects return HTTP 302.
- [ ] Identifier collisions are handled.
- [ ] Database uniqueness is enforced.
- [ ] Lists expire after 30 days.
- [ ] Expired content is inaccessible.
- [ ] Scheduled cleanup works.
- [ ] Expired records are physically deleted.
- [ ] Automated tests pass.
- [ ] OpenAPI documentation works.
- [ ] The README contains complete Docker instructions.
- [ ] No virtual environment is required.
- [ ] No host-level Python dependency installation is required.

You must actually execute the available verification commands rather than merely state that the implementation should work.

If tests or Docker commands fail, investigate and fix the problem.

Do not claim successful verification for commands you did not execute.

---

# 22. FINAL INSTRUCTIONS

Implement this project as a complete, maintainable Django backend.

Use the simplest architecture that correctly satisfies all requirements.

Do not add frontend code.

Do not introduce user accounts.

Do not add unnecessary infrastructure.

Do not create a Python virtual environment.

**Everything must run inside Docker.**

Make reasonable engineering decisions for unspecified implementation details and document them.

When implementation is complete:

1. Summarize the final architecture.
2. Explain any significant technical decisions.
3. Show the repository structure.
4. List the API endpoints.
5. Provide the exact Docker commands to run the application.
6. Report the actual test results.
7. Identify any remaining limitations or production-readiness concerns.

**Begin by inspecting the repository and producing a concise implementation plan. Then implement the complete project.**

delete unneeded files first though like initial project example. 