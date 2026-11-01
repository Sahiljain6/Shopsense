# ShopSense AI Provider Troubleshooting

This guide helps distinguish application configuration issues from upstream model-provider failures. Provider credentials must remain in backend environment variables (for example, Render service settings), never in Vite-prefixed frontend variables or committed files.

## Configuration checks
1. Confirm the backend has the intended provider API key configured.
2. Confirm the configured model identifier is supported by that provider and available to the account.
3. Check for accidental whitespace or quote characters copied into the secret value.
4. Confirm the deployed service was restarted or redeployed after an environment change.
5. Check backend logs for provider name, HTTP status, and request ID. Do not log API keys, authorization headers, full user prompts, or other private data.
6. Verify the application is using the expected backend deployment and not an older API URL.

The sample backend/.env.example file is documentation for local setup. Editing it does not change environment variables in an already deployed Render service.

## Common failure patterns

| Symptom | Possible cause | Safe next check |
|---|---|---|
| Authentication or 401 error | Missing, invalid, or revoked key | Replace the backend secret using the provider dashboard |
| 403 or permission error | Model or account access is restricted | Verify account access and model availability |
| 404 model error | Model identifier is unavailable or misspelled | Check the provider's current model catalogue |
| 429 response | Rate limit, quota, or billing limit | Inspect provider usage and retry-after guidance |
| 5xx or timeout | Temporary provider or network failure | Check provider status and application timeout logs |
| Empty or malformed response | Unexpected upstream response or parsing issue | Capture a redacted request ID and inspect parser handling |

## Fallback and user experience
- A fallback provider should be attempted only when the application's configured fallback policy allows it.
- Do not assume every provider failure is retryable. Authentication and permission errors usually require configuration changes.
- Respect Retry-After when supplied and avoid unbounded retry loops.
- Keep the user informed when a response is delayed or unavailable.
- Never present a provider error as a successful recommendation.
- Do not silently change the configured primary model just because a request failed.

## Safe diagnostic information
When reporting a failure, collect:
- UTC timestamp and request ID
- Backend deployment/commit identifier
- Provider and configured model identifier (not the credential)
- HTTP status and sanitized error category
- Whether the request used fallback
- Whether the failure is reproducible

Do not share API keys, bearer tokens, passwords, complete authorization headers, or private customer conversations in GitHub issues.

## Verify after a fix
1. Re-deploy the backend with the corrected server-side configuration.
2. Send a simple shopping query using a dedicated test account.
3. Confirm the response is non-empty and the UI completes its loading state.
4. Temporarily test a controlled provider-unavailable scenario in local or staging.
5. Confirm errors are surfaced safely and fallback behavior matches the configured policy.

Provider model names, quotas, and availability change over time. Verify them in the provider's official dashboard or documentation before changing production configuration.
