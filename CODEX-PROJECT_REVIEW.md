# CODEX Project Re-Review (2026-03-10)

## Scope and Method
- This report overwrites the prior CODEX review.
- Per request, I did **not** run project test suites and did **not** change code.
- Required docs were re-read first, in order:
  - `README.plan`
  - `PROJECT_BLUEPRINT.md`
  - `MEMORY.md`
  - `PROGRESS.md`
- I also reviewed `GEMINI-PROJECT_REVIEW.md` and carried forward only still-valid findings.
- I re-reviewed code, templates, migrations, and tests, and used targeted UAT/runtime probes (non-test scripts) for high-risk behaviors.

## Key Re-Validation Since Prior Review
These prior critical items are now fixed and should remain closed:
- Inventory model columns changed to decimal (`app/models/inventory.py:42-43`).
- Per-user broadcast notification read tracking implemented (`app/models/notification_read.py`, `app/services/notification_service.py`).
- Invoice status transition validation exists (`app/services/invoice_service.py:41-50`, `231-258`).
- Refund math is type-aware in payment aggregation (`app/services/invoice_service.py:579-589`).
- Health check now catches specific SQLAlchemy exceptions (`app/blueprints/health.py:28-33`).

## Executive Assessment
The project has improved materially, but the current implementation still falls short of the “Phase 6 complete / production-ready” bar claimed in docs. The top risks are now **incomplete inventory decimal migration**, **negative stock integrity holes**, and **documentation/testing drift that obscures actual behavior and readiness**.

## Priority Summary
| ID | Priority | Area | Issue | Suggested Fix Window |
|---|---|---|---|---|
| P0-1 | Critical | Data Integrity | Decimal inventory migration is incomplete across forms/routes/tests | Immediate |
| P0-2 | Critical | Data Integrity / Crash | Order part usage can drive inventory negative | Immediate |
| P1-1 | High | Billing Correctness / UX | Tax-rate semantics and display are inconsistent and misleading | This sprint |
| P1-2 | High | Workflow UX | Order/invoice edit forms expose status fields that are ignored by update paths | This sprint |
| P1-3 | High | Architecture | “Thin blueprints, fat services” pattern is still inconsistent | Next sprint |
| P1-4 | High | Config/Security Ops | Config hierarchy docs conflict with app init order for production secret checks | Next sprint |
| P1-5 | High | Documentation Governance | MEMORY/PROGRESS/UAT docs materially diverge from code reality | Immediate |
| P1-6 | High | Test Quality | UAT and core tests remain too shallow for edge/environment realism | Immediate planning |
| P2-1 | Medium | Scalability | Search/export/report patterns still rely on `ILIKE`, `.all()`, and Python grouping | Next 1-2 sprints |
| P2-2 | Medium | Maintainability | Large files and duplicated workflow constants increase onboarding cost | Next 1-2 sprints |
| P2-3 | Medium | Repo Hygiene | Empty/stale artifacts and unresolved template references create noise | Cleanup pass |

---

## Detailed Findings

### P0-1: Decimal inventory migration is incomplete
**Evidence**
- Inventory model now uses decimals (`app/models/inventory.py:42-43`).
- Inventory forms still enforce integers:
  - `quantity_in_stock` / `reorder_level` are `IntegerField` (`app/forms/inventory.py:64-73`).
  - stock adjustment is `IntegerField` (`app/forms/inventory.py:151-154`).
- Inventory blueprint logic is integer-oriented (`app/blueprints/inventory.py:154-155`, `237-241`, `248`).
- Test suites are still primarily integer-based for inventory route/form behavior (`tests/unit/forms/test_inventory_form.py`, `tests/blueprint/test_inventory_routes.py`).
- Runtime probe (UAT app context):
  - Posting `quantity_in_stock='2.5'` and `reorder_level='1.25'` to `InventoryItemForm` fails with `"Not a valid integer value."`.

**Impact**
- The domain model supports fractional stock, but UI and route layers reject it.
- Team can think decimal support is complete while production users cannot enter valid fractional inventory data.

