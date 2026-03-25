# Static Project Re-Review (2026-03-10, Refreshed)

## Scope and Constraints
- This report overwrites the prior static review report.
- Per request, no project test suites were run and no code was changed.
- Required docs were re-read first, in order: `README.plan`, `PROJECT_BLUEPRINT.md`, `MEMORY.md`, `PROGRESS.md`.
- `GEMINI-PROJECT_REVIEW.md` was reviewed and only still-valid points were retained.
- Because another agent is actively changing files, this pass re-reviewed changed files before finalizing.

## Refresh Status (What Changed Since Last Pass)
- Newly changed project files re-reviewed: `PROJECT_BLUEPRINT.md`, `Dockerfile`, `Dockerfile.uat`, `docker-entrypoint.sh`.
- Runtime probes re-run on local environment:
  - `http://localhost:8080/health` returns `{"status":"ok"}`.
  - Decimal inventory form submission still rejected (`"Not a valid integer value."`).
  - Part usage still allows negative stock (`inventory_after=-4.00`).
  - `dsm-worker` and `dsm-beat` are still `unhealthy` while running.

## Executive Assessment
The project has progressed, but it still does not meet a reliable "Phase 6 complete / production-ready" quality bar. The most urgent issues are inventory integrity (decimal migration gap + negative stock), deployment reliability patterns (healthcheck and startup behavior), and documentation/testing drift that obscures true readiness.

## Priority Summary
| ID | Priority | Area | Issue | Suggested Fix Window |
|---|---|---|---|---|
| P0-1 | Critical | Data Integrity | Decimal inventory migration is incomplete across forms/routes/tests | Immediate |
| P0-2 | Critical | Data Integrity / Crash | Order part usage can drive inventory negative | Immediate |
| P1-1 | High | Deployment Reliability | Worker/beat report unhealthy due image-level web healthcheck reuse | Immediate |
| P1-2 | High | Upgrade Safety | Startup migration/seed failures are logged but app still starts | Immediate |
| P1-3 | High | Billing Correctness / UX | Tax-rate semantics and display are inconsistent/misleading | This sprint |
| P1-4 | High | Workflow UX | Edit forms expose status fields that update paths intentionally ignore | This sprint |
| P1-5 | High | Architecture | "Thin blueprint / fat service" pattern remains inconsistently applied | Next sprint |
| P1-6 | High | Config/Security Ops | Config hierarchy docs conflict with initialization order | Next sprint |
| P1-7 | High | Documentation Governance | MEMORY/PROGRESS/UAT/blueprint claims materially diverge from code reality | Immediate |
| P1-8 | High | Test Quality | Tests are still weak on edge/environment realism and negative-path rigor | Immediate planning |
| P2-1 | Medium | Scalability | Search/export/reporting patterns will degrade with larger datasets | Next 1-2 sprints |
| P2-2 | Medium | Maintainability | Large files + duplicated lifecycle constants increase onboarding cost | Next 1-2 sprints |
| P2-3 | Medium | Correctness / UX | Broadcast notification read-state model and template behavior are misaligned | Next sprint |
| P2-4 | Medium | Repo Hygiene | Stale/missing references and ad-hoc artifacts add confusion | Cleanup pass |

---

## Detailed Findings

### P0-1: Decimal inventory migration is incomplete
**Evidence**
- Model now uses decimal stock fields: `app/models/inventory.py:42-43`.
- Forms still enforce integers:
  - `quantity_in_stock` / `reorder_level` are `IntegerField` in `app/forms/inventory.py:64-73`.
  - stock adjustment is `IntegerField` in `app/forms/inventory.py:151-154`.
- Route logic/messages still assume integer adjustments in `app/blueprints/inventory.py:237-241` and `app/blueprints/inventory.py:248-249`.
- Runtime probe confirms decimal form input is rejected (`Not a valid integer value`).

**Impact**
- Domain model says fractional stock is supported, but real user input paths reject it.
- High risk of false confidence that decimal migration is complete.

**When and how to fix (summary)**
- **Immediate**.
- Complete the migration end-to-end: forms, route handling, templates, exports, and associated tests.
- Define one precision/rounding/display policy and apply it consistently.

---

