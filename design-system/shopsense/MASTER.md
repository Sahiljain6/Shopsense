# ShopSense UI System — Precision Commerce

**Status:** Active working baseline  
**Product:** AI shopping copilot for India — conversational discovery, retailer comparison, offers, specifications and cart.  
**Implementation:** React 18 + Vite + CSS organized by domain + Framer Motion. Keep the existing stack and product behavior.

## Direction and re-evaluation

### Initial direction considered
A cinematic AI interface: neon cyan, multiple glows, glass surfaces, animated grids, card lifts, staggered entrances and persistent status pulses.

### Why it was rejected
The current interface already uses much of that vocabulary. Adding more would increase visual competition and may cause unnecessary painting/compositing work without improving the main shopping tasks. Large blur layers, continuous decoration, scaling and multi-layer shadows should not be the default.

### Selected direction: Precision Commerce
Use a calm deep-navy canvas, well-separated slate surfaces, a restrained cyan action color, clear typography, compact informational labels and purposeful micro-interactions. Retain ShopSense's recognizable dark/cyan identity, but make product content and primary actions dominate. This hybrid follows the skill's AI/chat guidance (minimal chrome and fast feedback) and e-commerce guidance (clear product hierarchy and useful cards).

## Design tokens

Use existing --ss-* tokens in frontend/src/styles/variables.css before adding raw values.

- Canvas: near-black navy (#07090E).
- Main surface: opaque blue-slate (#0E131E / #111724); layered surfaces only when separation helps.
- Primary action/focus: cyan (#06B6D4 to #22D3EE); use sparingly for primary actions, focus rings and selected/active states.
- Positive deal/success: emerald (#10B981 / #34D399).
- Offer/attention: amber (#F59E0B); do not turn every badge into an alarm.
- Text: near-white primary, light slate secondary. Measure contrast rather than assuming muted text is readable.
- Typography: preserve current Outfit display + Plus Jakarta Sans body + JetBrains Mono for prices/technical values. Do not add font downloads or extra font weights without a concrete need.
- Shape: use an 8px spacing rhythm and consistent 8/12/16/22px corner scale. Use borders for surface separation; keep shadows shallow and rare.

## Layout principles

1. First priority is the user's shopping task: chat, comparison, product information and cart.
2. Establish hierarchy using typography, spacing and contrast instead of more glow.
3. Keep product cards content-led, preserve pricing/specification details, and provide clear primary versus secondary actions.
4. Use one deliberate scroll owner per surface. Fixed actions must not cover scrollable content.
5. Use mobile-first layouts; test 375, 768, 1024 and 1440 CSS px, short-height and landscape windows. Avoid unintended horizontal page scroll.
6. Long labels, product names, URLs and specification values must wrap safely; don't solve layout problems by hiding meaningful content.
7. Keep surfaces mostly opaque where text overlays would otherwise reduce legibility. Reserve blur for a small number of intentional overlays.

## Motion and responsiveness budget

- Motion is feedback, not decoration. Prefer opacity and transform over animating layout, width/height, filters or large shadows.
- Interactions generally use 140–200ms; a new message may enter with a subtle 160–200ms opacity/translate effect. Avoid long stagger chains.
- Do not animate cards on every streaming token or continuously animate decorative backgrounds.
- Keep a single small typing indicator during waiting. Persistent “live” status can be static; don't pulse several unrelated components.
- Hover effects are optional enhancements; the same action must work by touch and keyboard.
- Framer Motion components must respect prefers-reduced-motion, not just CSS transitions.
- Respect prefers-reduced-motion: reduce globally. Do not block scrolling or input during animation.
- Avoid large backdrop-filter layers, animated gradients, huge glowing shadows and parallax on the main chat path.
- Keep chat auto-scroll conditional on the user being near the bottom. Keep token updates batched; never add state writes per token without batching.

## Accessibility baseline

- Use semantic controls, meaningful accessible names, sensible focus order and visible :focus-visible states.
- Target comfortable pointer/touch controls (44×44px for primary icon controls where layout permits).
- Maintain readable contrast for normal body text; color must not be the only status indicator.
- Respect browser zoom and text scaling; don't lock the page to a fixed pixel canvas.
- Keep modals dismissible with Escape and backdrop, trap/restore focus appropriately, and restore background scrolling.
- Respect safe-area insets for fixed footers on small screens.

## Component rules

- **Navbar:** compact brand anchor, meaningful account/cart controls, quiet service-status indicator; no excessive glass blur or glow.
- **Welcome prompts:** useful examples with consistent card layout; small entrance only when motion is enabled; no long animated cascade.
- **Chat messages:** readable and stable while streaming; entrance animation applies when inserted only, not to each content update.
- **Product cards:** image dimensions reserved, title/price easy to scan, badges limited, actions obvious; hover changes must not shift surrounding layout.
- **Product detail modal:** shell doesn't scroll; one content scroll region; fixed close control and persistent CTA footer.
- **Composer:** keyboard-focused, stable layout, clear disabled/loading feedback and sufficiently large hit targets.
- **Feedback:** prefer brief status text/checkmarks and inline errors over elaborate moving toasts.

## Performance guardrails

- No added animation libraries, background videos, WebGL scenes, polling or decorative perpetual effects.
- Do not add dependencies for visual polish when CSS/Framer Motion already covers the need.
- Prefer transform and opacity; reduce heavy blur, repeated filter/shadow animation and unbounded motion.
- Preserve lazy loading and explicit image dimensions; avoid introducing layout shift.
- Review React rendering paths before adding animated effects. Keep visual-only changes separate from network and cart logic.
- Treat performance claims as unverified until supported by build/test output or browser profiling.

## Pre-delivery checklist

- [ ] Existing product data, cart state, retailer links, chat streaming and authentication flows still work.
- [ ] Reduced-motion users get no unnecessary entrance, hover or looping motion.
- [ ] Keyboard focus is visible and not obscured; Escape/backdrop dismiss overlays.
- [ ] 375px mobile, 768px tablet, 1024px laptop and 1440px desktop layouts do not clip content.
- [ ] Short viewport and landscape cases keep composer and primary actions usable.
- [ ] Long product descriptions, offers, URLs and specifications wrap without horizontal page overflow.
- [ ] Only intentional scroll regions exist; sticky/fixed controls don't cover the last rows.
- [ ] Frontend unit tests and production build pass; lint status is accurately reported.
- [ ] Inspect a real browser before claiming pixel-level visual verification.

## Change policy

Prefer small coherent changes that preserve ShopSense's identity and behavior. Do not do a full redesign for a local defect. Update page-specific rules only when the master rules need an exception. Never overwrite existing team decisions or claim browser validation without performing it.