**Suggested fix window and approach**
- **Immediate**.
- Complete decimal migration end-to-end: forms, route logic/formatting, and tests.
- Decide precision/rounding/display policy once and apply consistently across model, forms, templates, and exports.

---

### P0-2: Part usage can push stock negative
**Evidence**
- `add_part_used()` deducts stock directly with no floor check (`app/services/order_service.py:620`).
- Runtime probe in UAT web container:
  - inventory started at `1.00`,
  - adding part usage of `5.00`,
  - resulting stock became `-4.00`.
- There is negative-stock protection in inventory manual adjustment (`app/blueprints/inventory.py:238-243`), but not in order-part consumption flow.

**Impact**
- Core inventory invariants are not enforced in the main consumption path.
- Leads to invalid stock states, broken reorder signals, and unreliable valuation/usage reports.

**Suggested fix window and approach**
- **Immediate**.
- Enforce non-negative stock invariants in service-layer deduction logic (including auto-deduct paths), with explicit behavior for insufficient stock.
- Add targeted tests for insufficient inventory and concurrent deductions.

---

### P1-1: Tax-rate semantics and display are inconsistent/misleading
**Evidence**
- Invoice form enforces `tax_rate` as decimal fraction `0..1` (`app/forms/invoice.py:67-72`).
- UAT doc instructs entering `8.25` for 8.25% (`docs/uat/UAT-07-invoices.md:46`).
- Invoice totals use fractional rate (`app/models/invoice.py:190-191`), but detail template labels it as percent without scaling (`app/templates/invoices/detail.html:160`).

**Impact**
- Operators can enter incorrect tax values or misread displayed percentages.
- Billing correctness and user trust are affected even when math logic is technically correct for fraction inputs.

**Suggested fix window and approach**
- **This sprint**.
- Standardize tax input/display semantics (fraction vs percent) in form labels/help text, docs/UAT, and rendered invoice detail.

---

### P1-2: Edit forms expose status fields that updates intentionally ignore
**Evidence**
- Order edit form shows editable status (`app/templates/orders/form.html:68-71`).
- Order edit route submits `status` (`app/blueprints/orders.py:260`), but service update ignores status and requires transition path (`app/services/order_service.py:235-240`), confirmed by tests (`tests/unit/services/test_order_service.py:293-303`).
- Invoice edit form similarly shows status (`app/templates/invoices/form.html:38-40`), but update path does not apply status (`app/services/invoice_service.py:192-204`), and tests assert this (`tests/blueprint/test_invoice_routes.py:307-308`, `tests/unit/services/test_invoice_service.py:930-942`).

**Impact**
- UX contradicts domain rules.
- Junior contributors and users get a misleading mental model of status lifecycle behavior.

**Suggested fix window and approach**
- **This sprint**.
- Align UI with actual workflow: either remove edit-form status controls or route edits through validated transition logic with clear feedback.

---

### P1-3: Architecture still deviates from declared service-layer pattern
**Evidence**
- Services package explicitly states blueprints should call services (`app/services/__init__.py:3-4`).
- Phase-2 blueprints still do direct ORM/session writes (examples: `app/blueprints/customers.py`, `items.py`, `inventory.py`, `price_list.py`, plus admin routes).
- Several service modules remain largely unused by blueprints (`customer_service`, `inventory_service`, `price_list_service`, `search_service`, `tag_service`).

**Impact**
- Increases duplicate logic and inconsistent behavior across domains.
- Makes onboarding harder: contributors cannot rely on one consistent layer for business rules.

**Suggested fix window and approach**
- **Next sprint**.
- Finish refactoring high-churn phase-2 blueprints to service calls.
- Define and enforce a contribution rule: business logic in services, not routes.

---

### P1-4: Config hierarchy documentation conflicts with initialization order
**Evidence**
- Config docs state hierarchy includes `instance/config.py` above app defaults (`app/config.py:3`, `PROJECT_BLUEPRINT.md:1752-1757`).
- App factory runs `config_class.init_app(app)` **before** loading `instance/config.py` (`app/__init__.py:55-62`).
- `ProductionConfig.init_app` performs strict default-secret checks (`app/config.py:97-109`).

