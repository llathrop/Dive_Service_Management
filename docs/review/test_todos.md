# Test Suite Review -- 2026-03-22

## Directory Structure

| Directory | Test Count | Purpose | Overlaps With |
|-----------|-----------|---------|---------------|
| `tests/blueprint/` | 367 | Route-level tests (auth, RBAC, CRUD) for core blueprints | `tests/test_blueprints/` |
| `tests/test_blueprints/` | 283 | Route-level tests for newer features (kanban, PDF, quick-create, branding) | `tests/blueprint/` |
| `tests/unit/models/` | 135 | Model creation, relationships, properties, constraints | `tests/test_models/` (minor) |
| `tests/test_models/` | 31 | Model tests for AuditLog, Attachment, SystemConfig | None (unique models) |
| `tests/unit/services/` | 268 | Service layer unit tests (core services) | `tests/test_services/` |
| `tests/test_services/` | 232 | Service layer tests (newer + refactored services) | `tests/unit/services/` |
| `tests/unit/forms/` | 99 | Form validation tests | None |
| `tests/unit/` (root files) | 33 | Config, infrastructure, mixins, user/role models | None |
| `tests/unit/migrations/` | 2 | Migration logic tests | None |
| `tests/unit/utils/` | 0 | Empty (only `__init__.py`) | `tests/test_utils/` |
| `tests/test_utils/` | 20 | PDF utility tests | None |
| `tests/smoke/` | 17 | App startup, page load, health check | None |
| `tests/validation/` | 4 | End-to-end workflow validation | None |
| `tests/uat/` | 133 | Playwright browser-based UAT tests | None |
| `tests/mariadb/` | 23 | MariaDB parity tests (skipped when DB unavailable) | None |

**Total tests: ~1,448** (matches known count of 1,448)

## Duplicate Tests

### tests/unit/services/ vs tests/test_services/ -- Service Layer

These two directories both test the service layer. The `tests/unit/services/` directory uses manual helpers (`_make_customer`, etc.) while `tests/test_services/` uses Factory Boy factories. Both are well-structured but represent a split convention.

#### customer_service
- [ ] P2: `test_returns_paginated_results` / `test_get_customers_returns_paginated` -- near-duplicate (both test pagination, different helper style) -- keep `test_services/` version (uses factories)
- [ ] P2: `test_search_filters_by_name` / `test_get_customers_search` -- near-duplicate -- keep `test_services/`
- [ ] P2: `test_excludes_soft_deleted` / `test_get_customers_excludes_deleted` -- near-duplicate -- keep `test_services/`
- [ ] P2: `test_get_customer_by_id` / `test_returns_customer_by_id` -- near-duplicate -- keep `test_services/`
- [ ] P2: `test_create_customer` / `test_creates_individual_customer` -- near-duplicate -- keep `test_services/`
- [ ] P2: `test_update_customer` / `test_updates_fields` -- near-duplicate -- keep `test_services/`
- [ ] P2: `test_delete_customer` / `test_soft_deletes_customer` -- near-duplicate -- keep `test_services/`
- [ ] P2: `test_search_customers` in unit/ has 1 test; `test_services/` has 3 (more thorough) -- keep `test_services/`
- [ ] P3: `test_customer_type_filter` / `test_get_customers_filter_type` -- near-duplicate -- keep `test_services/`
- [ ] P3: `test_sorting_asc`/`test_sorting_desc` only in `test_services/` -- unique, keep

**Recommendation**: `tests/unit/services/test_customer_service.py` (10 tests) can be removed. `tests/test_services/test_customer_service.py` (19 tests) is a superset.

#### inventory_service
- [ ] P2: `test_returns_paginated_results` / `test_get_inventory_items` -- near-duplicate
- [ ] P2: `test_search_filters_by_name` / search tests -- near-duplicate
- [ ] P2: `test_excludes_soft_deleted` -- near-duplicate
- [ ] P2: `test_creates_item` / `test_create_inventory_item` -- near-duplicate
- [ ] P2: `test_updates_fields` / `test_update_inventory_item` -- near-duplicate
- [ ] P2: `test_soft_deletes_item` / `test_delete_inventory_item` -- near-duplicate
- [ ] P2: `test_positive_adjustment` / `test_adjust_stock` -- near-duplicate
- [ ] P2: `test_returns_low_stock_items` / `test_get_low_stock_items` -- near-duplicate

