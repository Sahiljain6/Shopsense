# ShopSense Production Release Checklist

This checklist is a manual release gate. Complete it for the exact commit and environment being released; a successful local run does not prove that the deployed application is healthy.

## Before deployment
- [ ] Review the diff and confirm only intended files changed.
- [ ] Run the backend test suite from the backend environment.
- [ ] Run frontend lint, build, and available tests.
- [ ] Check dependency and container build output for new errors.
- [ ] Verify database changes are backward-compatible with the deployed application.
- [ ] Confirm the deployment has a tested backup or recovery path for persistent data.
- [ ] Verify required environment variables are configured in the hosting provider.
- [ ] Confirm secrets are not present in commits, frontend variables, screenshots, or logs.
- [ ] Confirm CORS allows only intended frontend origins.
- [ ] Confirm debug mode and development-only payment settings are disabled in production.

## Deploy
1. Record the current production commit and deployment identifier.
2. Deploy the reviewed commit to the intended environment.
3. Wait for the platform's build and health checks to finish.
4. Inspect startup logs for configuration, database, and provider errors.
5. Verify the frontend can reach the deployed API.
6. Run the smoke tests in demo-smoke-test-checklist.md against the deployment.

## After deployment
- [ ] Sign in with a dedicated test account.
- [ ] Complete one normal shopping chat request.
- [ ] Check product search and optional live-search fallback behavior.
- [ ] Verify cart and saved-data operations with test data.
- [ ] Check browser console and backend logs for new errors.
- [ ] Confirm request latency and error rate are within the expected baseline.
- [ ] Record the commit, deployment time, tester, and observed result.

## Rollback decision
Rollback or disable the affected feature if authentication, data isolation, checkout integrity, or core shopping flows regress. Prefer reverting the specific application change over applying an unreviewed hotfix directly to production.

Before rollback, consider whether the release included a database migration. Reverting application code alone may not reverse a schema change. Use the project's documented database backup and migration procedure, and do not delete or overwrite production data as an improvised recovery step.

## Release record

| Field | Value |
|---|---|
| Release commit | |
| Environment | |
| Deployment ID | |
| Database migration | |
| Smoke-test result | |
| Known issues | |
| Rollback commit / plan | |

Mark checks as **Not run** when they have not been executed. Do not report a deployment as verified based only on a successful GitHub commit.
