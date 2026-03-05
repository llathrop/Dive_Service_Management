# UAT (User Acceptance Testing) Plan

## Overview

UAT scripts validate the application from an end-user perspective using browser
automation via **Playwright**.  They complement unit/blueprint tests by
exercising the full stack: Docker containers, Flask app, rendered HTML, HTMX
interactions, and database persistence.

UAT tests live in `tests/uat/` and are marked with `@pytest.mark.uat`.  They
run against a live application container (not SQLite in-memory).

---

## Infrastructure

| Component | Purpose |
|-----------|---------|
| `Dockerfile.uat` | Extends test image with Playwright + Chromium |
| `docker-compose.uat.yml` | Orchestrates: app (web), db (MariaDB), Playwright runner |
| `tests/uat/conftest.py` | Fixtures: browser, page, live server URL, admin login |
| `requirements-uat.txt` | pytest-playwright, playwright |

---

## UAT Timing Schedule

UATs run at **phase gate boundaries** — after all unit/blueprint tests pass for
that phase and before marking the phase complete.

| Phase | Gate | UAT Scope | Script File(s) |
|-------|------|-----------|----------------|
| 1 | Foundation complete | Login, logout, dashboard access, health endpoint | `test_uat_auth.py` |
| 2 | Core Entities complete | Customer CRUD, item CRUD, inventory CRUD, price list, search | `test_uat_customers.py`, `test_uat_items.py`, `test_uat_inventory.py`, `test_uat_price_list.py`, `test_uat_search.py` |
| 3 | Service Workflow complete | Service order workflow, parts used, labor, notes | `test_uat_orders.py` |
| 4 | Billing complete | Invoice generation, payments, billing search | `test_uat_invoices.py` |
| 5 | Reports/Tools complete | Report pages render, tool calculators work | `test_uat_reports.py`, `test_uat_tools.py` |
| 6 | Production Ready | **Full end-to-end suite** — all scripts above + E2E workflow | `test_uat_e2e.py` |

### When to Run

- **During development**: Run relevant phase UATs after completing each phase
- **Before phase sign-off**: Full regression of all UATs for completed phases
- **Pre-release**: Full E2E suite (`test_uat_e2e.py`)

### Commands

```bash
# Run all UATs
docker compose -f docker-compose.uat.yml run --rm uat

# Run specific phase UATs
docker compose -f docker-compose.uat.yml run --rm uat pytest tests/uat/test_uat_auth.py -v

# Run full E2E
docker compose -f docker-compose.uat.yml run --rm uat pytest tests/uat/test_uat_e2e.py -v

# Run with headed browser (for debugging, requires X11 forwarding)
docker compose -f docker-compose.uat.yml run --rm uat pytest tests/uat/ -v --headed
```

---

## Test Structure

Each UAT script follows this pattern:

1. **Setup**: Navigate to relevant page, ensure prerequisite data exists
2. **Action**: Perform user actions (click, fill form, submit)
3. **Verify**: Check page content, URL, flash messages, data persistence
4. **Cleanup**: Soft-delete or revert test data where possible

### Naming Convention

- Files: `test_uat_<feature>.py`
- Tests: `test_<action>_<entity>` (e.g., `test_create_customer`, `test_edit_inventory_item`)

### Fixtures

- `live_server_url` — Base URL of the running Flask app container
- `page` — Playwright Page object (fresh per test)
- `admin_page` — Page pre-logged-in as admin
- `tech_page` — Page pre-logged-in as technician
- `viewer_page` — Page pre-logged-in as viewer

---

## End-to-End UAT Script (`test_uat_e2e.py`)

The final E2E script exercises a complete business workflow:

1. **Container Setup**: Docker compose brings up web + db + redis
2. **Health Check**: Verify `/health` returns 200
3. **Admin Login**: Log in as admin user
4. **Customer Creation**: Create a new customer
5. **Service Item Creation**: Create a drysuit service item for that customer
6. **Inventory Check**: Verify inventory items exist, check stock levels
7. **Service Order** (Phase 3+): Create order, add items, log parts/labor
8. **Invoice Generation** (Phase 4+): Generate invoice from order
9. **Report Verification** (Phase 5+): Check reports render with data
10. **Logout**: Verify logout works

Steps 7-10 are added progressively as those phases complete.

---

## Updating UAT Scripts

As development proceeds, UAT scripts must be updated to match actual output:

1. After implementing a new feature, run the relevant UAT
2. If selectors or page structure changed, update the test
3. If new fields were added, add assertions for them
4. Keep `UAT_PLAN.md` current with actual file names and test counts
5. The E2E script (`test_uat_e2e.py`) grows with each phase

---

## Current Status

| Script | Phase | Tests | Status |
|--------|-------|-------|--------|
| `test_uat_auth.py` | 1 | 6 | Ready |
| `test_uat_customers.py` | 2 | 7 | Ready |
| `test_uat_items.py` | 2 | 6 | Ready |
| `test_uat_inventory.py` | 2 | 6 | Ready |
| `test_uat_price_list.py` | 2 | 4 | Ready |
| `test_uat_search.py` | 2 | 3 | Ready |
| `test_uat_e2e.py` | 1-2 | 1 | Ready (Phase 1-2 steps) |
| `test_uat_orders.py` | 3 | - | Placeholder |
| `test_uat_invoices.py` | 4 | - | Placeholder |
| `test_uat_reports.py` | 5 | - | Placeholder |
| `test_uat_tools.py` | 5 | - | Placeholder |
