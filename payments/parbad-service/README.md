# ShopSense Parbad Virtual Gateway (Sandbox Only)

This small .NET 9 service integrates Parbad with ShopSense's Python/FastAPI backend. It uses Parbad Virtual Gateway to test the checkout, redirect, callback, verification, and order-status flow.

> **This is not a real payment gateway.** It does not charge money, process Indian UPI/cards, or confirm real INR settlement. Parbad's listed real gateways are primarily Iranian providers. Do not enable the virtual gateway in a production checkout or treat sandbox success as real payment.

## Local Docker setup

1. Copy `backend/.env.example` to `backend/.env`.
2. Optionally create a repository-root `.env` and set `PARBAD_INTERNAL_KEY` to a random value of at least 32 characters. Docker Compose uses a clearly local-only fallback when it is absent; never reuse that fallback outside local development.
3. Run from the repository root:

   ```bash
   docker compose up --build
   ```

4. Open `http://localhost:3000`, sign in, add an in-stock catalog product to your cart, and choose **Continue to Parbad Sandbox**.
5. The browser goes to the Parbad Virtual Gateway at `http://localhost:8081/virtual`. Choose the simulated result and return to ShopSense. Only a verified Parbad callback can mark the order `paid`.

The backend computes the total from current database product prices and stock; it ignores client-submitted prices/names/totals. Service callbacks use `X-ShopSense-Internal-Key`, and the backend validates the order/attempt state before accepting events.

## Environment variables

### ShopSense backend
- `PARBAD_MODE=virtual` enables local sandbox checkout.
- `PARBAD_PUBLIC_BASE_URL=http://localhost:8081` is the browser-accessible .NET service base URL.
- `PARBAD_INTERNAL_KEY` is a random secret shared only by the backend and payment service.
- `PARBAD_ALLOW_VIRTUAL_IN_PRODUCTION` defaults to `false`. Leave it disabled.

### Parbad service
- `PARBAD_MODE=virtual`
- `PARBAD_PUBLIC_BASE_URL=http://localhost:8081`
- `SHOP_API_BASE_URL=http://backend:8000`
- `SHOP_FRONTEND_RETURN_URL=http://localhost:3000/`
- `PARBAD_INTERNAL_KEY` must match the backend value.
- `PARBAD_ALLOW_VIRTUAL_GATEWAY_IN_PRODUCTION` defaults to `false`. Leave it disabled.

## Production payment readiness

Before accepting real money, select a provider compatible with ShopSense's country and currency (the current catalog is INR-priced), obtain merchant credentials, and implement the provider-specific signature checks, webhook verification, and refund flow. Parbad's Virtual Gateway and in-memory storage are development-only. The payment service refuses to start virtual payments in `Production` unless an explicit sandbox-only override is enabled; do not set that override on the live store.
