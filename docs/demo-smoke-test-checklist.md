# ShopSense Demo Smoke-Test Checklist

Use this checklist before a classroom demo, portfolio recording, or public walkthrough. Run it against a local or staging environment first. Do not use real customer data or real payment credentials during a demo.

## 1. Startup checks
- [ ] Backend starts without an import or configuration error.
- [ ] Backend health endpoint responds successfully.
- [ ] Frontend starts and can reach the configured backend URL.
- [ ] Browser developer console has no new application-breaking errors.
- [ ] Backend logs do not print API keys, passwords, JWTs, or payment secrets.

## 2. Core shopping journey
- [ ] Register a dedicated demo account or sign in with a test account.
- [ ] Refresh the page and confirm the expected session behavior.
- [ ] Submit a normal product recommendation request.
- [ ] Submit a budget-constrained request, such as a laptop under ₹60,000.
- [ ] Open a product detail view and verify the displayed product information.
- [ ] Add and remove an item from the cart.
- [ ] Compare two products and confirm both names are represented correctly.
- [ ] Try a non-shopping request and confirm the shopping-scope response is appropriate.

## 3. Live search and AI behavior
- [ ] When SerpApi is configured, ask for current deals and inspect retailer, price, and outbound link.
- [ ] When SerpApi is unavailable, confirm fallback behavior is understandable and does not fabricate a verified price.
- [ ] Check that missing images or optional listing fields do not break the page.
- [ ] Confirm an AI provider error is shown as a recoverable message rather than a blank or stuck chat.
- [ ] Confirm a cancelled request does not continue updating the visible conversation.

## 4. Account and data boundaries
- [ ] Sign out and confirm protected screens or API actions require authentication.
- [ ] Sign in as a second test user and verify the first user's saved data is not visible.
- [ ] Try an invalid form value and confirm validation feedback is shown.
- [ ] Confirm a failed request does not create a misleading success state.

## 5. Payment safety
- [ ] Keep the Parbad virtual gateway in test mode.
- [ ] Do not enable the virtual gateway in production.
- [ ] Do not enter real card or banking details in a demo.
- [ ] Treat an order as paid only after the backend verifies a supported provider's payment result.

## 6. Record the result

| Field | Value |
|---|---|
| Date and environment | |
| Frontend build / commit | |
| Backend commit | |
| Tester | |
| Passed checks | |
| Failed checks and reproduction steps | |
| Follow-up owner | |

A checklist item is not a test result until it has actually been executed. Record **Not run** rather than assuming it passed.