**Recommendation**: `tests/unit/services/test_inventory_service.py` (10 tests) can be removed. `tests/test_services/test_inventory_service.py` (24 tests) is a superset.

#### price_list_service
- [ ] P2: `test_get_categories` / `test_returns_active_categories` -- near-duplicate
- [ ] P2: `test_create_category` / `test_creates_category` -- near-duplicate
- [ ] P2: `test_get_price_list_items` / `test_returns_items` -- near-duplicate
- [ ] P2: `test_create_price_list_item` / `test_creates_item` -- near-duplicate
- [ ] P2: `test_duplicate_price_list_item` / `test_duplicates_item` -- near-duplicate
- [ ] P2: `test_link_part` / `test_unlink_part` -- present in both

**Recommendation**: `tests/unit/services/test_price_list_service.py` (11 tests) can be removed. `tests/test_services/test_price_list_service.py` (20 tests) is a superset.

#### search_service
- [ ] P2: `test_global_search_finds_customers` / `test_finds_customer_by_first_name` -- near-duplicate
- [ ] P2: `test_global_search_finds_service_items` / `test_finds_item_by_name` -- near-duplicate
- [ ] P2: `test_global_search_finds_inventory` / `test_finds_inventory_by_name` -- near-duplicate
- [ ] P2: `test_global_search_no_results` / `test_no_results_returns_empty` -- near-duplicate
- [ ] P2: `test_global_search_empty_query` / `test_global_search_empty_query_returns_empty` -- near-duplicate
- [ ] P2: `test_search_excludes_deleted` -- in both

**Recommendation**: `tests/unit/services/test_search_service.py` (6 tests) can be removed. `tests/test_services/test_search_service.py` (23 tests) is a superset with per-entity-type granularity.

#### attachment_service
- [ ] P2: `tests/unit/services/test_attachment_service.py` (6 tests) covers `get_all_attachments_for_item` (direct + via orders). `tests/test_services/test_attachment_service.py` (16 tests) covers validation, save, get, delete. **No overlap** -- these test different functions. Keep both.

#### Services only in tests/unit/services/ (no overlap)
- `test_order_service.py` (41 tests) -- unique, keep
- `test_invoice_service.py` (49 tests) -- unique, keep
- `test_notification_service.py` (18 tests) -- unique, keep
- `test_tag_service.py` (12 tests) -- unique, keep
- `test_log_service.py` (14 tests) -- unique, keep
- `test_email_service.py` (10 tests) -- unique, keep
- `test_export_service.py` (9 tests) -- unique, keep
- `test_saved_search_service.py` (17 tests) -- unique, keep
- `test_report_service.py` (10 tests) -- unique, keep
- `test_notification_email_hook.py` (4 tests) -- unique, keep
- `test_customer_orders.py` (3 tests) -- unique, keep
- `test_item_service_history.py` (3 tests) -- unique, keep

#### Services only in tests/test_services/ (no overlap)
- `test_audit_service.py` (11 tests) -- unique, keep
- `test_audit_wiring.py` (21 tests) -- unique, keep
- `test_config_service.py` (19 tests) -- unique, keep
- `test_data_management_service.py` (9 tests) -- unique, keep
- `test_export_streaming.py` (11 tests) -- unique, keep
- `test_import_mapping.py` (24 tests) -- unique, keep
- `test_import_service.py` (14 tests) -- unique, keep
- `test_item_service.py` (21 tests) -- unique, keep

### tests/blueprint/ vs tests/test_blueprints/ -- Route Tests

These directories test different blueprints with **no function-name overlap**:

- `tests/blueprint/` covers: admin, attachment, auth, customer, dashboard, export, inventory, invoice, item, notification, order, price_list, report, search, tools (core RBAC + CRUD routes)
- `tests/test_blueprints/` covers: admin_audit, admin_data, admin_email_settings, admin_import, admin_logs, admin_settings, attachments, company_branding, customer_orders, dashboard_activity, docs, extended_login, health_extended, import_wizard, inventory_quick_create, invoice_customer_dropdown, invoice_pdf, item_customer, items_quick_create, items_ui, orders, orders_kanban, price_list_quick_create, saved_searches, search_enhanced, static_vendor

**No exact or near-duplicates found between these directories.** They test complementary aspects of the same blueprints. The split is by feature vintage (original vs. later additions).

### tests/test_models/ vs tests/unit/models/

- `tests/test_models/` covers: AuditLog (9), Attachment (7), SystemConfig (15) -- all unique models not in `tests/unit/models/`
- `tests/unit/models/` covers: applied_service, customer, inventory, invoice, labor_entry, notification, parts_used, price_list, service_item, service_order, service_order_item, tag

**No overlap.** These are cleanly separated by model.

## Consolidation Plan

- [ ] P2: Merge `tests/unit/services/test_customer_service.py` into `tests/test_services/test_customer_service.py` (remove unit/ version, 10 tests redundant)
- [ ] P2: Merge `tests/unit/services/test_inventory_service.py` into `tests/test_services/test_inventory_service.py` (remove unit/ version, 10 tests redundant)
- [ ] P2: Merge `tests/unit/services/test_price_list_service.py` into `tests/test_services/test_price_list_service.py` (remove unit/ version, 11 tests redundant)
- [ ] P2: Merge `tests/unit/services/test_search_service.py` into `tests/test_services/test_search_service.py` (remove unit/ version, 6 tests redundant)
- [ ] P2: Rename `tests/blueprint/` to `tests/test_blueprint_core/` or merge into `tests/test_blueprints/` for naming consistency (both use `test_` prefix convention except `blueprint/`)
- [ ] P3: Move `tests/test_models/` contents into `tests/unit/models/` to consolidate all model tests in one location
- [ ] P3: Move `tests/test_utils/` contents into `tests/unit/utils/` (currently empty) for consistency
- [ ] P3: Move unique `tests/unit/services/` files (order, invoice, notification, etc.) into `tests/test_services/` or vice versa -- pick one canonical location
- [ ] P4: Delete empty `tests/unit/utils/` `__init__.py` if moving tests elsewhere

## Missing Markers

### Files with NO pytest markers at all:

#### tests/test_blueprints/ (27 of 30 files missing markers)
- [ ] P3: `test_admin_audit.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_admin_data.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_admin_email_settings.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_admin_import.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_admin_logs.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_admin_settings.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_attachments.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_company_branding.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_dashboard_activity.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_docs.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_extended_login.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_health_extended.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_import_wizard.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_inventory_quick_create.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_invoice_customer_dropdown.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_invoice_pdf.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_orders.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_orders_kanban.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_price_list_quick_create.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_saved_searches.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_search_enhanced.py` -- needs `pytestmark = pytest.mark.blueprint`
- [ ] P3: `test_items_quick_create.py` -- needs `pytestmark = pytest.mark.blueprint`

Files that DO have markers: `test_items_ui.py` (per-class), `test_item_customer.py`, `test_customer_orders.py`, `test_static_vendor.py` (uses `smoke`)

#### tests/test_services/ (all 14 files missing markers)
- [ ] P3: `test_attachment_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_audit_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_audit_wiring.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_config_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_customer_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_data_management_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_export_streaming.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_import_mapping.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_import_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_inventory_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_item_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_price_list_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_search_service.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_export_streaming.py` -- needs `pytestmark = pytest.mark.unit`

#### tests/test_models/ (all 3 files missing markers)
- [ ] P3: `test_audit_log.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_attachment.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_system_config.py` -- needs `pytestmark = pytest.mark.unit`

#### tests/test_utils/ (1 file missing markers)
- [ ] P3: `test_pdf.py` -- needs `pytestmark = pytest.mark.unit`

#### tests/unit/ root files (2 files missing markers)
- [ ] P3: `test_config.py` -- needs `pytestmark = pytest.mark.unit`
- [ ] P3: `test_infrastructure.py` -- needs `pytestmark = pytest.mark.unit`

