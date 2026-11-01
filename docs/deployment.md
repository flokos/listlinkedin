# Deploying and operating listlinkedin

This guide runs the production stack ([compose.prod.yaml](../compose.prod.yaml)) on one server
with Docker Compose, and keeps it running. Development setup is in the root
[README.md](../README.md). The reasons behind the infrastructure are in
[docs/v2/14-INFRASTRUCTURE.md](v2/14-INFRASTRUCTURE.md).

## What runs

| Service | Role | Published |
|---|---|---|
| `nginx` | TLS, the built Vue app, `/media/` (uploaded and fetched images), and a proxy to the API for `/api/`, `/_allauth/`, `/r/` and `/healthz`. Security headers and a Content Security Policy | ports 80 and 443 |
| `api` | Django under Gunicorn (`WEB_CONCURRENCY` workers, 30 s timeout) | no: only nginx reaches it |
| `worker` | Background tasks from the PostgreSQL queue: fetching link details, processing images. `WORKER_REPLICAS` copies | no |
| `cleanup` | Scheduled jobs ([below](#scheduled-jobs)) | no |
| `migrate` | Runs once at every start: `migrate`, then `createcachetable`. The others start only after it succeeds | no |
| `db` | PostgreSQL 17, volume `pgdata` | no |

Volumes: `pgdata` (the database) and `media` (images). Back up both ([Backups](#backups)).

## The server

- Linux with **rootful** Docker Engine and the Compose plugin. Rootless Docker's default port
  forwarding replaces every client's IP with the gateway's, so all clients would share one
  rate limit. If you must run rootless, use the `slirp4netns` port driver.
- A DNS name pointing at the server, and ports 80 and 443 open.
- An SMTP relay for account email and reports.
- Size: the [performance targets](v2/14-INFRASTRUCTURE.md#performance-targets-initial) were
  measured on 4 cores and 7 GB of RAM with 100,000 public lists. A smaller VM (2 vCPUs, 2–4
  GB) serves a team easily. The database and images grow with use. Leave room for 14 days of
  backups if they stay on the same disk before being copied off.
- The containers' logs rotate at 5 × 20 MB each.

The production host on Oracle Cloud (Always Free, `eu-frankfurt-1`) is created with Terraform:
[infra/terraform/](../infra/terraform/README.md) ([ADR-017](v2/adr/ADR-017-production-on-oci-always-free.md)).
It meets the list above and leaves `/srv/listlinkedin` ready for the steps below.

## Configuration

Copy [.env.example](../.env.example) to `.env` next to `compose.prod.yaml` and set the values.
`.env` holds secrets: keep it out of Git (it's ignored) and readable only by you
(`chmod 600 .env`). Compose refuses to start while a required value is missing.

**Required:**

| Variable | What |
|---|---|
| `DJANGO_SECRET_KEY` | A long random string, e.g. `openssl rand -base64 48`. Changing it signs everyone out and invalidates password-reset links |
| `DJANGO_ALLOWED_HOSTS` | The public hostname, e.g. `go.example.com` (comma-separated if several) |
| `PUBLIC_BASE_URL` | `https://<hostname>`. Used for every absolute URL the app hands out: list addresses, short URLs, email links |
| `SERVER_NAME` | The hostname nginx answers to. Other names are refused |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | The database. Used when `pgdata` is first created. Changing them later doesn't change the existing database |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | The SMTP relay. Port 587 with `EMAIL_USE_TLS=true` by default |
| `MODERATION_EMAIL` | Where reports go. Without it, reports are only logged |

**Optional:**

| Variable | Default | What |
|---|---|---|
| `DEFAULT_FROM_EMAIL` | `listlinkedin <no-reply@{host}>` | The sender of every email |
| `EMAIL_TIMEOUT` | `10` | Seconds. Mail is sent during the request, so a relay slower than this fails it |
| `DJANGO_NUM_PROXIES` | `1` | Proxies in front of the API (1 is the bundled nginx). Add one for each load balancer in front of nginx, or rate limits see the balancer's address |
| `BLOCKED_DESTINATION_HOSTS` | empty | Comma-separated hosts links may not point to, subdomains included. It applies to existing links too: their short URLs answer 410. This site's own host is always blocked |
| `WEB_CONCURRENCY` | `3` | Gunicorn worker processes |
| `WORKER_REPLICAS` | `2` | Worker containers, each running one task at a time |
| `METADATA_FETCH_ENABLED` | `true` | `false`: never fetch link details, for a deployment that must not contact other sites |
| `FETCH_BLOCKED_NETWORKS` | empty | Extra CIDRs the fetcher never connects to, added to its built-in private, loopback, link-local and cloud-metadata ranges. For internal services on public addresses |
| `THROTTLE_LIST_CREATE`, `THROTTLE_LIST_MANAGE`, `THROTTLE_GROUP_CREATE`, `THROTTLE_GROUP_MANAGE`, `THROTTLE_ACCOUNT`, `THROTTLE_UPLOAD`, `THROTTLE_RESTORE`, `THROTTLE_METADATA_REFRESH`, `THROTTLE_DIRECTORY`, `THROTTLE_REPORT` | see [.env.example](../.env.example) | Rate limits in DRF syntax (`30/hour`). Keep the defaults unless you have a reason ([13](v2/13-SECURITY.md#rate-limits)) |
| `DB_LOCK_TIMEOUT`, `DB_STATEMENT_TIMEOUT` | `5s`, `20s` | The API's PostgreSQL waits. Keep the statement cap below Gunicorn's 30 s. `migrate` runs without one |
| `LOG_FORMAT` | `json` | One JSON object per log line. `text` is easier to read by eye |
| `TLS_CERT_DIR` | `./deploy/certs` | The directory holding `fullchain.pem` and `privkey.pem` |
| `ACME_WEBROOT` | `./deploy/acme` | Let's Encrypt HTTP-01 challenges, served at `/.well-known/acme-challenge/` |
| `HTTP_PORT`, `HTTPS_PORT` | `80`, `443` | Host ports for nginx |
| `MAINTENANCE_DIR` | `./deploy/maintenance` | The directory holding the maintenance page and its `on` switch ([below](#maintenance-mode)). Tests point it elsewhere so they can't switch a real stack |

Development and test switches never belong in production: `DJANGO_EMAIL_BACKEND`,
`AUTH_RATE_LIMITS=off` and `FETCH_TEST_HOSTS`. The production
compose file doesn't pass them.

## First deploy

1. **Get the code** on the server: `git clone https://github.com/flokos/listlinkedin.git
   /srv/listlinkedin && cd /srv/listlinkedin`. Check out the release tag you are deploying.
2. **Configure** `.env` ([above](#configuration)).
3. **Get a certificate** into `TLS_CERT_DIR` as `fullchain.pem` and `privkey.pem`. With
   Let's Encrypt, issue the first one while the stack is down, since port 80 must be free:

   ```bash
   docker run --rm -p 80:80 -v /etc/letsencrypt:/etc/letsencrypt certbot/certbot \
     certonly --standalone -d go.example.com
   mkdir -p deploy/certs
   sudo cp -L /etc/letsencrypt/live/go.example.com/{fullchain,privkey}.pem deploy/certs/
   ```

   nginx serves `ACME_WEBROOT`, so renewals run while the stack is up:
   `certbot renew --webroot -w deploy/acme`. Copy the files again afterwards and reload nginx
   with `docker compose -f compose.prod.yaml exec nginx nginx -s reload`. A certbot
   `--deploy-hook` can do both.
4. **Start and check:**

   ```bash
   docker compose -f compose.prod.yaml up --build -d --wait
   docker compose -f compose.prod.yaml exec api python manage.py check --deploy
   curl https://go.example.com/healthz          # {"status": "ok"}
   docker compose -f compose.prod.yaml ps       # api and worker: healthy
   ```

5. **Try it:** sign up, confirm the email, create a list, add a link, and open its short URL.
   The link's title and icon appear within seconds when the worker can reach the site.
6. **Schedule** [backups](#backups) and [monitoring](#monitoring).

Before a public launch, [deploy/smoke-test.sh](../deploy/smoke-test.sh) runs the same stack
in an isolated project with a throwaway certificate. It checks the TLS redirect, headers,
host filtering, body limits, client-IP handling and a background task:
`bash deploy/smoke-test.sh`.

**Internal-only deployment:** uncomment the `allow` and `deny` block in
[deploy/nginx/default.conf.template](../deploy/nginx/default.conf.template) and list your
office or VPN ranges.

**Your own proxy** (Traefik, a cloud load balancer, and so on): remove the `nginx` service and
publish the API on a private interface, for example `127.0.0.1:8000:8000`. Serve the built
app and `/media/` yourself. Your proxy must also:

- set `X-Forwarded-Proto: https`;
- overwrite `X-Forwarded-For`, or set `DJANGO_NUM_PROXIES` to match its chain;
- buffer request bodies;
- send the same security headers as the bundled template.

## Upgrades

```bash
cd /srv/listlinkedin
git fetch --tags && git checkout <new tag>
docker compose -f compose.prod.yaml build              # while the old version still serves
touch deploy/maintenance/on                            # optional: the maintenance page
bash deploy/backup.sh                                  # always, before migrating
docker compose -f compose.prod.yaml up -d --wait
rm -f deploy/maintenance/on
curl https://go.example.com/healthz
```

`up` runs `migrate` before starting the new `api`, `worker` and `cleanup`. Use the maintenance
page when the release notes say an upgrade migrates a lot of data. Otherwise the old `api`
serves until the new one replaces it, a few seconds later. A failed migration stops there and the stack doesn't come up. Read
`docker compose -f compose.prod.yaml logs migrate`, then fix the problem or roll back.

**Automatically, on the production host** ([ADR-018](v2/adr/ADR-018-pull-based-deployment.md)):
publishing a GitHub Release (a `vX.Y.Z` tag on `main`) runs the steps above within about 5
minutes, through `lli-auto-deploy` and its timer
([infra/terraform/host/](../infra/terraform/README.md#continuous-deployment)). It rolls back as
below when something fails and mails the result to `MODERATION_EMAIL`. Put `[manual-deploy]` in
the release notes of a release that needs more than these steps; it is then skipped and
reported.

**Rolling back:**

1. Check out the previous tag.
2. Restore the backup taken before the upgrade with [deploy/restore.sh](../deploy/restore.sh).
   Migrations aren't run backwards in production, and the restored database matches the old
   code.
3. Start the stack.

Release notes say when an upgrade needs more than this, such as a one-off command.

**Moving a V1 install** (`release/v1`) to V2 goes through `v2.0.x`, the last releases that
still serve V1's edit links: follow the [runbook](v2/06-MIGRATION-PLAN.md#runbook), rehearsed
in [22](v2/22-RELEASE-REHEARSAL.md), and fetch details for V1's links with
`backfill_metadata` in batches of 1,000 (the default; larger batches make the worker
unhealthy). Upgrade to `v2.1.0` or later only once V1's lists have expired, at most 30 days
later: its migration `sharing.0011` stops while a list without an account is still alive.
`docker compose -f compose.prod.yaml run --rm -e RETIRE_LEGACY_LISTS=delete migrate` deletes
those lists instead, with their links and short URLs.

## Maintenance mode

While the file `deploy/maintenance/on` exists, nginx answers every request with a static
503 page ([deploy/maintenance/maintenance.html](../deploy/maintenance/maintenance.html)),
with `Retry-After: 600`, the API included. nginx checks on every request, so there's nothing
to reload:

```bash
touch deploy/maintenance/on       # start
rm deploy/maintenance/on          # end
```

The page doesn't need the API, so it stays up while the `api` container is stopped or being
replaced. nginx looks the API's address up per request, so a recreated `api` is reached
without restarting nginx. The V1 → V2 release uses the page for its whole window
([runbook](v2/06-MIGRATION-PLAN.md#runbook)).

## Worker

The worker is the only process that contacts other sites. It fetches a link's page through
an SSRF-safe fetcher that refuses private, loopback, link-local and metadata addresses, even
after redirects. It stores the title, description and icon, and never overwrites what people
typed.

- **Health:**
  - `docker compose -f compose.prod.yaml ps worker` should show healthy.
  - `docker compose -f compose.prod.yaml exec worker python manage.py check_worker` shows the
    queue.
  - A task that waits or runs longer than 10 minutes makes the worker unhealthy.
- **Recovery:**
  - A worker that dies mid-task is restarted (`restart: unless-stopped`).
  - Its task runs again: `recover_stuck_tasks` runs every 5 minutes.
  - A task that hangs ends its own process after 120 s.
- **Hardening**, on top of the fetcher's own checks
  ([14](v2/14-INFRASTRUCTURE.md#worker-egress)):
  - Block the worker's egress to private ranges at the host:
    `iptables -I DOCKER-USER -s <worker subnet> -d 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,100.64.0.0/10 -j DROP`.
    Find the subnet with `docker network inspect`.
  - Give the worker its own network with only `db`, so it can't reach `api` or `nginx`.

## Media

People upload list and group images and link icons, and the worker stores fetched icons. All
of them are re-encoded on arrival. They live in the `media` volume under content-addressed,
immutable names, and nginx serves them under `/media/`. `cleanup_media` deletes files that
nothing refers to, including old revisions, after 7 days. Back the volume up with the
database.

## Email

The api sends four kinds of email, during the request:

- address confirmation;
- password reset;
- "no account for this address";
- "you already have an account".

Reports go to `MODERATION_EMAIL`. The wording is in
[backend/templates/account/email/](../backend/templates/account/email/).

- Use a relay that signs for your domain (SPF, DKIM), or the mail lands in spam.
- If the relay is down, the requests that send mail fail rather than hang, because
  `EMAIL_TIMEOUT` caps the wait. A report answers 503 and asks the person to try again.
  Sign-up and password reset show a general error. Watch the api's logs for SMTP errors.
- Test it with a password reset to your own address.

## Scheduled jobs

The `cleanup` service runs [backend/docker/crontab](../backend/docker/crontab) with
supercronic. Times are UTC.

| When | Command |
|---|---|
| daily 03:00 | `cleanup_expired`: lists past their expiry date, with their links and short URLs; old rate-limit rows |
| daily 03:20 | `clearsessions` |
| daily 03:30 | `prune_db_task_results --min-age-days 7` |
| daily 03:40 | `purge_deleted_accounts`: accounts deleted more than 30 days ago are erased |
| every 5 minutes | `recover_stuck_tasks` |
| Sundays 04:00 | `cleanup_media` |

To run one now: `docker compose -f compose.prod.yaml exec cleanup python manage.py <command>`.
Its output is in `docker compose -f compose.prod.yaml logs cleanup`.

## Backups

[deploy/backup.sh](../deploy/backup.sh) runs on the host. It writes:

- `db-<time>.dump`: `pg_dump -Fc` of the database, taken while the site runs, and checked to
  be readable;
- `media-<time>.tar`: the `media` volume.

The files are readable only by you. Backups older than `BACKUP_KEEP_DAYS` (default 14) are
deleted. Run it daily, and copy the directory to another machine or object storage too.

```bash
# crontab -e, on the host:
30 2 * * * cd /srv/listlinkedin && bash deploy/backup.sh /var/backups/listlinkedin >> /var/log/listlinkedin-backup.log 2>&1
```

**Restore** with [deploy/restore.sh](../deploy/restore.sh). It stops the app, replaces the
database and the images, migrates, and starts the stack. Everything written since the backup
is lost, so it asks for `--yes`:

```bash
bash deploy/restore.sh --yes /var/backups/listlinkedin/db-….dump /var/backups/listlinkedin/media-….tar
```

**Test a restore monthly**, without touching production: restore the latest backup into a
separate compose project on other ports. Check it and remove it:

```bash
COMPOSE_PROJECT_NAME=listlinkedin-restore-test HTTP_PORT=8080 HTTPS_PORT=8443 \
  bash deploy/restore.sh --yes /var/backups/listlinkedin/db-….dump /var/backups/listlinkedin/media-….tar
curl -sk --resolve go.example.com:8443:127.0.0.1 https://go.example.com:8443/healthz
docker compose -p listlinkedin-restore-test -f compose.prod.yaml exec api python manage.py shell \
  -c "from apps.sharing.models import SharedList; print(SharedList.objects.count())"
docker compose -p listlinkedin-restore-test -f compose.prod.yaml down -v
```

In a rehearsal, a small database restored in about 15 seconds.

## Monitoring

Compose marks a container unhealthy but never restarts it, and nothing alerts.
[deploy/autoheal.sh](../deploy/autoheal.sh) fills that gap. Run it on the host every few
minutes. It:

- restarts every unhealthy container: the api's `/healthz`, the worker's `check_worker`, the
  database's `pg_isready`;
- reports any service that has stopped;
- exits non-zero when it found something;
- pipes its message to `ALERT_COMMAND` when that is set.

```bash
# crontab -e, on the host:
*/2 * * * * cd /srv/listlinkedin && ALERT_COMMAND='mail -s "listlinkedin alert" ops@example.com' bash deploy/autoheal.sh 2>> /var/log/listlinkedin-autoheal.log
```

Any command that reads a message on standard input works, for example a webhook:
`ALERT_COMMAND='curl -s -X POST -H "Content-Type: text/plain" --data-binary @- https://hooks.example.com/…'`.
It's a host script, not a compose service, so nothing new runs next to the app.

Also watch these from outside:

- **Uptime:** an external check on `https://<host>/healthz`, which also covers nginx, TLS
  and DNS.
- **Certificate expiry:** certbot renews, but check its timer runs.
- **Disk:** the database, `media`, backups and logs.
- **Logs:** `docker compose -f compose.prod.yaml logs --since 1h api worker`.
  - Each line is a JSON object with a `request_id`. nginx sends the same id as
    `X-Request-ID`, so a request can be followed from nginx through the api into the worker.
  - Logs never contain passwords, tokens, session ids or email addresses
    ([21](v2/21-SECURITY-REVIEW.md#logging)).
  - Errors are logged with tracebacks. Nothing is sent to an error service.

## Moderation

People report lists and groups with **Report…** in their ⋮ menu. Each report arrives at
`MODERATION_EMAIL` with:

- the code, title, address and owner id;
- the reason and details;
- the command to act on it.

It never includes the reporter's address. Act with these commands. Codes can start with `-`,
so always put `--` before a code:

```bash
alias manage='docker compose -f compose.prod.yaml exec api python manage.py'
manage unpublish_list --reason "phishing" -- <code>        # private: only owner and members
manage delete_list --reason "illegal" --yes -- <code>      # without --yes: shows what it deletes
manage find_links phishing.example                          # every live link to a host
manage unpublish_group --reason "spam" -- <code>
manage delete_group --reason "spam" --yes -- <code>         # its lists stay
manage suspend_account someone@example.com --reason "spam" --unpublish
manage unsuspend_account someone@example.com --reason "appeal accepted"
```

- To stop a phishing domain everywhere, add it to `BLOCKED_DESTINATION_HOSTS` in `.env` and
  run `docker compose -f compose.prod.yaml up -d`. Its existing short URLs answer 410 from
  then on.
- Every command logs the ids and your reason.
- There is no admin site: shell access to the server is the trust boundary.
- What each command does exactly is in [13](v2/13-SECURITY.md#moderation).
