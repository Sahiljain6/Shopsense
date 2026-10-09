# Chat and product results — Page override

This page follows ../MASTER.md and narrows the rules for ShopSense's chat-first shopping experience.

## Content hierarchy
1. Message composer and conversation state.
2. Assistant answer and useful comparison context.
3. Product cards, with title, current price, rating/value context and direct actions.
4. Expanded details in the product modal, with full specifications and retailer links preserved.

## Motion
- New message: fade + at most a small vertical offset once on insertion.
- Prompt cards: brief opacity/transform entrance, no delayed waterfall when reduced motion is requested.
- Streaming: batch text updates; don't replay the message entrance or animate dimensions as tokens arrive.
- Waiting: one subtle typing indicator. No animated ambient background.
- Cards: very small hover lift on pointer devices only; don't scale the image and card simultaneously.

## Layout
- Keep one primary vertical scroll owner for the chat transcript and one for an open modal; don't nest scroll frames inside the modal.
- Product grid uses responsive minmax columns; cards and price/spec text are allowed to wrap.
- The modal owns fixed close and footer controls, with specifications scrolling between them.
- At mobile widths, switch to one column before buttons/prices become cramped. Honor dynamic viewport height and safe areas.

## Acceptance checks
- Add-to-cart behavior and success feedback unchanged.
- Chat auto-scroll only follows the user when they were already near the bottom.
- No mandatory hover-only cues or lost keyboard focus.
- Reduced-motion mode disables Framer Motion entrance transforms as well as CSS motion.
- No new perpetual decorative animation, package dependency or network work is introduced.
