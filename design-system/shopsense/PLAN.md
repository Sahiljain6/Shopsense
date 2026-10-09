# ShopSense UI Refinement Plan — Generate → Evaluate → Regenerate → Apply

## Product goal
Make ShopSense feel like a deliberate, modern shopping copilot—not an AI template—while preserving its current dark/cyan brand and keeping typing, streaming, scrolling, product comparisons and checkout responsive.

## Candidate directions scored before implementation

Scores are design reviews (1 = weak, 5 = strong), not user-study measurements.

| Direction | Brand fit | Task clarity | Low rendering risk | Accessibility headroom | Decision |
|---|---:|---:|---:|---:|---|
| A. Cinematic neon/glass and layered animation | 5 | 2 | 2 | 3 | Rejected: overuses the current visual vocabulary; expensive effects compete with shopping content |
| B. Plain minimal monochrome | 2 | 4 | 5 | 5 | Rejected: fast and clear, but loses the recognizable ShopSense identity |
| C. Precision Commerce (restrained dark/cyan) | 5 | 5 | 4 | 5 | Selected: brand-preserving, content-led, with motion on demand and stable surfaces |

These scores are an explicit design review, not benchmark results. Actual responsiveness still has to be confirmed with test output and browser profiling.

## Regenerated implementation plan

### Phase 1 — Lock the design rules
- Define a master token/pattern source and chat/product page rules.
- Keep existing fonts and libraries; add no animation or icon package.
- Define a low-noise palette: navy canvas, slate surfaces, cyan primary action, emerald success, amber offers.
- Prefer SVG icons from one small local icon component rather than emoji as structural controls.

### Phase 2 — Remove decorative cost before adding polish
- Replace stacked ambient background layers with one static radial highlight.
- Remove continuous status pulses, large blurred glows, repeated image/card scaling, and high-cost shadow animation.
- Keep one small typing/waiting indicator and brief transition feedback.
- Respect `prefers-reduced-motion` in Framer Motion components and globally.

### Phase 3 — Improve the task surfaces
- Welcome prompts use consistent iconography and brief entrances.
- Product cards emphasize name, price, rating and actions without hiding details.
- Chat surfaces and composer are stable; controls have visible focus and comfortable targets.
- Product modal remains a single scrollable details region between pinned close and cart controls.
- Auth dialog gets correct dialog semantics, focus handling, background-scroll locking, responsive internal scrolling and reduced-motion behavior.
- Cart remains functional while receiving matching surface, control and safe-viewport treatment.

### Phase 4 — Cut work during streaming
- Keep existing SSE/network behavior and all token text.
- Batch message state commits to roughly 30 updates/second instead of re-rendering Markdown and the nested product/chat tree for each incoming chunk.
- Flush the buffered text synchronously on completion and clear pending timers on cleanup.
- Do not add polling, background jobs, animation dependencies or new network work.

### Phase 5 — Evaluate again before delivery
- Review every change against the selected direction. Remove anything decorative that has no task/feedback purpose.
- Verify JSX imports, icon names, dialog semantics, stream flush paths, CSS breakpoints and fallback viewport units.
- Run frontend tests and production build in GitHub Actions; report unrelated CI failures separately.
- Run lint only if the repo has a working ESLint dependency/configuration. The current repository's lint script is not configured correctly.
- Check responsive sizes (375, 768, 1024, 1440 CSS px), short-height, keyboard, reduced-motion and long product data in a browser when available. Never call these browser-verified without actually running them.

## Implementation summary on this branch

Implemented: design docs; stable token/focus rules; calmer static ambience; lighter chat, navbar, product and composer styling; SVG icon component for primary product/chat/cart actions; responsive chat heights; reduced-motion awareness in the root and animated message/welcome/modal/auth components; responsive, focus-managed auth modal; and throttled stream rendering with immediate completion flush.

## Acceptance criteria
- No product/cart/network behavior intentionally changed by visual edits.
- No new package dependencies.
- No continuous decorative animation added to the main chat path.
- Streaming output is complete with no dropped final buffered text.
- CSS and JSX compile; frontend tests/build pass.
- Performance language remains precise: a code change is a hypothesis until measured in the browser; CI build success is not an FPS guarantee.
