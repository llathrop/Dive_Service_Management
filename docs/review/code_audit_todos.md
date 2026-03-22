# Code Audit -- 2026-03-22

Comprehensive code audit of the Dive Service Management codebase covering dead code,
stale comments, incomplete features, route/template verification, and feature proposals.

---

## Dead Code

### Unused Service Functions (called only from tests, never from app code)

- [ ] P2: `app/services/customer_service.py:123` -- `update_customer()` is never called from any blueprint. The customers blueprint uses `form.populate_obj(customer)` + `db.session.commit()` directly instead of calling through the service layer.
- [ ] P2: `app/services/customer_service.py:202` -- `search_customers()` is never called from app code. The search blueprint uses `search_service.search_customers()` (a separate function in `search_service.py`), making this a dead duplicate.
- [ ] P2: `app/services/inventory_service.py:136` -- `update_inventory_item()` is never called from any blueprint. The inventory blueprint uses `form.populate_obj(item)` + `db.session.commit()` directly.
- [ ] P2: `app/services/inventory_service.py:234` -- `get_low_stock_items()` is never called from any blueprint. The dashboard uses a direct SQLAlchemy query, and the inventory blueprint uses `get_inventory_items(low_stock_only=True)`.
- [ ] P2: `app/services/price_list_service.py:76` -- `update_category()` is never called from any blueprint. The price list blueprint uses `form.populate_obj(category)` + `db.session.commit()` directly.
- [ ] P2: `app/services/price_list_service.py:188` -- `update_price_list_item()` is never called from any blueprint. Same pattern -- uses `form.populate_obj()` directly.
- [ ] P2: `app/services/price_list_service.py:275` -- `link_part()` is never called from any blueprint or other service. Only tested.
- [ ] P2: `app/services/price_list_service.py:298` -- `unlink_part()` is never called from any blueprint or other service. Only tested.
- [ ] P3: `app/services/saved_search_service.py:35` -- `get_default_search()` is never called from any blueprint. Only used internally and in tests.

### Unwired Notification Triggers

- [ ] P1: `app/services/notification_service.py:337` -- `notify_low_stock()` is defined and tested but never called from `inventory_service.py` or any blueprint when stock runs low. Users will never receive low-stock notifications.
- [ ] P1: `app/services/notification_service.py:386` -- `notify_order_status_change()` is defined and tested but never called from `order_service.change_status()`. Users will never receive order status change notifications.
- [ ] P1: `app/services/notification_service.py:430` -- `notify_payment_received()` is defined and tested but never called from `invoice_service.record_payment()`. Users will never receive payment notifications.

### Unused Forms

- [ ] P3: `app/forms/search.py:12` -- `GlobalSearchForm` is defined and exported in `forms/__init__.py` but never imported or used by any blueprint. The search blueprint uses raw `request.args` instead.

### Dead Templates

- [ ] P3: `app/templates/auth/login.html` -- Never referenced from any route or included from another template. This is a dead duplicate of `security/login_user.html` (which is the actual Flask-Security override template).
- [ ] P3: `app/templates/search/_autocomplete.html` -- Never referenced from any Python route. Contains only `{% include 'partials/search_autocomplete.html' %}`. The search blueprint renders `partials/search_autocomplete.html` directly. Comment says "Legacy autocomplete template -- kept for backward compatibility" but nothing uses it.

### Redundant Import

- [ ] P3: `app/blueprints/items.py:259` -- `from app.models.customer import Customer` is imported locally inside `quick_create()`, but `Customer` is already imported at module level on line 15.

### Inconsistent Service Layer Usage

- [ ] P2: `app/blueprints/customers.py:138-140` -- Edit route uses `form.populate_obj(customer)` + `db.session.commit()` directly, bypassing `customer_service.update_customer()`. This skips any service-layer validation or logic. Same pattern in inventory edit (line 172), price list edit (line 160), and price list category edit (line 275).

---

## Stale Comments

- [ ] P2: `app/models/service_item.py:4` -- Docstring says "Each item **optionally** belongs to a customer" but `customer_id` is now `nullable=False` (NOT NULL) since migration `h8c9d0e1f2g3`. Should say "Each item belongs to a customer."
- [ ] P2: `app/models/customer.py:8` -- Docstring says the model includes "polymorphic tagging via the TaggableMixin" but `Customer` does not inherit from `TaggableMixin`. Its class definition is `Customer(TimestampMixin, SoftDeleteMixin, AuditMixin, db.Model)`.
- [ ] P3: `app/extensions.py:27-28` -- Comment says "Mail support -- placeholder for future password-reset / notification emails." Email notification is already fully implemented via `app/services/email_service.py` and Celery tasks. No longer a placeholder.
- [ ] P3: `app/config.py:43` -- Comment says `SECURITY_RECOVERABLE = False  # Disable password recovery (no email configured yet)`. Email IS configured. Comment should say something like "Disabled by design -- admin resets passwords via user management."
- [ ] P3: `app/config.py:76` -- Comment says `MAIL_SERVER` etc. are "placeholder for future use" but email is already implemented.

---

## TODO/FIXME Consolidation

