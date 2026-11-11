# syntax=docker/dockerfile:1

FROM node:26-alpine AS deps
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund


# Lint, tests and watch builds. Dependencies sit in /node_modules, outside /app, so the
# sources can be bind-mounted over /app (compose.yaml, profile `extension`) and Node still
# finds them by walking up.
FROM node:26-alpine AS dev
COPY --from=deps /app/node_modules /node_modules
ENV PATH=/node_modules/.bin:$PATH \
    NPM_CONFIG_UPDATE_NOTIFIER=false
WORKDIR /app
COPY . .
CMD ["node", "scripts/build.ts", "--watch"]


# The extension for Chrome and for Firefox, talking to the site at LL_BASE_URL.
FROM deps AS build
ARG LL_BASE_URL=https://listlinkedin.versioncontrol.xyz
ARG LL_GECKO_ID=extension@listlinkedin.versioncontrol.xyz
# 1 only for the build the end-to-end tests load (scripts/manifest.ts).
ARG LL_GRANT_OPTIONAL=
ENV LL_BASE_URL=$LL_BASE_URL LL_GECKO_ID=$LL_GECKO_ID LL_GRANT_OPTIONAL=$LL_GRANT_OPTIONAL
COPY . .
RUN npm run build


# Only the build's output, for `docker build --target export --output extension/dist extension`:
# dist/chrome and dist/firefox, each a folder a browser can load.
FROM scratch AS export
COPY --from=build /app/dist /
