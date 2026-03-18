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

### Post-Phase 6: Third Review Fix-ups — CODEX Re-Review (In Progress)

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