No `TODO`, `FIXME`, `HACK`, or `XXX` markers found in any `.py` or `.html` files. These were cleaned up in commit `9b8a443` ("Codebase audit: fix stale comments, remove dead code, consolidate TODOs").

---

## Incomplete Features

- [ ] P1: **Notification triggers not wired** -- `notify_low_stock()`, `notify_order_status_change()`, and `notify_payment_received()` are fully implemented with tests but never called from the services that should trigger them. The entire in-app notification pipeline (create notification -> email delivery via Celery) works, but nothing in the app actually fires these events. This means the notification system is effectively inert for automated alerts.

- [ ] P2: **Price list part linking has no UI** -- `link_part()` and `unlink_part()` in `price_list_service.py` allow associating inventory items with price list items (via `PriceListItemPart`), but no route or UI exists to manage these associations. The `price_list/detail.html` template renders linked parts if they exist, but there is no form to add or remove them.

- [ ] P2: **Saved search default loading not wired** -- `saved_search_service.get_default_search()` exists to retrieve a user's default saved search for auto-loading on list pages, but no blueprint code calls it. Saved searches can be created and set as default, but the default is never actually applied when loading a list view.

- [ ] P2: **Inconsistent update patterns** -- Some blueprints (customers, inventory, price list) bypass their service layer for updates, using `form.populate_obj()` + `db.session.commit()` directly. Meanwhile create and delete operations go through the service layer. This means service-layer validation rules on updates are never enforced in practice.

- [ ] P3: **SORTABLE_FIELDS duplicated** -- `SORTABLE_FIELDS` is defined in both `app/services/invoice_service.py` (line 30) and `app/blueprints/invoices.py` (line 39) with identical content. Same pattern for orders: `app/services/order_service.py` (line 48) and `app/blueprints/orders/__init__.py` (line 29). Risk of the lists drifting apart.

- [ ] P3: **Blueprints `__init__.py` missing entries** -- `app/blueprints/__init__.py` exports 14 blueprints but is missing `admin_bp`, `docs_bp`, and `attachments_bp`. The app factory imports them directly so this has no functional impact, but the `__init__.py` is incomplete as a registry.

---

## Feature Proposals (Discussion)

### High Value

1. **Wire notification triggers into services** -- Call `notify_low_stock()` from `inventory_service.adjust_stock()` when stock drops below reorder level. Call `notify_order_status_change()` from `order_service.change_status()`. Call `notify_payment_received()` from `invoice_service.record_payment()`. All the plumbing exists; just needs 3-6 lines of glue code.

2. **Part linking UI for price list items** -- Add a form/modal on the price list detail page to associate inventory items as required parts. This would enable automatic part deduction when services are applied to orders (the `auto_deduct_parts` flag already exists on `PriceListItem`).

3. **Customer portal / self-service status lookup** -- Add a public-facing (no login) route where customers can check order status by order number + last name or email. Eliminates phone calls asking "is my suit done yet?"

4. **Recurring service reminders** -- Track last-service-date per item and send reminder notifications when annual service intervals approach. The `last_service_date` field exists on `ServiceItem` but is never populated or used.

### Medium Value

5. **Batch operations on list views** -- Add checkbox selection + bulk actions (e.g., "Mark 5 orders as ready for pickup", "Deactivate selected inventory items"). Common admin workflow currently requires clicking into each record individually.

6. **Service order templates / presets** -- Allow saving common service configurations (e.g., "Annual Drysuit Service" = specific services + parts + estimated labor) as templates that pre-populate when creating new orders.

7. **Dashboard customization** -- Let users configure which cards appear on their dashboard and in what order. Different roles care about different metrics.

8. **Auto-populate `last_service_date`** -- When a service order containing a service item transitions to "completed" status, automatically update the item's `last_service_date`. Currently this field is never written.

### Lower Priority

9. **Audit log export** -- Add CSV/XLSX export for the audit log, filtered by the same parameters as the view. Useful for compliance reporting.

10. **Password recovery via email** -- `SECURITY_RECOVERABLE` is set to `False`. With email now fully configured, enabling Flask-Security's password recovery flow would be straightforward and reduce admin burden for password resets.

---

## Route/Template Verification

### Templates -- All Verified

Every `render_template()` call in the blueprints references a template that exists in `app/templates/`. All templates extend `base.html` correctly. All `url_for()` calls in templates reference valid blueprint endpoints.

### Specific Findings

- **`url_for('security.login')` and `url_for('security.logout')`** in `base.html` -- Valid; these are auto-registered by Flask-Security.
- **`url_for('security.change_password')`** in `base.html` -- Valid; `SECURITY_CHANGEABLE = True`.
- **`url_for_security('login')`** in `security/login_user.html` -- Valid Flask-Security helper.
- **`hx-get` / `hx-post` attributes** in templates consistently reference valid endpoints (gallery, autocomplete, activity feed, log tail).
- **No broken `href` or `action` attributes** found in any template.

### Macro Usage -- Consistent

All templates import macros from `macros/` correctly: `forms.html`, `pagination.html`, `tables.html`, `status_badges.html`, `modals.html`, `tags.html`, `saved_searches.html`.
