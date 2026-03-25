# Dive Service Management - Implementation Progress

## Timeline

### Phase 0: Planning (Complete)
- [x] Initial README.plan created
- [x] PROJECT_BLUEPRINT.md written (14 sections, ~2800 lines)
- [x] Price list with real-world drysuit repair pricing added
- [x] Deployment script (setup.sh) specified
- [x] Testing strategy defined (4 test categories, phase gates)
- [x] Critical review performed: 12 pre-implementation items identified and applied
  - Architecture: fpdf2 primary PDF, Huey lightweight alternative, Pi MariaDB tuning
  - Data model: Circular FK removed, applied_service traceability, many-to-many invoices, drysuit_details table
  - Features: Attachments, customer approval workflow, deposits, warranty tracking
  - Additional fields: condition_at_receipt, pickup tracking, customer billing defaults, inventory expiration

### Phase 1: Foundation (Complete)
**Target**: Project scaffolding, Docker, config, DB schema, base template, auth, CLI

- [x] Project scaffolding (directory structure, requirements, pyproject.toml)
- [x] Docker setup (Dockerfile, docker-compose.yml, lightweight profile, DB config)
- [x] Configuration system (config.py, .env.example, extensions.py)
- [x] Application factory (app/__init__.py)
- [x] Model mixins (TimestampMixin, SoftDeleteMixin, AuditMixin)
- [x] User/Role models + Alembic migrations
- [x] Base template with navigation, theme support, error pages
- [x] Static assets (HTMX, Alpine.js, Bootstrap via CDN; CSS themes, app.js)
- [x] Flask-Security-Too authentication (login, logout, password management)
- [x] Flask CLI commands (seed-db, create-admin)
- [x] Makefile + scripts/setup.sh
- [x] Health check endpoint (/health with DB connectivity check)
- [x] Docker-based testing workflow (Dockerfile.test, docker-compose.test.yml)
- [x] Phase 1 tests: 36 tests (10 smoke, 14 unit, 9 blueprint, 3 health)
- [x] Phase 1 gate: all 36 tests pass, 93.27% coverage (target: 80%)

**Critical Review Findings (resolved)**:
- Added /health endpoint (Docker health check was referencing it)
- Initialized Alembic migrations directory with initial schema migration
- Added Flask-Mail to requirements.txt (was imported but not listed)
- Added DSM_SECURITY_PASSWORD_SALT to .env.example and setup.sh
- Added admin_client, viewer_client test fixtures for Phase 2 readiness
- Added theme CSS links and htmx-loading-bar to base.html
- Created .dockerignore for efficient builds

**Remaining low-priority items for future phases**:
- Vendor frontend libraries (currently CDN-only; works but not offline-ready)
- Wire up ExtendedLoginForm (exists but not connected to Flask-Security)
- Add docker-compose.override.yml template for dev workflow

### Phase 2: Core Entities (Complete)
**Target**: Customer, ServiceItem, Inventory, PriceList, Tags, Search

- [x] Customer model with validation, soft-delete, display_name/full_address properties
- [x] ServiceItem model with serial number tracking, serviceability status
- [x] DrysuitDetails model (1:1 extension for drysuit-specific fields)
- [x] InventoryItem model with stock management, is_low_stock property
- [x] PriceList models (PriceListCategory, PriceListItem, PriceListItemPart)
- [x] Tag/Taggable polymorphic tagging system with TaggableMixin
- [x] Customer, Item, Inventory, PriceList, Search forms (WTForms)
- [x] Customer, Inventory, PriceList, Tag, Search services (business logic layer)
- [x] Customers blueprint (list, detail, create, edit, delete)
- [x] Items blueprint (list, lookup, detail, create, edit, delete, drysuit fields)
- [x] Inventory blueprint (list, low-stock, detail, create, edit, delete, stock adjust)
- [x] Price List blueprint (list, detail, create, edit, duplicate, categories)
- [x] Search blueprint (global search results, HTMX autocomplete)
- [x] 16 templates + 4 macro files (status_badges, tables, tags, modals)
- [x] Base template: sidebar nav wired, global search form, pagination macro fix
- [x] Config: SECURITY_UNAUTHORIZED_VIEW=None for proper 403 responses
- [x] Test factories (Factory Boy) for all models
- [x] Phase 2 tests: 377 total, 94.01% coverage (target: 80%)

### UAT Testing Framework (Complete)

- [x] UAT test plan (tests/uat/UAT_PLAN.md) with per-phase timing schedule
- [x] Playwright infrastructure (Dockerfile.uat, docker-compose.uat.yml, requirements-uat.txt)
- [x] UAT conftest with browser fixtures (admin_page, tech_page, viewer_page)
- [x] Phase 1 UAT: test_uat_auth.py (6 tests)
- [x] Phase 2 UATs: customers (7), items (6), inventory (6), price_list (4), search (3)
- [x] End-to-end UAT: test_uat_e2e.py (full workflow with Phase 3-5 placeholders)
- [x] Future phase placeholders: orders, invoices, reports, tools
- [x] UAT excluded from standard test runs (--ignore=tests/uat in pyproject.toml)
- [ ] UAT scripts updated as each phase completes to match actual output