**Impact**
- If a deployment relies on `instance/config.py` for secret overrides, startup validation can fail before those values are loaded.
- Operational behavior diverges from documented config model.

**Suggested fix window and approach**
- **Next sprint**.
- Reconcile order-of-operations with documented hierarchy and document exactly which sources are valid for production secrets.

---

### P1-5: Documentation drift remains significant
**Evidence**
- `MEMORY.md` still states current phase is “1 complete, phase 2 next” (`MEMORY.md:61-64`) while `PROGRESS.md` claims post-phase-6 completion (`PROGRESS.md:156-241`).
- `MEMORY.md` lists blueprints/tables not present in code (e.g., `billing`, `import_data`, `api`; `system_config`, `saved_searches`, `attachments`) (`MEMORY.md:27`, `39`).
- Actual registered blueprints are 16 and do not include those entries (`app/__init__.py:116-146`).
- `tests/uat/UAT_PLAN.md` still marks orders/invoices/reports/tools as placeholders (`tests/uat/UAT_PLAN.md:130-133`) despite real test files existing (`tests/uat/test_uat_orders.py`, `test_uat_invoices.py`, `test_uat_reports.py`, `test_uat_tools.py`).
- UAT docs still reference `http://localhost:8080` while UAT compose exposes `8081` (`docs/uat/UAT-05-price-list.md:10`, `UAT-06-service-orders.md:10`, `UAT-07-invoices.md:10`, `UAT-08-reports.md:10`; `docker-compose.uat.yml:20`).
- UAT order status terminology does not match implemented status set (`docs/uat/UAT-06-service-orders.md:107-142` vs `app/models/service_order.py:23-33`).

**Impact**
- Team planning and onboarding become unreliable.
- QA scripts encourage incorrect data entry and wrong expectations.

**Suggested fix window and approach**
- **Immediate**.
- Re-baseline docs against current code and gate “complete” status on doc parity checks.

---

### P1-6: Test quality and realism are still below project claims
**Evidence**
- Core test stack is SQLite in-memory (`tests/conftest.py:21`; `app/config.py:116`), not MariaDB parity by default.
- UAT tests contain many conditional assertions that can silently pass without validating behavior (examples: `tests/uat/test_uat_orders.py:44`, `54`; `tests/uat/test_uat_invoices.py:31`; `tests/uat/test_uat_e2e.py:109-117`, `133`, `174`; `tests/uat/test_uat_price_list.py:36-40`; `tests/uat/test_uat_customers.py:58`, `78`).
- UAT fixture is fixed desktop viewport only (`tests/uat/conftest.py:44`).
- UAT Dockerfile installs Chromium only (`Dockerfile.uat:45`).
- Missing coverage for important edge/business risks remains visible:
  - no insufficient-stock tests for order part deduction path,
  - no explicit cross-user negative tests for notifications mark-read behavior.

**Impact**
- High coverage numbers may still miss realistic breakage modes.
- Browser/device/theme/config variance risk is largely untested.

**Suggested fix window and approach**
- **Immediate planning**, staged over next sprint.
- Prioritize risk-based tests: negative stock, insufficient stock, concurrency, auth ownership negatives, MariaDB parity, mobile/browser matrix.

---

### P2-1: Scalability bottlenecks remain in search/export/reporting
**Evidence**
- Search is still `ILIKE`-based in both blueprint and service (`app/blueprints/search.py:35-77`, `app/services/search_service.py:58-153`) despite FULLTEXT requirements (`README.plan:69-72`, `PROJECT_BLUEPRINT.md:1281-1302`).
- Exports materialize full result sets with `.all()` (e.g., `app/services/export_service.py:137`, `179`, `222`, `261`, `310`, `351`, `394`, `433`).
- Revenue monthly aggregation uses Python-side grouping (`app/services/report_service.py:89-105`).
- Order/invoice aggregation paths iterate nested dynamic relationships with repeated `.all()` (e.g., `app/services/order_service.py:770-784`, `app/services/invoice_service.py:357-393`).

**Impact**
- Performance and memory behavior will degrade with real historical data volumes.

