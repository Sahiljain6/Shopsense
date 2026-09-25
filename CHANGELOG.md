# Changelog

All notable changes to ShopSense are documented in this file.

## [1.3.0] - 2026-09-25

### Added
- **API Gateway Authentication Middleware**: High-performance edge middleware with sub-2ms stateless RS256/HS256 JWT signature verification, anti-spoofing header stripping, and verified identity injection (`X-User-Tier`, `X-User-Id`).
- **Hierarchical Role & Scope Permissions**: Four-tier role hierarchy (`admin` > `enterprise` > `pro` > `free`) with granular OAuth2-style permission scopes and declarative FastAPI dependencies (`require_scope`, `require_feature_flag`, `require_tier`).
- **Refresh Token Rotation (RTR) & Reuse Detection**: Single-use refresh token families with automatic compromise detection—replaying an old token revokes the entire family and all active sessions.
- **Instant Session Invalidation & Token Versioning**: Mid-session tier downgrades or subscription updates increment user token version, instantly rejecting obsolete JWTs across all endpoints with zero database queries.
- **Multi-Tier Token Quota Engine**: Pre-request token reservation (`check_quota`) and post-inference token settlement (`record_usage`), returning RFC 7807 429 Too Many Requests when limits are exhausted.
- **Row-Level Tenant Isolation**: `ScopedQueryFilter` enforcing row-level database ownership on user queries to prevent Insecure Direct Object Reference (IDOR) vulnerabilities.
- **Security Audit Logger**: Structured audit dispatcher capturing access denials, quota overages, rate limits, and administrative tier modifications.
- **User Quota & Management Endpoints**:
  - `GET /user/quota`: Live dashboard of monthly token usage, limits, and rate limits.
  - `GET /user/profile` & `PATCH /user/profile`: Authenticated user profile retrieval and name updates.
  - `GET /admin/analytics`: Platform analytics enriched with user tier distributions.
  - `PATCH /admin/users/{user_id}/tier`: Admin tier updates with immediate session revocation.
  - `PATCH /admin/users/{user_id}/feature-flags`: Admin-driven feature flag assignment for gradual rollouts.
  - `GET /admin/audit-logs`: Privileged audit log stream for platform security reviews.
- **Comprehensive Security Test Suite**: Added `test_gateway_auth_and_scoping.py` with 11 automated test cases covering free tier restriction, quota exhaustion, mid-session tier downgrades, IDOR isolation, and RTR replay protection.

## [1.2.2] - 2026-09-02

### Changed & Refactored
- **Ultra-Translucent Chatbot & Dock**: Drastically increased transparency across `.chatbot-widget-container` (`rgba(10, 14, 22, 0.18)`), composer dock (`rgba(18, 22, 34, 0.38)`), and navigation bar (`rgba(10, 14, 22, 0.35)`).
- **Custom Invisible & Slim Scrollbar**: Replaced default Windows white scrollbar track on the chat stream with a custom thin, translucent thumb (`rgba(255, 255, 255, 0.16)`).
- **Removed Header Pills**: Removed `22 Stacks`, `Deal Radar`, and `Live EMI` pill badges from the header navigation for an unencumbered layout.
- **Ambient Mode Permanent by Default**: Made cinematic video background permanently active by default, removing the manual toggle button from the navbar.

## [1.2.1] - 2026-09-02

### Changed & Refactored
- **Transparent Chatbot Stage**: Replaced solid white chatbot box with a transparent, dark frosted-glass container (`backdrop-filter: blur(28px)`) seamlessly integrated into the Fastshot ambient background.
- **Removed Legacy Window Bar & Action Chips**: Removed the bright blue OS window title bar and the quick action chips (`Today's Deals`, `Compare Specs`, `EMI Calc`, `Pincode Check`) from the frontend UI for a clean, minimalist design.
- **Glassmorphic Message Bubbles & Cards**: Restyled assistant messages, user bubbles, product cards, and welcome chips in dark frosted glass with high-contrast text and crisp typography.
- **Model Training Integration**: Integrated Today's Deals, Spec Comparisons, EMI Amortization, and Pincode Logistics directly into the backend AI system prompt rather than relying on frontend chips.