### P0-2: Part usage can push stock negative
**Evidence**
- `add_part_used()` deducts stock without insufficient-stock guard: `app/services/order_service.py:620`.
- Runtime probe against live container produced `inventory_after=-4.00`.
- Manual inventory adjustment route blocks negative outcomes (`app/blueprints/inventory.py:238-243`), but order-part flow does not.

**Impact**
- Inventory invariants are broken in the primary consumption path.
- Causes stock drift, unreliable reorder signals, and report corruption.

**When and how to fix (summary)**
- **Immediate**.
- Enforce non-negative stock invariant in service-layer deduction logic (including auto-deduct flows).
- Add insufficient-stock and concurrent-deduction tests.

---

### P1-1: Deployment health model produces false negatives
**Evidence**
- Image-level healthcheck targets web endpoint in `Dockerfile:66-67`.
- Worker and beat reuse same image (`docker-compose.yml:83-87`, `docker-compose.yml:104-108`).
- Runtime check shows `dsm-worker` and `dsm-beat` unhealthy while process logs show Celery running.

**Impact**
- Monitoring and orchestration see healthy workers as unhealthy.
- Can cause noisy alerts and potential restart churn.

**When and how to fix (summary)**
- **Immediate**.
- Separate health strategy by service role (web vs worker vs beat), or override healthchecks per service.

---

### P1-2: Startup migration/seed failures are non-fatal
**Evidence**
- Entrypoint catches migration/seed failures and continues startup: `docker-entrypoint.sh:8-16`.
- Blueprint now documents this behavior as intentional: `PROJECT_BLUEPRINT.md:1492`.

**Impact**
- App may run with schema mismatch or incomplete seed state.
- Failures are deferred into runtime errors instead of failing fast at deployment.

**When and how to fix (summary)**
- **Immediate**.
- Define explicit policy by environment: fail-fast in production, optional debug-continue mode for local troubleshooting.
- Document operational runbook for migration failure handling.

---

### P1-3: Tax input/display semantics are inconsistent
**Evidence**
- Form expects fraction `0..1`: `app/forms/invoice.py:67-72`.
- UAT guide instructs percent input (`8.25`): `docs/uat/UAT-07-invoices.md:46`.
- Invoice detail labels percent but formats raw `tax_rate`: `app/templates/invoices/detail.html:160`.

**Impact**
- Users can enter wrong values or misread displayed tax rates.
- Billing correctness and trust risk.

**When and how to fix (summary)**
- **This sprint**.
- Standardize one tax convention (fraction or percent) across form labels/help text, docs, and rendered output.

---

### P1-4: Edit forms expose status fields that update logic ignores
**Evidence**
- Order edit form renders status select: `app/templates/orders/form.html:68-71`.
- Invoice edit form renders status select: `app/templates/invoices/form.html:38-40`.
- `update_order()` intentionally excludes status: `app/services/order_service.py:212-241`.
- `update_invoice()` intentionally excludes status: `app/services/invoice_service.py:192-204`.
- Tests confirm status remains unchanged in update flows: `tests/unit/services/test_order_service.py:293-303`, `tests/unit/services/test_invoice_service.py:930-942`, `tests/blueprint/test_invoice_routes.py:308`.

**Impact**
- UI contradicts domain workflow rules.
- Confusing for users and junior contributors.

**When and how to fix (summary)**
- **This sprint**.
- Align forms with workflow model: remove misleading status controls from edit pages or route them to transition-specific flows.

---

### P1-5: Service-layer architecture remains inconsistent
**Evidence**
- Service package states blueprints should call services: `app/services/__init__.py:3-4`.
- Many phase-2 and admin routes still perform direct session/business operations:
  - `app/blueprints/customers.py:117`,
  - `app/blueprints/items.py:120`,
  - `app/blueprints/inventory.py:169`,
  - `app/blueprints/price_list.py:109`,
  - `app/blueprints/admin.py:95`.
- Search blueprint duplicates query logic and bypasses `search_service`: `app/blueprints/search.py:35-77` vs `app/services/search_service.py:58-153`.

**Impact**
- Rule duplication, uneven behavior, and weaker maintainability.
- Harder onboarding because there is no consistent “authoritative” layer.

