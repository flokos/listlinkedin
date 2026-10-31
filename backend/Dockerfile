# syntax=docker/dockerfile:1
ARG TARGETARCH

# supercronic: cron for containers, runs the `cleanup` schedule (docker/crontab).
# Pinned per architecture and verified against the release's SHA-256 digests.
FROM scratch AS supercronic-amd64
ADD --chmod=755 \
    --checksum=sha256:a53ae236602c7338aba3fbaff40bda6300eae3b9fedb8261eb06cfe3724430c1 \
    https://github.com/aptible/supercronic/releases/download/v0.2.49/supercronic-linux-amd64 \
    /supercronic

FROM scratch AS supercronic-arm64
ADD --chmod=755 \
    --checksum=sha256:02aa0cb229ba09050cba6638059dadb9eedc2276632ea43d6a57a2f8c1629dd5 \
    https://github.com/aptible/supercronic/releases/download/v0.2.49/supercronic-linux-arm64 \
    /supercronic

FROM supercronic-${TARGETARCH} AS supercronic


FROM python:3.14-slim AS base
COPY --from=supercronic /supercronic /usr/local/bin/supercronic

# Dependencies are installed into the image's system interpreter: no virtualenv.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./


FROM base AS dev
RUN --mount=from=ghcr.io/astral-sh/uv:0.9.5,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


FROM base AS prod
RUN --mount=from=ghcr.io/astral-sh/uv:0.9.5,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev
RUN useradd --system --uid 10001 --create-home app \
    # The media volume's mount point. A new named volume copies this ownership, so the
    # non-root app user can write uploads to it.
    && mkdir -p /srv/media && chown app:app /srv/media
COPY . .
USER app
ENV DJANGO_SETTINGS_MODULE=config.settings.production
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "30", \
     "--access-logfile", "-"]
