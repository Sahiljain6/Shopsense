# Changelog

All notable changes to ShopSense are documented in this file.

## [1.1.0] - 2026-09-01

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