**When and how to fix (summary)**
- **Next sprint**.
- Finish refactor for high-churn blueprints first, then enforce service-layer rule in review checklist.

---

### P1-6: Config hierarchy docs conflict with actual init order
**Evidence**
- Config docstring states hierarchy includes `instance/config.py` above defaults: `app/config.py:3`.
- App factory calls `init_app()` before loading instance config: `app/__init__.py:55-62`.
- Production secret checks run in `ProductionConfig.init_app`: `app/config.py:97-109`.

**Impact**
- Deployments relying on instance overrides can fail validation before those values are loaded.
- Ops behavior diverges from documented hierarchy.

**When and how to fix (summary)**
- **Next sprint**.
- Reconcile load order with documented hierarchy and explicitly define allowed production secret sources.

---

### P1-7: Documentation and progress artifacts are materially out of sync
**Evidence**
- `MEMORY.md` says phase 1 complete / phase 2 next: `MEMORY.md:61-64`.
- `PROGRESS.md` claims phase 6 plus post-phase fixes complete: `PROGRESS.md:156-257`.
- `MEMORY.md` lists blueprints/tables not present (e.g., `billing`, `import_data`, `api`, `system_config`, `saved_searches`, `attachments`): `MEMORY.md:27`, `MEMORY.md:39`.
- Registered blueprints do not include those entries: `app/__init__.py:116-146`.
- `seed-db` still marks system config as placeholder: `app/cli/seed.py:159-164`.
- UAT docs still reference `http://localhost:8080`: `docs/uat/UAT-05-price-list.md:10`, `docs/uat/UAT-06-service-orders.md:10`, `docs/uat/UAT-07-invoices.md:10`, `docs/uat/UAT-08-reports.md:10`, while UAT compose maps `8081`: `docker-compose.uat.yml:20`.
- UAT order status wording diverges from implemented status set: `docs/uat/UAT-06-service-orders.md:107-142` vs `app/models/service_order.py:23-33`.
- README/blueprint promise account lockout, but no lockout configuration is present in active config: `README.plan:47`, `PROJECT_BLUEPRINT.md:1215`, `app/config.py:33-52`.

**Impact**
- Team cannot trust docs as execution source-of-truth.
- Increases onboarding friction and QA errors.

**When and how to fix (summary)**
- **Immediate**.
- Re-baseline docs to current code, then add a release gate requiring doc parity for status claims.

---

### P1-8: Test quality is still weak on realistic edge cases
**Evidence**
- Core test stack uses in-memory SQLite only: `tests/conftest.py:21`, `app/config.py:116`.
- Validation suite is present but much thinner than documented 14-workflow expectation: 4 tests in `tests/validation/test_full_workflow.py` (`:37`, `:285`, `:362`, `:387`).
- UAT tests contain many soft/conditional assertions that can skip meaningful validation:
  - examples in `tests/uat/test_uat_e2e.py:109-117`, `tests/uat/test_uat_e2e.py:133`, `tests/uat/test_uat_e2e.py:174`,
  - `tests/uat/test_uat_orders.py:44`, `tests/uat/test_uat_invoices.py:31`, and many others.
- UAT runs single viewport and Chromium-only: `tests/uat/conftest.py:44`, `Dockerfile.uat:45`.
- `freezegun`/`responses` are installed but not used in tests (no usage found by repository scan).

**Impact**
- High reported coverage can still miss production failure modes.
- Weak assurance for browser/device/config/time-based behavior.

**When and how to fix (summary)**
- **Immediate planning**, staged next sprint.
- Prioritize risk-based additions: insufficient stock, negative paths, ownership checks, MariaDB parity subset, mobile/browser matrix, time-sensitive behavior.

---

### P2-1: Scalability risks remain in search/export/reporting paths
**Evidence**
- Search still uses `ILIKE` scans in both blueprint and service: `app/blueprints/search.py:35-77`, `app/services/search_service.py:58-153`.
- Export functions materialize full datasets with `.all()`: `app/services/export_service.py:137`, `179`, `222`, `261`, `310`, `351`, `394`, `433`.
- Revenue monthly grouping is done in Python: `app/services/report_service.py:89-105`.

**Impact**
- Query time and memory pressure will degrade with larger datasets.