### Phase 2 → Phase 3 Gate: External Review Fix-ups (Complete)

**Trigger**: External code reviews identified issues to address before Phase 3.

**Fixed Now**:

- [x] Sort parameter injection — added SORTABLE_FIELDS allowlists in customers, items, inventory blueprints
- [x] IntegrityError handling — wrapped db.session.commit() with try/except in customers, items, inventory, price_list for duplicate unique fields (email, serial_number, sku, code)
- [x] Setup script stale messages — updated seed-db and create-admin fallback messages (were saying "not yet available")
- [x] MEMORY.md and PROGRESS.md sync — updated to reflect actual state

**Deferred to Later Phases**:

- Service layer refactoring (Phase 3 new code uses services; existing blueprints refactored incrementally)
- Drysuit logic extraction from items.py to item_service.py (Phase 3)
- Validation workflow tests (progressive, each phase)
- Migration quality gate / test-vs-Alembic alignment (Phase 6)
- Tag UI integration into entity workflows (Phase 3+)
- FULLTEXT search + HTMX autocomplete (Phase 5)
- Inconsistent populate_obj usage (Phase 3 refactor)

### Phase 3: Service Workflow (Complete)

**Target**: Orders, AppliedServices, PartsUsed, Labor, Notes, Status workflow

- [x] ServiceOrder model with status workflow, priority, customer/tech assignment, approval/pickup fields
- [x] ServiceOrderItem model with warranty tracking, condition-at-receipt, per-item status
- [x] AppliedService model linking price list items to order items with price snapshots
- [x] PartUsed model with inventory deduction/restoration and cost snapshots
- [x] LaborEntry model with tech assignment and rate snapshots
- [x] ServiceNote model with typed notes (diagnostic, repair, testing, general, customer_communication)
- [x] order_service.py — full service layer with status transitions, order number generation, CRUD, sub-entity management, order summary calculations
- [x] Orders blueprint — 16 routes using service layer, role-based access, SORTABLE_FIELDS allowlist
- [x] ServiceOrderForm, OrderSearchForm, ServiceOrderItemForm, AppliedServiceForm, PartUsedForm, LaborEntryForm, ServiceNoteForm
- [x] Templates: orders/list.html, form.html, detail.html (full workspace), kanban.html (placeholder)
- [x] Base template: sidebar Orders link wired to orders.list_orders
- [x] Test factories for all Phase 3 models
- [x] Phase 3 tests: 516 total, 91.23% coverage (target: 80%)

### Phase 4: Billing (Complete)
**Target**: Invoices, Payments, Line Items, Invoice Generation from Orders

- [x] Invoice model with status tracking (draft→sent→paid/void/refunded), financial fields, recalculate_totals()
- [x] InvoiceLineItem model with type classification (service, labor, part, fee, discount), traceability links
- [x] invoice_orders many-to-many association table linking invoices to service orders
- [x] Payment model with payment types (payment, deposit, refund), methods, and external system fields
- [x] invoice_service.py — full service layer with CRUD, invoice number generation (INV-YYYY-NNNNN), generate_from_order(), line item management, payment recording with auto-status transitions
- [x] Invoices blueprint — 11 routes using service layer, role-based access (void=admin only), SORTABLE_FIELDS
- [x] InvoiceForm, InvoiceSearchForm, InvoiceLineItemForm, PaymentForm
- [x] Templates: invoices/list.html, form.html, detail.html (workspace with line items, payments, status changes)
- [x] Base template: sidebar Invoices link wired to invoices.list_invoices
- [x] Test factories: InvoiceFactory, InvoiceLineItemFactory, PaymentFactory
- [x] Phase 4 tests: 635 total, 91.24% coverage (target: 80%)

### Phase 5: Reports, Tools, Polish (Complete)

**Target**: Reports, Calculators, Import/Export, Notifications

- [x] Notification model with severity levels, entity linking, read/unread tracking
- [x] report_service.py — 5 report functions: revenue, orders, inventory, customers, aging
- [x] notification_service.py — CRUD, unread counts, mark-as-read, domain notifications (low stock, order status, payment)
- [x] export_service.py — CSV and XLSX export for customers, inventory, orders, invoices (with openpyxl)
- [x] Reports blueprint — 6 routes (hub, revenue, orders, inventory, customers, aging)
- [x] Reports templates — hub with card links, 5 report pages with Chart.js visualizations, date range filters
- [x] Tools blueprint — 7 routes (hub + 6 tools)
- [x] Tools templates — seal calculator, material estimator, pricing calculator, leak test log, valve reference, unit converter (Alpine.js client-side)
- [x] Notifications blueprint — 4 routes (list, unread count JSON, mark read, mark all read)
- [x] Export blueprint — 8 endpoints (4 entities x CSV/XLSX)
- [x] Base template: sidebar Reports and Tools links wired
- [x] Test factories: NotificationFactory
- [x] Phase 5 tests: 726 total, 92% coverage (target: 80%)