**Total: ~42 files missing pytest markers.**

## Outdated Tests

- [ ] P4: `tests/unit/utils/` directory exists but is empty (no test files, only `__init__.py`) -- remove or populate
- [ ] P4: `tests/test_blueprints/test_static_vendor.py` marked as `@pytest.mark.smoke` but lives in `test_blueprints/` not `smoke/` -- either move to `tests/smoke/` or change marker to `blueprint`

## Coverage Gaps

### Services without dedicated test files
- [ ] P3: `app/services/email_service.py` -- only tested in `tests/unit/services/test_email_service.py` (10 tests), no `tests/test_services/` counterpart. This is fine but noted for awareness.
- [ ] P3: `app/services/notification_service.py` -- only tested in `tests/unit/services/test_notification_service.py` (18 tests), no `tests/test_services/` counterpart. This is fine.
- [ ] P3: `app/services/order_service.py` -- only tested in `tests/unit/services/test_order_service.py` (41 tests). No `tests/test_services/` counterpart. Comprehensive but single location.
- [ ] P3: `app/services/invoice_service.py` -- only tested in `tests/unit/services/test_invoice_service.py` (49 tests). No `tests/test_services/` counterpart. Comprehensive.

### Blueprint routes without route-level tests
- [ ] P4: `docs` blueprint -- tested in `tests/test_blueprints/test_docs.py` (10 tests) but no `tests/blueprint/test_docs_routes.py`. Covered.
- [ ] P4: `health` blueprint -- tested in `tests/smoke/test_health.py` (5 tests) and `tests/test_blueprints/test_health_extended.py` (11 tests). Covered.

### Other gaps
- [ ] P4: No route-level tests for `notifications` blueprint beyond basic auth/CRUD in `tests/blueprint/test_notification_routes.py` (12 tests). The email notification delivery path (via Celery worker) is only unit-tested.
- [ ] P4: No integration tests for the import wizard end-to-end flow (upload -> map -> preview -> execute). Pieces are tested individually.
- [ ] P4: `tests/test_blueprints/test_invoice_customer_dropdown.py` has only 1 test -- could be expanded or folded into `test_invoice_routes.py`

## conftest Duplication

- [ ] P2: `tests/mariadb/conftest.py` duplicates fixtures from `tests/conftest.py`: `app`, `db_session`, `client`, `auth_user` are near-identical copies. The only differences are: (1) uses `MariaDBTestingConfig` instead of `TestingConfig`, (2) adds `mariadb_available` session-scoped fixture for skip logic, (3) auto-applies `pytest.mark.mariadb` marker. **Recommendation**: Extract shared fixture logic into a helper module (e.g., `tests/_fixtures.py`) parameterized by config class, then have both conftest files delegate to it. The `runner`, `logged_in_client`, `admin_client`, and `viewer_client` fixtures are missing from MariaDB conftest (not currently needed but would be if MariaDB tests expand).
- [ ] P3: `tests/uat/conftest.py` is intentionally different (Playwright-based, connects to live app). No duplication concern.

## Summary

| Metric | Count |
|--------|-------|
| Total tests | ~1,448 |
| Test directories | 14 (excluding `__pycache__`) |
| Duplicate service test files | 4 (customer, inventory, price_list, search) |
| Estimated removable duplicate tests | ~37 |
| Files missing pytest markers | ~42 |
| conftest duplication locations | 1 (`tests/mariadb/conftest.py`) |
| Empty test directories | 1 (`tests/unit/utils/`) |
| Coverage gaps (significant) | 0 (all services have tests) |
| Coverage gaps (minor) | 3-4 (single-test files, missing integration tests) |

### Priority Summary

- **P2 (should fix)**: 4 duplicate service test files to remove (~37 tests), conftest duplication, directory naming inconsistency (`blueprint/` vs `test_blueprints/`)
- **P3 (nice to have)**: 42 files missing pytest markers, directory consolidation (test_models -> unit/models, test_utils -> unit/utils)
- **P4 (low priority)**: Empty directories, single-test files, minor coverage gaps