## [1.2.0] - 2026-09-02

### Added
- **Single-Page Home Architecture**: Consolidated multi-page auth barrier into a single, instant-loading home page featuring the Fastshot composer and chat interface.
- **Glassmorphic AuthModal Overlay**: Lightweight popup authentication modal with smooth Framer Motion entrance, dark backdrop blur, and ESC/outside-click dismissal.
- **Segmented Auth Mode Switcher**: Instant one-click toggle between "Sign In" and "Create Account" within the modal without page reload.
- **Interactive Navbar Auth CTAs**: Added "Sign In" text button and Fastshot-styled "Sign Up" gradient pill CTA in the header for guest visitors.
- **Interactive Guest Composer Triggers**: Unauthenticated clicks on composer inputs or quick action prompts gracefully invoke the sign-in modal.
- **Auth Unit Test Suite**: Added `auth.test.js` validating token storage lifecycle and friendly authentication error mappings.

### Refactored
- **Performance Optimization**: Removed heavy full-page SVG desk lamp and firefly rendering loop from initial visitor load, reducing bundle bloat and eliminating perceived page lag.
- **Domain CSS Expansion**: Introduced `auth-modal.css` maintaining consistent glassmorphism design tokens.


### Added
- **Fastshot Glassmorphic Interface**: Complete hero redesign with cinematic ambient background video toggle, radial lighting gradients, and floating composer dock.
- **AI Persona Switcher**: Dynamic runtime selection across `Sonnet 4.5` (Deep Reasoning & Comparisons), `Gemini Flash` (Live Web Prices), and `Deal Specialist` (Visual Logistics & Inspection).
- **Quick Actions Toolbar**: One-tap action chips for Today's Deals, Compare Specs, EMI Breakdown, and Pincode Logistics.
- **Welcome Prompt Cards**: Initial state suggestions for earbuds under ₹3,000, iPhone vs OnePlus comparison, mechanical keyboards, and financing calculations.
- **Financing & Amortization Engine**: Month-by-month principal and interest breakdown with No-Cost EMI eligibility and Razorpay IFSC validation.
- **Logistics Delivery SLA Engine**: Indian postal PIN code resolution with metro express vs regional delivery turnaround estimates.
- **Continuous Integration Pipeline**: GitHub Actions workflow running automated frontend builds, unit tests, and backend Pytest test suites.

### Refactored
- **Modular Component Hierarchy**:
  - `HeaderBrandMark`: Reusable SVG brand mark.
  - `FeaturePillBadges`: Navigation highlight badges.
  - `UserProfileMenu`: Authenticated session controls.
  - `ComposerInput`: Isolated dock input bar.
  - `ModelDropdown`: Floating accessible engine picker.
  - `AttachmentPreviewBar`: File upload management with dismiss actions.
  - `TypingIndicator`: Animated pulse dots with cold-start server notice.
  - `CartDrawer` & `useCart`: Centralized reactive shopping cart state.
  - `ProductDetailModal`: Specification comparison and benchmark pricing dialog.
- **Domain CSS Modularization (`frontend/src/styles/`)**:
  - Extracted monolithic `index.css` into 10 clean domain stylesheets: `variables.css`, `ambient.css`, `navbar.css`, `composer.css`, `products.css`, `cart.css`, `auth.css`, `chat.css`, `markdown.css`, and `responsive.css`.

### Tested
- **Frontend Test Suite**: 29 unit tests covering currency formatting (`formatINR`), star ratings, text truncation, buy link generation, schema constants, and API error mappings.
- **Backend Test Suite**: 80+ Pytest unit and integration tests passing with 100% test success rate.
