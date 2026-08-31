# ShopSense AI Engineering & Contribution Guidelines

These guidelines are permanently active across all pair programming, agentic sessions, and automated tasks on this repository.

---

## 1. Git Contribution & Batching Strategy

- **Granular, High-Value Commits**:
  - Always break down tasks and implementations into granular, logical batches.
  - Deliver each distinct feature, integration, service layer, or refactor as an independent, well-tested commit.
  - Maximize valuable GitHub contribution graph activity without creating trivial or noise commits. Every commit must provide tangible technical or product value.

- **Strict Git Identity & Attribution**:
  - All git commits MUST be authored by:
    - **Name**: `Sahil Jain`
    - **Email**: `sahil.jain24@sakec.ac.in`
  - Ensure local repo git config is always maintained:
    ```bash
    git config user.name "Sahil Jain"
    git config user.email "sahil.jain24@sakec.ac.in"
    ```

- **Commit & Push Discipline**:
  - Follow Conventional Commits format:
    - `feat(api): ...`
    - `feat(agent): ...`
    - `fix(security): ...`
    - `test(services): ...`
  - Push changes directly to `origin/main` after verifying each batch:
    ```bash
    git add -A
    git commit -m "<type>(<scope>): <clear descriptive message>"
    git push origin main
    ```

---

## 2. Testing & Quality Invariants

- **Automated Verification Before Every Commit**:
  - Run the full pytest suite (`python -m pytest -v`) to guarantee zero regressions before pushing any commit.
  - Maintain 100% pass rate across all test suites (`test_api.py`, `test_agents.py`, `test_logistics.py`, `test_finance.py`, `test_weather_context.py`, `test_currency_import.py`, `test_deal_timing.py`, `test_photo_deal_agents.py`, etc.).
- **Security Guardrails**:
  - Never commit raw secrets or API keys.
  - Enforce SSRF validation (`safe_fetch_url`) for external HTTP calls.
  - Enforce prompt injection guardrails on all user chat inputs.
- **Architectural Grounding**:
  - Keep AI responses strictly grounded in real product attributes, catalog fields, and verified public APIs.
  - Maintain multi-agent collaboration standards (Visual Inspector ↔ Deal Specialist).