**Suggested fix window and approach**
- **Next 1-2 sprints**.
- Move to indexed search strategy, chunked/streaming exports, and SQL-side aggregation where practical.

---

### P2-2: Maintainability/onboarding friction is still high
**Evidence**
- Large multi-responsibility files:
  - `app/services/order_service.py` (808 lines),
  - `app/services/invoice_service.py` (624),
  - `app/blueprints/orders.py` (614),
  - `app/blueprints/invoices.py` (365).
- Workflow constants duplicated across models/forms/services/templates (status sets and transition maps in multiple locations), e.g.:
  - `app/services/order_service.py:35-45`
  - `app/forms/order.py:29-39`
  - `app/models/service_order.py:23-33`
  - `app/templates/orders/detail.html:10-32`
  - similar duplication in invoice equivalents.

**Impact**
- More places to update for each policy change.
- Junior developers have a harder time identifying the authoritative source of truth.

**Suggested fix window and approach**
- **Next 1-2 sprints**.
- Split large modules by use-case and centralize status/transition constants in one domain layer.

---

### P2-3: Repo hygiene and stale artifacts still need cleanup
**Evidence**
- Empty template/static directories remain (`app/templates/admin/settings`, `app/templates/admin/data`, `app/templates/billing`, `app/templates/partials`, `app/static/img`, `app/static/vendor`).
- Tag macro references missing endpoint (`app/templates/macros/tags.html:23` references `api.tag_suggestions`, no `api` blueprint exists).
- Migration file ownership anomaly persists (`migrations/versions/46a737a590f6_phase_2_customers_service_items_drysuit_.py` owned by `dnsmasq:systemd-journal`).

**Impact**
- Adds noise for onboarding and release hygiene.

**Suggested fix window and approach**
- **Cleanup pass** after P0/P1 fixes.
- Remove or consolidate dead artifacts; resolve ownership/permissions consistency.

---

## Surface Security and Crash Pattern Review
Current pattern-level concerns to correct:
- Inventory/financial invariants must be enforced in service layer, not only in selected routes/forms.
- Documentation promises (lockout, config hierarchy, feature readiness) should match deployed behavior to avoid operational/security assumptions.
- Negative-path tests should explicitly verify ownership and invalid-input handling for critical routes/services.

Notable specific risk observed now:
- `add_part_used` allowing negative stock is a concrete integrity defect (see P0-2).

## Suggested Fix Sequence (When and How)
1. **Immediate (P0)**: close inventory integrity holes (decimal path completion + no-negative-stock invariant), then backfill targeted tests.
2. **This sprint (P1)**: resolve billing/status UX mismatches and documentation/UAT drift.
3. **Next sprint (P1/P2)**: complete service-layer consolidation and config hierarchy alignment.
4. **Next 1-2 sprints (P2)**: address scalability and module decomposition.
5. **Cleanup pass (P2)**: remove stale artifacts and clean migration ownership/hygiene.

## Recommended Tests to Run After Fixes
Do not run until the team is ready (per request). Recommended next execution set:
1. Inventory decimal acceptance tests (form + route + service + export) including fractional stock adjustment.
2. Insufficient stock and concurrent part deduction tests (service + route).
3. MariaDB-backed CI subset for transactions, constraints, numeric precision, and collation/search behavior.
4. Billing UX tests for tax input/display semantics and rounding.
5. UAT hardening:
   - remove conditional “if exists/visible” soft assertions,
   - add at least one mobile viewport,
   - add at least one non-Chromium browser run,
   - add theme/font smoke checks.
6. Security negative tests:
   - cross-user notification read attempts,
   - tampered status transitions,
   - invalid payloads across key write routes.

## Runtime Probe Appendix (Non-Test Validation)
- Environment check: UAT stack is served on `http://localhost:8081` (`docker-compose.uat.yml:20`), not `8080`.
- Probe 1 (inventory form): fractional `quantity_in_stock`/`reorder_level` fails validation as integer.
- Probe 2 (service layer): consuming quantity `5.00` from stock `1.00` produced `inventory_after = -4.00`.