### Phase 6: Production Readiness (Complete)

**Target**: Migrations, Docker verification, Security audit, Makefile updates

- [x] Alembic migration for Phases 3-5 (11 tables: service_orders, service_order_items, service_notes, applied_services, parts_used, labor_entries, invoices, invoice_orders, invoice_line_items, payments, notifications)
- [x] Dockerfile verified: multi-stage build, non-root user, health check, proper gunicorn config
- [x] docker-compose.yml verified: health checks, service dependencies, restart policies, named volumes
- [x] .env.example verified: all active DSM_ variables documented (mail vars deferred — not yet active)
- [x] config.py verified: ProductionConfig disables DEBUG, argon2 password hashing, proper SECRET_KEY handling
- [x] Makefile updated: added export-test and lint targets
- [x] All 15 blueprints registered and wired (admin, auth, customers, dashboard, export, health, inventory, invoices, items, notifications, orders, price_list, reports, search, tools)
- [x] All sidebar links wired to actual routes
- [x] Phase 6 tests: 726 total, 92% coverage (target: 80%) — all passing

### Post-Phase 6: Review Fixes and Enhancements (Complete)

**Trigger**: External code reviews and manual UAT identified issues to address.

**Critical (P0) Fixes**:

- [x] P0-1: Inventory truncation — `int()` → `round()` for decimal quantity deductions in order_service.py
- [x] P0-2: Notification auth — added user ownership check to `mark_as_read` (IDOR prevention)
- [x] P0-3: Number generation race — retry-on-IntegrityError for order/invoice creation
- [x] P0-4: Refund math — type-aware payment sum using `case()` for refund/deposit/payment handling

**High Priority (P1) Fixes**:

- [x] P1-4: Invoice status bypass — VALID_STATUSES allowlist on change_status route

**Medium Priority (P2) Fixes**:

- [x] P2-4: Health endpoint — specific exception types (OperationalError/SQLAlchemyError) instead of broad catch
- [x] P2-3: pyproject.toml README reference fixed
- [x] P2-3: Placeholder stubs documented and cleaned up

**Feature Enhancements**:

- [x] Dashboard — live open orders, awaiting pickup, low stock alerts, overdue invoices counts
- [x] Dashboard — quick action links wired to real routes
- [x] Admin blueprint — user management (list, create, edit, toggle active, password reset)
- [x] Admin blueprint — system settings overview
- [x] Admin blueprint — data management with backup/restore instructions and export links
- [x] Admin sidebar link wired to actual route
- [x] Seed data — 6 price list categories, 3 demo users seeded by default
- [x] Empty-state UX warnings for service items and price list categories
- [x] Report service — MariaDB-compatible date calculations (Python-side grouping)
- [x] UAT scripts — 11 markdown test scripts with screenshots in docs/uat/
- [x] README.md created for GitHub
- [x] .gitignore enhanced with credential/key exclusions

**Tests**: 757 total, all passing (802 after review fix-ups below)

### Post-Phase 6: Second Review Fix-ups (Complete)

**Trigger**: CODEX and Gemini static reviews identified additional correctness, security, and resilience issues.

**Critical (P0) Fixes**:

- [x] P0-1: Inventory stock drift — changed `quantity_in_stock`/`reorder_level` from `Integer` to `Numeric(10,2)`, removed 5 `round()` calls in order_service.py ([PR #1](https://github.com/llathrop/Dive_Service_Management/pull/1))
- [x] P0-2: Notification broadcast read state — added `NotificationRead` model for per-user broadcast tracking, rewrote notification_service with outerjoin pattern ([PR #2](https://github.com/llathrop/Dive_Service_Management/pull/2))
- [x] P0-3: Order status/priority bypass — removed status/priority from `update_order()` generic loop, added priority allowlist validation, guarded `change_status()` against empty values, added `DataRequired()` to form ([PR #3](https://github.com/llathrop/Dive_Service_Management/pull/3))

**High Priority (P1) Fixes**:

- [x] P1-1+P1-6: Invoice lifecycle — added `INVOICE_STATUS_TRANSITIONS` state machine, `change_status()` function, removed status from `update_invoice()`, added negative `unit_price` guard for non-discount line items ([PR #4](https://github.com/llathrop/Dive_Service_Management/pull/4))
- [x] P1-4: Security posture — `ProductionConfig.init_app()` rejects default secrets at startup, `_seed_demo_users()` skips in production mode ([PR #5](https://github.com/llathrop/Dive_Service_Management/pull/5))
- [x] P1-5: Crash resilience — `try/except ValueError` on add_part/add_labor/add_note routes, fixed `unread_only` bool parsing in notifications ([PR #6](https://github.com/llathrop/Dive_Service_Management/pull/6))

**Deferred to future sprints**:

- P1-2: Service layer refactoring for Phase 2 blueprints (customers, items, inventory, price_list, search)
- P2-1: Search FULLTEXT and export streaming/pagination for large datasets
- P2-2: Module splitting and repeated mapping logic consolidation

**Ignored (with rationale)**:

- P1-3: Documentation drift — addressed via this PROGRESS.md update and MEMORY.md sync
- P2-3: Repo hygiene (empty dirs, placeholder comments) — low risk, cleanup only
- P3-2: `populate_obj` usage inconsistency — cosmetic, not a correctness issue

**Database migrations**: 2 new migrations added

- `a1b2c3d4e5f6`: Inventory columns `Integer` → `Numeric(10,2)`
- `b2c3d4e5f6a7`: `notification_reads` table for per-user broadcast read tracking

**Tests**: 802 total, all passing

### Infrastructure: Auto-Migration and Persistence (Complete)

- [x] `docker-entrypoint.sh` — web container auto-runs `flask db upgrade` and `flask seed-db` on startup; worker/beat containers skip migration step
- [x] `Dockerfile` — added `ENTRYPOINT ["./docker-entrypoint.sh"]` before `CMD`
- [x] `Dockerfile.uat` — added `default-libmysqlclient-dev` and simplified pip install (requirements-dev.txt includes requirements.txt transitively)
- [x] `PROJECT_BLUEPRINT.md` section 8.2 — documented hard constraints for data persistence and auto-upgrade
- [x] `README.md` — updated setup instructions to reflect automatic migration/seeding
- [x] `.gitignore` — added exclusions for `.claude/`, `MEMORY.md`, `test_uat_eval.py`

**Hard constraints documented**:

1. Production DB must use named Docker volume for persistence across restarts
2. App must auto-detect and upgrade prior DB schema versions on startup
3. All schema changes must have Alembic migration scripts
4. Database seeding must be idempotent and run automatically

### Post-Phase 6: Third Review Fix-ups — CODEX Re-Review (Complete)

**Trigger**: CODEX static re-review (2026-03-04, updated 2026-03-10) identified remaining correctness and usability issues.

**Critical (P0) Fixes**:

- [x] P0-1: Inventory form decimal truncation — `IntegerField` → `DecimalField` for `quantity_in_stock`, `reorder_level`, and stock adjustment fields ([PR #9](https://github.com/llathrop/Dive_Service_Management/pull/9))
- [x] P0-2: Negative stock prevention — `add_part_used()` now raises `ValueError` when deduction exceeds available stock ([PR #10](https://github.com/llathrop/Dive_Service_Management/pull/10))

**High Priority (P1) Fixes**:

- [x] P1-1: Worker/beat healthchecks — added `celery inspect ping` for worker, `pgrep` for beat in docker-compose.yml ([PR #11](https://github.com/llathrop/Dive_Service_Management/pull/11))
- [x] P1-2: Fail-fast entrypoint — migration/seeding failures now exit 1 in production mode ([PR #15](https://github.com/llathrop/Dive_Service_Management/pull/15))
- [x] P1-3: Tax rate display — template now multiplies by 100 before showing %, form placeholder clarified ([PR #16](https://github.com/llathrop/Dive_Service_Management/pull/16))
- [x] P1-4: Misleading status fields — removed editable status dropdowns from order/invoice edit forms ([PR #17](https://github.com/llathrop/Dive_Service_Management/pull/17))
- [x] P1-7: Documentation drift — PROGRESS.md, MEMORY.md updated to match current state

**Deferred to future sprints**:

- P1-5: Service layer refactoring for Phase 2 blueprints
- P1-8: Test quality gaps (MariaDB parity tests, time-freezing, validation suite)
- P2-1: Scalability (FULLTEXT search, streaming exports)
- P2-2: Module splitting for maintainability
- P2-3: Broadcast notification UI alignment
- P2-4: Repo hygiene cleanup

**Tests**: 809+ total, all passing

### Admin Overhaul: Settings & Data Management (Complete)

**Trigger**: Admin System Settings and Data Management pages are entirely read-only. All configurable settings should be editable from the web UI.

**Implementation Plan — 4 PRs**:

**PR A: SystemConfig Foundation** (prerequisite for all others)
- SystemConfig model (`system_config` table per PROJECT_BLUEPRINT.md section 9.3)
- Alembic migration for new table
- `config_service.py` with `get_config(key)`, `set_config(key, value)`, type coercion, ENV override locking
- Seed ~25 default config entries via `flask seed-db` (company, invoice, tax, service, notification, display, security categories)
- ~25 tests covering model, service, seeding, ENV override behavior

**PR B: Editable Settings UI**
- Replace read-only settings.html with tabbed form layout (6 tabs: Company, Service, Invoice/Tax, Display, Notifications, Security)
- WTForms for each settings category, pre-populated from `config_service`
- POST routes to save settings back to `system_config` table
- ENV-locked settings shown as read-only with explanation
- Infrastructure info cards (DB engine, Redis status) remain read-only with useful diagnostics
- Wire config values into app logic (e.g., `invoice.default_terms`, `tax.default_rate`)
- ~35 tests covering form rendering, save, ENV locking, validation

**PR C: Actionable Data Management**
- `data_management_service.py` for live DB info queries (table sizes, row counts, DB version)
- One-click backup download button (triggers `mariadb-dump` inside DB container, streams result)
- Enhanced export section with format selector and current filter state
- Migration status display (current revision, pending migrations)
- DB statistics dashboard with real table sizes and index info
- ~20 tests covering service layer, backup endpoint, stats display

**PR D: Simplified CSV Import**
- CSV import for customers and inventory (fixed column order matching export format)
- Upload → preview (first 10 rows) → confirm → import workflow
- Validation with error reporting (row-by-row)
- ~20 tests covering upload, validation, import, error cases

**Database migration**: `d4e5f6a7b8c9` — `system_config` table

**Tests**: 905 total, all passing

### Sprint 2026-03-13 (Complete)

- [x] Quick-create customer modal on order form (8 tests)
- [x] AuditLog model, migration `e5f6a7b8c9d0`, audit_service, admin viewer with filters (26 tests)
- [x] UAT admin tests — 53 Playwright tests + 4 E2E steps for admin overhaul

**Tests**: 939 total, all passing

---

### Sprint 2026-03-15: Waves 1-3 (Complete)

**Wave 1: High Impact** (3 parallel agents)
- [x] **1a: Wire audit logging** — `audit_service.log_action()` wired into all 7 write-path blueprints + order_service + invoice_service. 21 new tests.
- [x] **1b: PDF invoice generation** — `app/utils/pdf.py` with fpdf2, invoice PDF route (`/invoices/<id>/pdf`), price list PDF route (`/price-list/pdf`). 35 new tests.
- [x] **1c: Documentation suite** — `docs/architecture.md` (469 lines), `docs/user_guide.md` (539 lines), `docs/installation.md` (481 lines), `docs/configuration.md` (344 lines).

**Wave 2: Medium Impact** (4 parallel agents)
- [x] **2a: Dashboard activity feed** — live audit log feed on dashboard with HTMX polling (60s), action badges, entity links. 14 new tests.
- [x] **2b: Cloud integration readiness** — `/health/ready` (DB+Redis), `/health/live` endpoints; `docs/cloud_deployment.md` for AWS/GCP/Azure. 11 new tests.
- [x] **2c: Kanban view for orders** — drag-and-drop board with HTML5 DnD API, priority-colored cards, responsive layout. 19 new tests.
- [x] **2d: Camera image capture** — Attachment model + migration `f6a7b8c9d0e1`, camera capture via HTML5 `capture="environment"`, gallery on item/order detail pages. 41 new tests.

**Wave 3: Polish & Tech Debt** (3 parallel agents)
- [x] **3a: Service layer refactoring** — customers, items, inventory, price_list blueprints refactored to use service modules. 84 new tests.
- [x] **3b: FULLTEXT search + streaming exports** — multi-entity global search, HTMX autocomplete dropdown, generator-based streaming CSV. 47 new tests.
- [x] **3c: Import column mapping wizard** — multi-step wizard with column detection, fuzzy auto-mapping, XLSX support, row-level validation. 35 new tests.

**Tests**: 1246 total, all passing

---

### Wave 4A: Infrastructure & Polish (Complete)

- [x] **Beat healthcheck fix** — dsm-beat container healthcheck now works reliably ([PR #29](https://github.com/llathrop/Dive_Service_Management/pull/29))
- [x] **Vendor frontend libs** — Bootstrap, HTMX, Alpine.js, Chart.js served from static files instead of CDN ([PR #30](https://github.com/llathrop/Dive_Service_Management/pull/30))
- [x] **Extended login form** — Flask-Security ExtendedLoginForm wired up ([PR #31](https://github.com/llathrop/Dive_Service_Management/pull/31))
- [x] **Compose override template** — docker-compose.override.yml.example for dev workflow ([PR #32](https://github.com/llathrop/Dive_Service_Management/pull/32))
- [x] **Company branding** — logo upload, company name in header/invoices ([PR #33](https://github.com/llathrop/Dive_Service_Management/pull/33))

### Wave 4B: Features (Complete)

- [x] **Email notifications** — SMTP-based delivery via email_service.py, reads config from SystemConfig at send-time, Celery async delivery, SMTP settings editable from admin UI
- [x] **Saved searches** — per-user, per-type JSON filter storage with CRUD API and reusable Jinja macro; SavedSearch model with migration g7b8c9d0e1f2
- [x] **Broadcast notification UI** — notification list page with broadcast/personal distinction, mark-as-read for broadcast notifications via NotificationRead join table
- [x] **In-app docs viewer** — docs blueprint serving project documentation from the sidebar

### Wave 4C: Technical Debt (Complete)

- [x] **Module splitting** — admin/ package (5 modules: users, settings, data, audit, logs) and orders/ package (7 modules: items, labor, notes, parts, services, status)
- [x] **Admin log viewer** — allowlist-based path traversal prevention, HTMX 5s polling, admin-only access via log_service.py
- [x] **MariaDB parity tests** — test suite validates MariaDB-specific behavior alongside SQLite

### Wave 4D: UX Enhancements (Complete)

- [x] **Inline dropdown creation** — 4 quick-create patterns (customers, inventory items, price list categories, tags) allowing creation without leaving the current form
- [x] **Docker persistent test container** — avoids rebuild overhead, supports rapid test iteration

### Wave 4E: Documentation Updates (Complete)

- [x] PROJECT_BLUEPRINT.md updated (file structure, features, implementation status)
- [x] README.md updated (test count, tech stack, features, blueprint count)
- [x] PROGRESS.md updated (Wave 4A-E entries)
- [x] MEMORY.md verified and corrected

**Tests**: 1418 total, all passing

---

### Sprint 2026-03-18 (Complete)

**Wave A: Quick Fixes & Infrastructure** (parallel)
- [x] **#41: Mobile quick-create fix** — `getOrCreateInstance` for Bootstrap dropdowns, `scrollIntoView` after creation, `touch-action: manipulation` CSS for reliable touch handling
- [x] **#43: Auto DB backup before migrations** — `docker-entrypoint.sh` detects pending Alembic migrations and runs `mariadb-dump` with `--single-transaction` before applying them. Controlled by `DSM_AUTO_BACKUP_ON_UPGRADE` env var. Backups stored in `./backups/` as compressed `.sql.gz` files.

**Wave B: Service Item Customer Requirement** (#42)
- [x] **#42: Service items require customer** — `customer_id` column changed from nullable to `NOT NULL` via migration `h8c9d0e1f2g3`. Smart orphan resolution: migration creates "Default / Unassigned" customer and reassigns orphaned items before adding the constraint. Service history displayed on item detail page. Customer detail page now shows open orders and completed orders separately. Item form includes customer dropdown for reassignment. Item attachments shown on order detail page.

**Wave C: Codebase Audit & Documentation**
- [x] Documentation updates for Sprint 2026-03-18 changes
- [x] PROGRESS.md, MEMORY.md, architecture.md, user_guide.md, configuration.md updated

**GitHub Issues**: #41, #42, #43 — all closed

**Tests**: 1448 total, all passing

### Sprint 2026-03-22 (Complete)

**Wave A: Issue #44 — Unified Gallery**
- [x] **#44: Unified photo gallery** — Service item detail page now shows a "Complete Photo History" combining direct item photos and photos from all service order items. New `get_unified_attachments()` service function, `/attachments/gallery/unified/<id>` endpoint, HTMX-loaded gallery partial grouped by source. 10 new tests (6 unit, 4 blueprint).

**Wave B: Comprehensive Project Review** (4 parallel agents)
- [x] **Code audit** — Found 3 P1 (unwired notification triggers), 12 P2 (unused service functions, inconsistent update patterns), 7 P3 (dead templates/forms, stale comments). No TODOs/FIXMEs remaining. 10 feature proposals generated.
- [x] **Documentation audit** — 27 findings (6 P1, 9 P2, 12 P3). Stale model counts, outdated health check descriptions, email system misclaimed as inactive, missing screenshots.
- [x] **Test suite review** — ~37 duplicate tests identified across 4 service test files. 42 files missing pytest markers. No blueprint or model test overlap despite dual directories. conftest duplication with MariaDB.
- [x] **Security audit** — 0 P0, 7 P1 (missing CSRF on 2 forms, no security headers, export/reports lack role restrictions, no rate limiting), 8 P2, 8 P3. No SQL injection, XSS, or critical vulnerabilities found.

**Wave C: TODO Consolidation**
- [x] Consolidated 48 actionable items from all 4 audits into `docs/review/consolidated_todos.md` (P1: 11, P2: 20, P3: 17)

**GitHub Issues**: #44 — closed
**Tests**: 1458 total, all passing

### Sprint 2026-03-22B (Wave 1-4 Complete, Wave 5 In Progress)

**Scope**: All 48 audit fix items (P1: 11, P2: 20, P3: 17) + all 13 feature proposals from consolidated TODO list. Waves 1-4 are landed and pushed on `master`; Wave 5 is now the active execution stage.

**Wave 1: P1 Fixes + Quick-Win Features** (Complete)
- [x] Security headers, secure session cookies, and rate limiting added
- [x] Export and report routes restricted to `admin`/`technician`
- [x] CSRF tokens added to admin import forms
- [x] Notification triggers wired into order, inventory, and invoice services
- [x] Audit log CSV export added; password recovery enabled; stale docs corrected
- [x] Stale docstrings fixed and part-linking UI added to price list items

**Wave 2: P2/P3 Fixes + Medium Features** (Complete)
- [x] Redis auth, localhost binding, path traversal guard, backup audit logging, and table allowlist hardening
- [x] Customer, inventory, and price list edit routes now go through service-layer update functions; password policy comes from `SystemConfig`
- [x] Dead code removed, duplicate tests deduplicated, and pytest markers added
- [x] Hide completed orders toggle, order-to-invoice workflow, and auto `last_service_date`
- [x] Stale docs fixed, `SORTABLE_FIELDS` deduplicated, and security settings verified
- [x] Saved search defaults, dashboard customization, CSRF on dashboard fetch, and corrupted JSON guard
- [x] Validation fixes for auto-generated invoices and notification wiring

**Wave 3: Medium Features** (4 parallel agents)
- [x] 3A: Batch operations on list views
- [x] 3B: Service order templates
- [x] 3C: Recurring service reminders
- [x] 3D: Shipping calculator with pluggable provider framework

**2026-03-24 Wave 3 Recovery Update**
- Recovered interrupted `3D` shipping work into dedicated worktree `.claude/worktrees/agent-wave3d-shipping`, completed lead review plus QA/security fixes, then cherry-picked onto `master`
- Verified `3D` in the persistent Docker test container (`docker-compose.test-dev.yml`)
- `tests/test_services/test_shipping.py`: 29 passed
- `tests/blueprint/test_order_routes.py`: 43 passed
- Completed `3C` recurring reminders after QA/security fixes, including inactive-admin filtering, delivery dedupe tracking, and `last_service_date` updates on completion
- Verified `3C` on `master` in the persistent Docker test container
- `tests/test_services/test_reminder_tasks.py` + `tests/unit/models/test_notification.py` + `tests/unit/services/test_order_service.py`: passed
- Completed `3A` batch operations after QA/security fixes for non-admin list rendering, reachable UI actions, and audit-log consistency
- Verified `3A` on `master` in the persistent Docker test container
- `tests/test_blueprints/test_batch_operations.py` + `tests/blueprint/test_customer_routes.py` + `tests/blueprint/test_inventory_routes.py`: passed
- Completed `3B` service order templates after QA/security fixes for owner-only writes, safe form parsing, create-order prefill behavior, and shared-template UI visibility
- Verified `3B` on `master` in the persistent Docker test container
- `tests/test_blueprints/test_order_templates.py` + `tests/blueprint/test_order_routes.py`: passed
- Post-wave regression gate passed in the persistent Docker test container
- `pytest tests/ -q --tb=short`: passed

**Wave 4: Customer Portal** (4 parallel agents)
- [x] 4A: PortalUser model + auth system (separate from Flask-Security)
- [x] 4B: Portal dashboard + order tracking
- [x] 4C: Portal invoice view + payment provider framework
- [x] 4D: Portal equipment view + admin invite management + email notifications

**2026-03-24 Wave 4 Kickoff**
- Reconciled planning docs on `master` so `PROGRESS.md`, `README.plan`, and `consolidated_todos.md` all point at Wave 4 as the active next stage
- Created dedicated Wave 4A auth worktree `.claude/worktrees/agent-wave4a-portal-auth`
- Launched parallel agent work for:
  - 4A auth foundation implementation
  - 4B order/dashboard integration discovery
  - 4C invoice/payment integration discovery
  - 4D equipment/invite/email integration discovery
- 4C invoice/payment implementation is now active in `.claude/worktrees/agent-wave4c-portal-invoices` on `feature/customer-portal-invoices`; it will ship as its own remote branch and PR before merge
- Pulled remote GitHub backlog into planning: open issue [#46](https://github.com/llathrop/Dive_Service_Management/issues/46) extends the Wave 3 shipping foundation into real-time carrier integrations and is tracked as a follow-on after Wave 4 unless portal/invoice work forces earlier extraction
- Process correction: every new feature, fix, or docs lane now requires an isolated worktree, a remote feature branch, and a GitHub PR before merge to `master`
- Historical exception: the Wave 3 recovery and Wave 4 kickoff commits on `master` (`3bfd7ae` through `a6db2de`) were pushed without PRs and cannot be turned into true reviewable PRs retroactively without rewriting published history

**2026-03-25 Wave 4A Update**
- Completed Wave 4A portal auth foundation in dedicated worktree, reviewed it with dedicated QA/security agents, and merged it via [PR #48](https://github.com/llathrop/Dive_Service_Management/pull/48)
- Verified Wave 4A after review in the persistent Docker test container
- `tests/unit/models/test_portal_user.py` + `tests/blueprint/test_portal_auth.py` + `tests/blueprint/test_auth_routes.py` + `tests/unit/test_user_model.py`: passed
- Created fresh implementation worktrees from merged `master` for 4B portal orders/dashboard, 4C portal invoices/payments, and 4D portal equipment/invites, then launched new worker lanes for those slices

**2026-03-25 Wave 4B Update**
- Completed the portal dashboard + order tracking slice in `.claude/worktrees/agent-wave4b-portal-orders`
- Reviewed QA findings for customer/item scoping and `ready_for_pickup` visibility, patched them on the feature branch, and merged via [PR #50](https://github.com/llathrop/Dive_Service_Management/pull/50)
- Verified the portal order slice in the persistent Docker test container with `tests/unit/services/test_portal_service.py` + `tests/blueprint/test_portal.py` + `tests/blueprint/test_portal_auth.py`

**2026-03-25 Wave 4C Update**
- Completed the portal invoice/payment slice in `.claude/worktrees/agent-wave4c-portal-invoices`
- Reviewed the draft-invoice exposure issue, patched it on the feature branch, resolved a portal blueprint merge-conflict blocker, and merged via [PR #52](https://github.com/llathrop/Dive_Service_Management/pull/52)
- Verified the portal invoice slice in the persistent Docker test container with `tests/blueprint/test_portal_invoices.py` + `tests/unit/services/test_portal_invoice_service.py` + `tests/unit/services/test_payment_provider_service.py` + `tests/test_utils/test_pdf.py`

**2026-03-25 Wave 4D Update**
- Completed the portal equipment/invite slice in `.claude/worktrees/agent-wave4d-portal-equipment-invites`
- Repaired the stale branch merge state, tightened portal equipment media to image attachments only after security review, and merged the lane via [PR #51](https://github.com/llathrop/Dive_Service_Management/pull/51)
- Verified the portal equipment/invite slice in the persistent Docker test container with `tests/unit/services/test_portal_service.py` + `tests/blueprint/test_portal_equipment.py` + `tests/blueprint/test_customer_portal_invites.py` + `tests/blueprint/test_portal_auth.py` + `tests/blueprint/test_portal.py` + `tests/blueprint/test_portal_invoices.py` + `tests/test_utils/test_pdf.py`

**2026-03-25 Wave 5 Kickoff**
- Pulled remote GitHub backlog before the final wave: issue [#46](https://github.com/llathrop/Dive_Service_Management/issues/46) was the only open issue and was promoted into the active pre-Wave-5 closure lane
- Confirmed all Wave 4 feature lanes were shipped via remote PRs: [#48](https://github.com/llathrop/Dive_Service_Management/pull/48), [#50](https://github.com/llathrop/Dive_Service_Management/pull/50), [#52](https://github.com/llathrop/Dive_Service_Management/pull/52), and [#51](https://github.com/llathrop/Dive_Service_Management/pull/51)
- Confirmed the only remaining open PR on GitHub at kickoff was unrelated portal/gallery work [#45](https://github.com/llathrop/Dive_Service_Management/pull/45); it was closed as stale before final-wave execution resumed
- Started final-wave planning/doc reconciliation on a dedicated docs branch so `PROGRESS.md`, `README.plan`, and shared memory all reflect the post-Wave-4 state
- Merged follow-up [PR #56](https://github.com/llathrop/Dive_Service_Management/pull/56) after QA flagged that the new equipment portal surface was not discoverable from the shared nav or order detail view

**2026-03-25 Shipping Backlog Closure**
- Completed the follow-on shipping carrier expansion from remote issue [#46](https://github.com/llathrop/Dive_Service_Management/issues/46) in a dedicated worktree/branch, reviewed it with QA and security agents, and merged it via [PR #59](https://github.com/llathrop/Dive_Service_Management/pull/59)
- Expanded the shipping framework to support provider registry selection (USPS, UPS, FedEx, DHL, Local Pickup, Flat Rate), destination-aware quotes, enabled-provider enforcement, and a standalone tools calculator
- Verified the shipping expansion in the persistent Docker test container with `tests/test_services/test_shipping.py` + `tests/blueprint/test_tools_routes.py`
- Synced `master` to `origin/master` after the merge; remote GitHub backlog is now clear with zero open issues and zero open PRs
- Cleaned merged feature branches and stale worktree directories so Wave 5 can start from a single clean `master` worktree

**Wave 5: Final Polish** (3 agents)
- [x] 5A: Capture missing screenshots
- [ ] 5B: Sprint documentation finalization
- [x] 5C: Integration smoke tests

**5C completion note**
- Added an authenticated smoke route lane for the core internal surfaces and a single Dockerized handoff gate via `make test-gate`
