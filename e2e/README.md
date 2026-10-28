# End-to-end tests

Playwright tests that drive real browsers against the **production stack**: nginx serving
the built Vue app over HTTPS, Gunicorn and PostgreSQL. They run in Chromium, Firefox,
WebKit (Safari's engine) and emulated iPhone and Pixel phones. Everything runs in Docker;
you need nothing but Docker on the host.

```bash
bash e2e/run.sh                          # all projects
bash e2e/run.sh --project=chromium       # one browser
bash e2e/run.sh --project=webkit -g share  # one browser, tests matching "share"
```

`run.sh` starts an isolated compose project (`listlinkedin-e2e`) with a throwaway
certificate and random host ports, so it never clashes with a stack you already run. It
runs the tests from a container on that compose network and removes everything on exit.
It exits non-zero if any test fails.

## Results and debugging

- The HTML report is written to `e2e/report/index.html`. Failed tests include a
  screenshot and a **trace**.
- To step through a trace (DOM, network and console at every action):
  `docker run --rm -it -p 9323:9323 -v "$PWD/e2e":/e2e -w /e2e listlinkedin-e2e show-report report --host 0.0.0.0`,
  then open http://localhost:9323.
- In CI, the report is uploaded as the `e2e-report` artifact when the job fails.

## Writing tests

- Import `test` and `expect` from `./fixtures`, not from `@playwright/test`. The fixture
  fails any test that logs an unexpected console error.
- Locate elements the way users find them: by role and accessible name
  (`getByRole('button', { name: 'Add link' })`), never by CSS classes. If something can't
  be found that way, that's usually an accessibility bug in the app.
- Set data up through the API (`api.createList`, `api.addLink`) and use the UI only for what
  the test is about. `openAsOwner(page, list)` unlocks a list through its edit link.
- States the real stack can't easily produce (429, 5xx, offline, a missing chunk after a
  deploy) are covered in `states.spec.ts` with `page.route` mocks. Those run in Chromium
  only.
- All browsers share one client IP, so `run.sh` raises the API's rate limits for this
  throwaway stack (`THROTTLE_LIST_CREATE`, `THROTTLE_LIST_MANAGE`).

## Versions

`Dockerfile` uses `mcr.microsoft.com/playwright:vX.Y.Z-noble`, which has the browsers
preinstalled. Its tag must equal the `@playwright/test` version in `package.json`. Update
both together, and regenerate the lockfile in a container:
`docker run --rm -v "$PWD/e2e":/app -w /app node:24-alpine npm install --package-lock-only`.