**When and how to fix (summary)**
- **Next 1-2 sprints**.
- Move to indexed search strategy, chunked/streaming export, and DB-side aggregation where practical.

---

### P2-2: Maintainability and onboarding friction are still high
**Evidence**
- Large modules with mixed responsibilities:
  - `app/services/order_service.py` (~800 lines),
  - `app/services/invoice_service.py` (~620),
  - `app/blueprints/orders.py` (~600),
  - `app/blueprints/invoices.py` (~360).
- Lifecycle/status constants are duplicated across layers/templates, increasing drift risk.

**Impact**
- Harder for junior developers to find authoritative logic.
- More regression risk during policy changes.

**When and how to fix (summary)**
- **Next 1-2 sprints**.
- Split by use-case/domain and centralize lifecycle constants.

---

### P2-3: Broadcast notification read model and UI behavior are misaligned
**Evidence**
- Service supports per-user broadcast read receipts: `app/services/notification_service.py:59-92`, `app/services/notification_service.py:172-191`.
- Template still drives unread/read styling and actions from `notification.is_read`: `app/templates/notifications/list.html:40-42`, `app/templates/notifications/list.html:58`, `app/templates/notifications/list.html:76`.
- Broadcast notification row keeps `is_read=False` by design: `app/models/notification.py:56-58`, validated by tests (`tests/unit/services/test_notification_service.py:465-466`).

**Impact**
- Read-state display/action logic can be incorrect for broadcast notifications.

**When and how to fix (summary)**
- **Next sprint**.
- Pass user-resolved read-state to template (or expose computed property for current user) and align button/render conditions.

---

### P2-4: Repo hygiene and stale references still add noise
**Evidence**
- Tag macro references non-existent endpoint/component: `app/templates/macros/tags.html:23`, `app/templates/macros/tags.html:34`.
- No `api` blueprint is registered: `app/__init__.py:116-146`.
- Ad-hoc script with hardcoded credentials/URLs exists outside test structure: `test_uat_eval.py:17-20`, `test_uat_eval.py:12-13`.
- Migration ownership anomaly persists: `migrations/versions/46a737a590f6_phase_2_customers_service_items_drysuit_.py` owned by `dnsmasq:systemd-journal`.

**Impact**
- Raises onboarding uncertainty and release hygiene risk.

**When and how to fix (summary)**
- **Cleanup pass** after P0/P1 items.
- Remove or quarantine stale artifacts, resolve dangling references, normalize file ownership.

---

## Surface Security and Crash Pattern Review
Patterns that should be corrected:
- Enforce invariants (stock, lifecycle, ownership) in service/domain boundaries, not only in forms/routes.
- Fail predictably on critical startup path failures (schema/seed) in production.
- Strengthen negative-path tests for auth ownership, tampered statuses, invalid payloads, and concurrency.
- Keep operational docs aligned with actual behavior to avoid unsafe assumptions in deployment and support.

Glaring currently active concrete issues:
- Negative stock creation path (P0-2).
- Worker/beat unhealthy false negatives in deployed stack (P1-1).

## Recommended Verification Tests After Fixes (Do Not Run Yet)
1. Fractional inventory acceptance tests across form, route, service, and export layers.
2. Insufficient-stock and concurrent-deduction tests for part usage.
3. Deployment smoke checks verifying correct health semantics per container role.
4. Startup safety tests for migration/seed failure behavior by environment policy.
5. Billing UX tests covering tax input/output semantics and rounding behavior.
6. UAT hardening: remove conditional soft assertions, add mobile viewport, add non-Chromium run.
7. MariaDB parity subset in CI for transaction, precision, and collation/search behavior.
8. Security negatives: cross-user notification operations, invalid status transitions, malformed write payloads.

## Suggested Fix Sequence
1. **Immediate (P0)**: close inventory integrity gaps end-to-end.
2. **Immediate (P1)**: fix deployment health and startup safety behavior.
3. **This sprint (P1)**: resolve tax/status UX inconsistencies and major doc drift.
4. **Next sprint (P1/P2)**: complete service-layer consolidation and notification UI/read-state alignment.
5. **Next 1-2 sprints (P2)**: scalability + maintainability refactors.
6. **Cleanup pass (P2)**: remove stale references/artifacts and normalize repo hygiene.
