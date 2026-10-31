# AI provider configuration

ShopSense sends customer-chat model requests from the FastAPI backend. Provider
credentials must stay on the backend and must never be added to frontend
variables such as `VITE_GEMINI_API_KEY`.

## Configure Gemini

Set these variables in the backend environment (for example, Render):

```dotenv
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

The model setting is a preference for the configured Gemini route. The backend
may use its model-discovery and fallback logic if the preferred model is not
available, depending on the current implementation. A configured model name
does not grant API access or additional quota.

## Verify after deployment

1. Confirm the backend service has both variables configured. Do not paste
   secret values into issues, logs, screenshots, or commits.
2. Trigger a normal shopping question in the deployed application.
3. Check backend logs for the provider and model recorded for that request.
4. If Google returns an authorization, model-not-found, quota, or rate-limit
   error, verify the key's project access and Google AI Studio usage limits.
5. Restart/redeploy the backend after changing environment variables.

## Important limitations

- A model name in the UI is not proof of which model handled a request; use
  backend request logs to verify.
- A fixed model preference cannot guarantee successful responses when that
  model is rate-limited or unavailable.
- Keep the existing catalog and search flows available when the AI provider
  cannot return a response.
