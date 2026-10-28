# syntax=docker/dockerfile:1
# Browsers come preinstalled in the official image. Its tag MUST match the @playwright/test
# version in package.json, or Playwright refuses to start ("browser executable not found").
FROM mcr.microsoft.com/playwright:v1.64.1-noble
ENV NPM_CONFIG_UPDATE_NOTIFIER=false CI=true
WORKDIR /e2e
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY . .
ENTRYPOINT ["npx", "playwright", "test"]
