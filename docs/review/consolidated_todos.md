# Consolidated TODO List — Sprint 2026-03-22

Prioritized findings from 4 parallel audits: code, documentation, test suite, and security.
Use this as input for planning the next sprint.

Remote backlog intake note: GitHub open issue [#46](https://github.com/llathrop/Dive_Service_Management/issues/46) adds a follow-on shipping-provider expansion (real-time carrier integrations) that is not part of the original four audits. It should be planned separately from the remaining audit items below.

---

## P1 — High Priority (Fix Before Next Release)

### Security
- [ ] **Missing CSRF tokens on admin import forms** — `admin/import_preview.html:91` and `admin/import_form.html:36` POST without CSRF protection. (security_todos)
- [ ] **No security response headers** — Missing X-Frame-Options, CSP, HSTS, Referrer-Policy on all responses. Add `@app.after_request` handler. (security_todos)
- [ ] **Export routes lack role restrictions** — All 4 routes in `export.py` only require `@login_required`. Any authenticated viewer can export all data. Add `@roles_accepted("admin", "technician")`. (security_todos)
- [ ] **Report routes lack role restrictions** — All 5 routes in `reports.py` only require `@login_required`. Revenue reports expose financial data to viewers. Add `@roles_accepted("admin", "technician")`. (security_todos)
- [ ] **No session cookie SECURE flag** — `ProductionConfig` doesn't set `SESSION_COOKIE_SECURE = True`. Cookies sent over HTTP. (security_todos)
- [ ] **No rate limiting** — Login, password reset, API endpoints vulnerable to brute-force. Add `flask-limiter`. (security_todos)

### Code — Unwired Features
- [ ] **Notification triggers never called** — `notify_low_stock()`, `notify_order_status_change()`, `notify_payment_received()` are implemented and tested but never invoked from services. The notification system is inert. Wire 3-6 lines of glue code. (code_audit)

### Documentation
- [ ] **architecture.md model count wrong** — Says 17 models, should be 26. Missing Attachment and SavedSearch from table entirely. ER diagram also missing them. (docs_todos)
- [ ] **configuration.md says email "not yet active"** — Email is fully implemented since Wave 4B. Stale claim misleads users. (docs_todos)
- [ ] **installation.md migration count wrong** — Says 7 migrations, should be 11. (docs_todos)
- [ ] **PROGRESS.md "In Progress" label wrong** — Third Review section still says "(In Progress)" but is complete. (docs_todos)

---

## P2 — Medium Priority (Fix Soon)

### Security
- [ ] **SQL injection risk in SQLite table stats** — `data_management_service.py:58` uses f-string for table names. Low risk (names from DB, not user input) but code smell. (security_todos)
- [ ] **Redis has no authentication** — Docker Redis runs without `requirepass`. Any process on Docker network can access. (security_todos)
- [ ] **Backup downloads not audit-logged** — `admin.download_backup` returns full SQL dump with no audit trail. (security_todos)
- [ ] **Password policy minimal** — Only checks `len(password) < 8`. SystemConfig has `security.password_min_length` but it's not wired into user creation. (security_todos)
- [ ] **SMTP password storage** — Verify email SMTP password stored with `is_sensitive=True` in SystemConfig. (security_todos)
- [ ] **Upload route path concern** — `<path:filename>` in `__init__.py:184`. `send_from_directory` has protection but defense-in-depth suggested. (security_todos)
- [ ] **Default bind 0.0.0.0** — Exposes app on all interfaces. Consider defaulting to 127.0.0.1. (security_todos)

### Code
- [ ] **8 unused service functions** — `update_customer()`, `search_customers()`, `update_inventory_item()`, `get_low_stock_items()`, `update_category()`, `update_price_list_item()`, `link_part()`, `unlink_part()` are never called from blueprints. Either wire them in or remove. (code_audit)
- [ ] **Blueprints bypass service layer for updates** — customers, inventory, price_list edit routes use `form.populate_obj()` directly instead of service functions. Skips service-layer validation. (code_audit)
- [ ] **Price list part linking has no UI** — `link_part()`/`unlink_part()` exist but no form or modal to manage part associations. (code_audit)
- [ ] **Saved search defaults never applied** — `get_default_search()` exists but never called on list page load. (code_audit)
- [ ] **Stale model docstrings** — `ServiceItem` says customer is "optional" (now required). `Customer` claims TaggableMixin (not inherited). (code_audit)

### Documentation
- [ ] **Health check descriptions stale** — 3 docs files describe outdated health check commands that don't match docker-compose.yml. (docs_todos)
- [ ] **architecture.md service layer table missing 7 modules** — attachment, email, item, log, saved_search, inventory (scope changed). (docs_todos)
- [ ] **architecture.md stale service layer note** — Says Phase 2 blueprints access models directly; they were refactored in Wave 3a. (docs_todos)
- [ ] **user_guide.md tab count wrong** — Says "six tabs" but lists 7. (docs_todos)
- [ ] **configuration.md health check commands stale** — Web, worker, beat health checks don't match actual docker-compose.yml. (docs_todos)

### Tests
- [ ] **4 duplicate service test files** — `tests/unit/services/` has near-duplicate tests for customer (10), inventory (10), price_list (11), search (6) that are supersets in `tests/test_services/`. Remove ~37 tests. (test_todos)
- [ ] **conftest.py duplication** — MariaDB conftest duplicates 4 fixtures from main conftest. Extract shared helper. (test_todos)
- [ ] **Directory naming inconsistency** — `tests/blueprint/` lacks `test_` prefix that all other dirs use. Rename or merge. (test_todos)

---

## P3 — Low Priority (Improve When Convenient)

### Security
- [ ] **`|safe` on Markdown rendering** — `docs/detail.html:39` renders server-side .md files without sanitization. Low risk (not user input) but add `bleach`/`nh3` for defense-in-depth. (security_todos)
- [ ] **Container runs as `dsm` user** — Good practice but verify no privilege escalation paths. (security_todos)
- [ ] **DEBUG=false enforcement** — Verify `ProductionConfig` disallows debug mode. (security_todos)

### Code
- [ ] **Dead templates** — `auth/login.html` (duplicate of Flask-Security's), `search/_autocomplete.html` (legacy wrapper). (code_audit)
- [ ] **Dead form** — `GlobalSearchForm` defined but never used. (code_audit)
- [ ] **Redundant import** — `items.py:259` re-imports `Customer` already at module level. (code_audit)
- [ ] **Stale comments in extensions.py/config.py** — Say email is "placeholder"/"future" but it's implemented. (code_audit)
- [ ] **SORTABLE_FIELDS duplicated** — Between service and blueprint files for invoices and orders. (code_audit)
- [ ] **`blueprints/__init__.py` missing entries** — Missing admin_bp, docs_bp, attachments_bp exports. (code_audit)

### Documentation
- [ ] **Missing screenshots** — `customer_detail.png` and `item_detail_service_history.png` referenced in user_guide.md but don't exist. (docs_todos)
- [ ] **Docker volume table missing backups mount** — architecture.md and system overview diagram. (docs_todos)
- [ ] **cloud_deployment.md Azure MariaDB retired** — Microsoft retired Azure Database for MariaDB. (docs_todos)
- [ ] **cloud_deployment.md GCP MariaDB confusion** — Contradicts installation.md about Cloud SQL MariaDB support. (docs_todos)
- [ ] **Missing email SystemConfig keys in docs** — configuration.md doesn't document SMTP config keys. (docs_todos)
- [ ] **PROJECT_BLUEPRINT.md aspirational deps** — WeasyPrint, Marshmallow, Huey, Tom Select listed but not in requirements.txt. (docs_todos)
- [ ] **installation.md seed data count** — Verify "29 system config entries" is still accurate. (docs_todos)

### Tests
- [ ] **42 files missing pytest markers** — 27 in test_blueprints/, 14 in test_services/, 3 in test_models/. (test_todos)
- [ ] **Directory consolidation** — Move test_models/ into unit/models/, test_utils/ into unit/utils/. (test_todos)
- [ ] **Empty directory** — `tests/unit/utils/` has only `__init__.py`. (test_todos)
- [ ] **Single-test file** — `test_invoice_customer_dropdown.py` has 1 test. Fold into parent. (test_todos)

---

## Feature Proposals (Discussion — Not Prioritized)

Status note: items 1, 4, 5, 6, 7, 8, 9, and 10 below have already been implemented across Sprint `2026-03-22B` Waves 1-3. The primary remaining proposal in this section is the customer portal work (`3`), which is now the active next wave in `PROGRESS.md`.

1. **Wire notification triggers** — 3-6 lines of glue to call existing notify functions from inventory/order/invoice services. Immediate value.
2. **Part linking UI** — Modal on price list detail to associate inventory parts. Enables auto-deduction.
3. **Customer portal** — Public status lookup by order number. Eliminates "is my suit done?" calls.
4. **Recurring service reminders** — Track last-service-date, send reminders at annual intervals.
5. **Batch operations on list views** — Checkbox + bulk actions (mark orders ready, deactivate items).
6. **Service order templates** — Save common service configs as reusable presets.
7. **Dashboard customization** — Per-user card selection and ordering.
8. **Auto-populate last_service_date** — Set when order transitions to "completed".
9. **Audit log export** — CSV/XLSX export for compliance.
10. **Password recovery via email** — Enable Flask-Security's recovery flow (email now works).
11. **Real-time carrier shipping framework** — Tracked separately as GitHub issue [#46](https://github.com/llathrop/Dive_Service_Management/issues/46); extends the current flat-rate/pluggable shipping base with carrier APIs.

---

## Summary

| Priority | Count | Source Breakdown |
|----------|-------|-----------------|
| P1 | 11 | Security: 6, Code: 1, Docs: 4 |
| P2 | 20 | Security: 7, Code: 5, Docs: 5, Tests: 3 |
| P3 | 17 | Security: 3, Code: 6, Docs: 7, Tests: 4 |
| **Total** | **48** | |

**Estimated effort for P1 items**: 1 sprint (most are small, targeted fixes)
**Test impact**: Removing ~37 duplicate tests brings count from 1,458 to ~1,421
