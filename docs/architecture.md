# System Architecture

Dive Service Management (DSM) is a Flask-based web application for managing dive equipment repair and service operations. This document describes the system's architecture, data model, and key design decisions.

## Table of Contents

- [System Overview](#system-overview)
- [Application Architecture](#application-architecture)
- [Data Model](#data-model)
- [Service Layer](#service-layer)
- [Authentication and Authorization](#authentication-and-authorization)
- [Search](#search)
- [Background Tasks](#background-tasks)
- [Configuration Hierarchy](#configuration-hierarchy)
- [Docker Architecture](#docker-architecture)

---

## System Overview

DSM runs as a set of five Docker containers communicating over a private bridge network.

```
                         +------------------+
                         |   Web Browser    |
                         +--------+---------+
                                  |
                            port 8080
                                  |
+---------------------------------------------------------------------+
|  dsm-net (Docker bridge network)                                    |
|                                                                     |
|  +------------------+    +------------------+   +----------------+  |
|  |   web            |    |   db             |   |   redis        |  |
|  |   (Flask +       +--->|   (MariaDB 11    |   |   (Redis 7     |  |
|  |    Gunicorn)     |    |    LTS)          |   |    Alpine)     |  |
|  |   port 8080      |    |   port 3306      |   |   port 6379   |  |
|  +--------+---------+    +------------------+   +-------+--------+  |
|           |                                             |           |
|  +--------+---------+    +------------------+           |           |
|  |   worker         |    |   beat           +-----------+           |
|  |   (Celery        +----+   (Celery Beat   |                      |
|  |    Worker)       |    |    Scheduler)    |                      |
|  +------------------+    +------------------+                      |
+---------------------------------------------------------------------+

Volumes:
  dsm-db-data    -> /var/lib/mysql (persistent database)
  dsm-redis-data -> /data (persistent cache/queue)
  ./uploads      -> /app/uploads (file attachments)
  ./logs         -> /app/logs (application logs)
  ./instance     -> /app/instance (local config overrides)
```

**Container roles:**

| Container | Image | Purpose |
|-----------|-------|---------|
| `dsm-web` | `dsm-web:latest` | Flask app served by Gunicorn (2 workers, 4 threads). Runs auto-migration and seeding on startup via `docker-entrypoint.sh`. |
| `dsm-db` | `mariadb:lts` | MariaDB 11 LTS database. Tuned for memory-constrained environments via `docker/db/conf/custom.cnf`. |
| `dsm-redis` | `redis:7-alpine` | Redis 7 with AOF persistence. Serves as Celery broker, result backend, and general cache. 64 MB memory limit with LRU eviction. |
| `dsm-worker` | `dsm-web:latest` | Celery worker (2 concurrent tasks). Processes async jobs like notification checks and exports. |
| `dsm-beat` | `dsm-web:latest` | Celery Beat scheduler. Triggers periodic tasks such as low-stock checks and overdue invoice reminders. |

---

## Application Architecture

### App Factory

The application is bootstrapped via `create_app()` in `app/__init__.py`. This function:

1. Loads `.env` via `python-dotenv`
2. Resolves the config class from `DSM_ENV` (defaults to `development`)
3. Creates the Flask instance with `instance_relative_config=True`
4. Applies the config class, including optional `init_app()` validation (e.g., `ProductionConfig` rejects default secret keys)
5. Optionally loads `instance/config.py` for local overrides
6. Initializes extensions, registers blueprints, error handlers, and CLI commands

```python
from app import create_app
app = create_app()                   # uses DSM_ENV or defaults to development
app = create_app(TestingConfig)      # explicit config for test suite
```

### Extensions

Extensions are created in `app/extensions.py` as uninitialized singletons, then bound to the app inside `create_app()`:

| Extension | Instance | Purpose |
|-----------|----------|---------|
| Flask-SQLAlchemy | `db` | ORM and database session management |
| Flask-Migrate | `migrate` | Alembic schema migrations |
| Flask-Security-Too | `security` | Authentication, authorization, password hashing |
| Flask-WTF CSRFProtect | `csrf` | CSRF token generation and validation |
| Flask-Mail | `mail` | Email support (optional; placeholder for future use) |

### Blueprint Registration

All 15 blueprints are registered in `_register_blueprints()`. Each blueprint owns a URL prefix and a set of related views:

| Blueprint | URL Prefix | Description |
|-----------|-----------|-------------|
| `admin` | `/admin` | User management, system settings, data management, CSV import |
| `auth` | (none) | Login/logout (delegates to Flask-Security) |
| `customers` | `/customers` | Customer CRUD, individual/business types |
| `dashboard` | `/dashboard` | Main landing page with live summary cards |
| `export` | `/export` | XLSX export functionality |
| `health` | (none) | `/health` endpoint for Docker health checks |
| `inventory` | `/inventory` | Inventory item management, stock tracking |
| `invoices` | `/invoices` | Invoice lifecycle, line items, payments |
| `items` | `/items` | Service item (equipment) management |
| `notifications` | `/notifications` | In-app notification list and read tracking |
| `orders` | `/orders` | Service order workflow, status transitions |
| `price_list` | `/price-list` | Price list categories, items, linked parts |
| `reports` | `/reports` | Revenue, order, inventory, customer, and aging reports |
| `search` | `/search` | Global search across entities |
| `tools` | `/tools` | Utility calculators (seal size, material estimator, pricing, leak test, valve reference, unit converter) |

### Request Lifecycle

A typical authenticated request follows this path:

```
Browser Request
  |
  v
Flask-Security auth check (login_required / roles_required)
  |
  v
Blueprint route handler
  |
  v
Service layer function (business logic, validation)
  |
  v
SQLAlchemy model (database query / mutation)
  |
  v
Jinja2 template (renders HTML with HTMX/Bootstrap/Alpine.js)
  |
  v
HTTP Response
```

For unauthenticated users, Flask-Security redirects to `/login`. For authenticated users lacking the required role, the app returns a 403 Forbidden response (because `SECURITY_UNAUTHORIZED_VIEW` is set to `None`).

### Error Handling

Custom error pages are registered for HTTP 403, 404, and 500 responses, rendering templates from `app/templates/errors/`.

### CLI Commands

Two custom commands are registered:

- `flask seed-db` -- Seeds roles, price list categories, demo users (dev/test only), and system config entries. Idempotent.
- `flask create-admin` -- Creates an admin user interactively. For production deployments where demo users are skipped.

---

## Data Model

### Entity Relationship Overview

```
User ----< user_roles >---- Role
  |
  +-- assigned_tech on ServiceOrder
  +-- tech on LaborEntry
  +-- Notification (user_id, or NULL for broadcast)
  +-- NotificationRead (per-user read state for broadcasts)

Customer ----< ServiceItem
  |                |
  |                +-- DrysuitDetails (1:1, optional)
  |                |
  |                +--< ServiceOrderItem
  |                       |
  |                       +--< AppliedService
  |                       +--< PartUsed
  |                       +--< LaborEntry
  |                       +--< ServiceNote
  |
  +----< ServiceOrder
  |         |
  |         +--< ServiceOrderItem (above)
  |         +--< invoice_orders >--< Invoice
  |
  +----< Invoice
            |
            +--< InvoiceLineItem
            +--< Payment

PriceListCategory ----< PriceListItem ----< PriceListItemPart

Tag ----< Taggable (polymorphic: any entity type + id)

SystemConfig (key-value settings store)
AuditLog (action tracking)
```

### Models (17 total)

| Model | Table | Mixins | Key Relationships |
|-------|-------|--------|-------------------|
| `User` | `users` | -- | Roles (M2M via `user_roles`), Notifications |
| `Role` | `roles` | -- | Users (M2M) |
| `Customer` | `customers` | Timestamp, SoftDelete, Audit | ServiceItems, ServiceOrders, Invoices |
| `ServiceItem` | `service_items` | Timestamp, SoftDelete, Audit | Customer (FK), DrysuitDetails (1:1) |
| `DrysuitDetails` | `drysuit_details` | Timestamp | ServiceItem (1:1, unique FK) |
| `InventoryItem` | `inventory_items` | Timestamp, SoftDelete, Audit | PartUsed (referenced) |
| `PriceListCategory` | `price_list_categories` | Timestamp | PriceListItems |
| `PriceListItem` | `price_list_items` | Timestamp | Category (FK), PriceListItemParts |
| `PriceListItemPart` | `price_list_item_parts` | -- | PriceListItem (FK), InventoryItem (FK) |
| `Tag` | `tags` | -- | Taggable entries |
| `Taggable` | `taggables` | -- | Tag (FK), polymorphic link (type + id) |
| `ServiceOrder` | `service_orders` | Timestamp, SoftDelete, Audit | Customer (FK), Tech (FK), OrderItems, Invoices (M2M) |
| `ServiceOrderItem` | `service_order_items` | Timestamp | Order (FK), ServiceItem (FK), children cascade |
| `AppliedService` | `applied_services` | Timestamp | ServiceOrderItem (FK), PriceListItem (FK, optional) |
| `PartUsed` | `parts_used` | Timestamp | ServiceOrderItem (FK), InventoryItem (FK) |
| `LaborEntry` | `labor_entries` | Timestamp | ServiceOrderItem (FK), User/tech (FK) |
| `ServiceNote` | `service_notes` | Timestamp | ServiceOrderItem (FK) |
| `Invoice` | `invoices` | Timestamp, Audit | Customer (FK), LineItems, Payments, Orders (M2M) |
| `InvoiceLineItem` | `invoice_line_items` | Timestamp | Invoice (FK), source links (FK, optional) |
| `Payment` | `payments` | Timestamp | Invoice (FK) |
| `Notification` | `notifications` | Timestamp | User (FK, nullable for broadcast) |
| `NotificationRead` | `notification_reads` | -- | User (FK), Notification (FK) |
| `SystemConfig` | `system_config` | Timestamp | -- |
| `AuditLog` | `audit_log` | -- | User (FK) |

### Model Mixins

Three mixins in `app/models/mixins.py` provide reusable column patterns:

- **TimestampMixin**: Adds `created_at` (set on insert) and `updated_at` (set on update)
- **SoftDeleteMixin**: Adds `is_deleted` flag and `deleted_at` timestamp, plus `not_deleted()` class method for filtered queries and `soft_delete()` / `restore()` instance methods
- **AuditMixin**: Adds `created_by` FK to `users.id`

A **TaggableMixin** in `app/models/tag.py` provides `add_tag()`, `remove_tag()`, and `get_tags()` helper methods for any model that needs polymorphic tagging.

### Key Design Decisions

- **Polymorphic tags**: The `taggables` table uses `taggable_type` + `taggable_id` columns to associate any model with tags, avoiding per-model join tables.
- **Soft deletes**: Customers, service items, inventory items, and service orders use soft deletion. Invoices use status-based void instead of deletion since financial records must be preserved.
- **Price snapshots**: When a price list item is applied to an order, the service name, description, and price are copied into `AppliedService` fields. This preserves the price at time of service even if the price list changes later.
- **Many-to-many invoices**: The `invoice_orders` association table links invoices to service orders, allowing one invoice to cover multiple orders or one order to appear on multiple invoices.
- **DrysuitDetails extension table**: Drysuit-specific fields (seal types, zipper configuration, valve details, boot information) are stored in a separate 1:1 table rather than adding nullable columns to the generic `ServiceItem` table.
- **Inventory uses Decimal**: `quantity_in_stock` and `reorder_level` are `Numeric(10,2)` to support fractional quantities without floating-point rounding errors.
- **Negative stock prevention**: `add_part_used()` checks available stock before deduction and raises `ValueError` if the deduction would drive stock below zero.

### Migration Chain

Migrations are stored in `migrations/versions/` and applied in order:

1. `65a0d287ea08` -- Initial schema: users, roles, user_roles
2. `46a737a590f6` -- Phase 2: customers, service_items, drysuit_details, inventory, price_list, tags
3. `phase_3_5_service_orders_invoices_notifications` -- Phase 3-5: service orders, order items, applied services, parts used, labor, notes, invoices, payments, notifications
4. `p0_1_inventory_decimal_stock_columns` -- Post-review: convert inventory stock columns to Decimal(10,2)
5. `p0_2_notification_reads_table` -- Post-review: add notification_reads for broadcast read tracking
6. `d4e5f6a7b8c9` -- System config table
7. `e5f6a7b8c9d0` -- Audit log table

The `docker-entrypoint.sh` runs `flask db upgrade` automatically on web container startup, so schema updates are applied when a new version is deployed.

---

## Service Layer

Business logic lives in `app/services/`, with one module per domain area:

| Service | Module | Key Responsibilities |
|---------|--------|---------------------|
| Order | `order_service.py` | Order CRUD, order number generation (SO-YYYY-NNNNN), status transitions with validation, order items, applied services with price list snapshot, parts used with inventory deduction, labor entries, service notes, order summary calculations |
| Invoice | `invoice_service.py` | Invoice CRUD, invoice number generation (INV-YYYY-NNNNN), status transitions (INVOICE_STATUS_TRANSITIONS), line item management, payment recording with automatic status updates, totals recalculation |
| Customer | `customer_service.py` | Customer CRUD with individual/business validation |
| Inventory | `inventory_service.py` | Inventory CRUD, stock adjustments |
| Price List | `price_list_service.py` | Category and item management, linked parts |
| Search | `search_service.py` | Global search across customers, service items, inventory |
| Notification | `notification_service.py` | Notification CRUD, broadcast support, per-user read tracking via NotificationRead |
| Report | `report_service.py` | Revenue, order, inventory, customer, and aging report data aggregation |
| Export | `export_service.py` | XLSX export generation via openpyxl |
| Config | `config_service.py` | Typed read/write of system_config with ENV override locking |
| Data Management | `data_management_service.py` | Table stats, DB version/size, migration status, SQL backup |
| Import | `import_service.py` | CSV import for customers/inventory with parse, validate, preview, confirm flow |
| Tag | `tag_service.py` | Tag CRUD operations |
| Audit | `audit_service.py` | Audit log recording and querying |

### When Services Are Used vs Direct Model Access

- **Phase 3+ blueprints** (orders, invoices, reports, notifications, admin, search, export, tools) use the service layer for all business logic.
- **Phase 2 blueprints** (customers, items, inventory, price_list) access models directly in some routes. This is a known simplification from the initial implementation.
- **Status changes** must always go through service functions (`change_status()` for orders, status transition validation for invoices) to enforce the state machine.
- **Order summary calculations** and **invoice totals recalculation** are service-layer responsibilities, not model methods.

### Key Patterns

- **Retry-on-IntegrityError**: Order and invoice number generation retries up to 3 times on IntegrityError to handle race conditions in concurrent requests.
- **SORTABLE_FIELDS allowlists**: List-view service functions validate the `sort` parameter against an explicit allowlist to prevent SQL injection via sort column manipulation.
- **Type-aware payment math**: Payment sums use SQLAlchemy `case()` expressions to negate refund amounts, ensuring correct balance calculations.

---

## Authentication and Authorization

DSM uses **Flask-Security-Too** for authentication with session-based login (no token auth). Passwords are hashed with Argon2 in production and plaintext in tests.

### Roles

| Role | Description | Capabilities |
|------|-------------|-------------|
| `admin` | Full system access | Everything, plus user management, system settings, data management, CSV import |
| `technician` | Create and edit data | Create/edit customers, items, orders, invoices. Cannot access admin pages. |
| `viewer` | Read-only access | View all data, run reports. Cannot create or modify records. |

### Permission Enforcement

- **`@login_required`**: Applied to all routes except `/health` and `/login`. Unauthenticated users are redirected to the login page.
- **`@roles_required("admin")`**: Applied to all admin blueprint routes. Authenticated users without the admin role receive a 403 response.
- **Viewer restrictions**: Write routes (create, edit, delete, status change) check for appropriate roles and return 403 for viewers.

### Security Configuration

- Registration is disabled (`SECURITY_REGISTERABLE = False`)
- Password recovery is disabled (`SECURITY_RECOVERABLE = False`)
- Login tracking is enabled (`SECURITY_TRACKABLE = True`)
- Password changes are enabled (`SECURITY_CHANGEABLE = True`)
- `ProductionConfig.init_app()` rejects default SECRET_KEY and SECURITY_PASSWORD_SALT values at startup

---

## Search

### Global Search

The search service (`app/services/search_service.py`) provides a `global_search()` function that queries across three entity types:

- **Customers**: Matches on first_name, last_name, business_name, email, phone_primary
- **Service Items**: Matches on name, serial_number, brand, model
- **Inventory Items**: Matches on name, SKU, manufacturer

All searches use SQL `ILIKE` patterns for case-insensitive substring matching. Soft-deleted records are excluded via the `not_deleted()` class method.

### Per-Entity Search

Individual list views (orders, invoices, customers, inventory) have their own search and filter parameters handled in their respective service layer functions.

### FULLTEXT Indexes

MariaDB's `innodb_ft_min_token_size` is set to 2 in `docker/db/conf/custom.cnf` to allow short search terms (e.g., "O2", "DI") in FULLTEXT indexes.

---

## Background Tasks

### Celery

The Celery application is created in `app/celery_app.py` using a factory that wraps task execution inside the Flask application context:

```python
celery -A app.celery_app worker --loglevel=info --concurrency=2
celery -A app.celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule
```

Redis serves as both the Celery broker (database 1) and result backend (database 2).

### Worker Tasks

The worker container processes asynchronous tasks including:

- Notification generation (low-stock alerts, overdue invoice reminders)
- Export file generation
- Periodic cleanup operations

### Scheduled Tasks (Beat)

The beat container runs periodic tasks on a configurable schedule:

- **Low-stock checks**: Scans inventory for items below reorder level and creates notifications. Frequency controlled by `notification.low_stock_check_hours` system config.
- **Overdue invoice reminders**: Checks for invoices past due date and creates notifications. Run time controlled by `notification.overdue_check_time` system config.

---

## Configuration Hierarchy

Configuration is resolved in this order (highest priority first):

1. **Environment variables** (`DSM_*` prefix): Set in `.env` file or container environment. Always takes precedence.
2. **Instance config** (`instance/config.py`): Optional Python file for local overrides. Not committed to version control.
3. **Database system_config** (`system_config` table): Admin-editable settings stored in the database. Some keys can be locked by ENV variables.
4. **Application defaults**: Hardcoded in `app/config.py` config classes.

### Config Classes

| Class | `DSM_ENV` value | Key differences |
|-------|----------------|-----------------|
| `DevelopmentConfig` | `development` | `DEBUG = True` |
| `ProductionConfig` | `production` | `DEBUG = False`, validates SECRET_KEY and SECURITY_PASSWORD_SALT are not defaults |
| `TestingConfig` | `testing` | SQLite in-memory, CSRF disabled, plaintext passwords |

### ENV Override Locking

The config service (`app/services/config_service.py`) maps certain system_config keys to environment variables. When the ENV var is set, the DB value is ignored and the setting appears as read-only in the admin UI:

| Config Key | ENV Variable |
|------------|-------------|
| `company.name` | `DSM_COMPANY_NAME` |
| `display.pagination_size` | `DSM_PAGINATION_SIZE` |
| `security.password_min_length` | `DSM_PASSWORD_MIN_LENGTH` |
| `security.session_lifetime_hours` | `DSM_SESSION_LIFETIME_HOURS` |

---

## Docker Architecture

### Container Dependencies

```
web  --> db (healthy), redis (healthy)
worker --> db (healthy), redis (healthy)
beat --> redis (healthy)
```

The `depends_on` directive with `condition: service_healthy` ensures containers start in the correct order.

### Health Checks

| Container | Check Method | Interval |
|-----------|-------------|----------|
| `web` | `curl -f http://localhost:8080/health` (checks DB connectivity) | 30s |
| `db` | `healthcheck.sh --connect --innodb_initialized` | 10s |
| `redis` | `redis-cli ping` | 10s |
| `worker` | `celery inspect ping` (checks worker responds) | 60s |
| `beat` | `pgrep -f 'celery.*beat'` (checks process running) | 60s |

### Volumes

| Volume | Mount Point | Purpose |
|--------|------------|---------|
| `dsm-db-data` (named) | `/var/lib/mysql` | Persistent database storage. Survives container recreation. |
| `dsm-redis-data` (named) | `/data` | Persistent Redis data (AOF). |
| `./uploads` (bind) | `/app/uploads` | User-uploaded files (logos, imports, exports, attachments) |
| `./logs` (bind) | `/app/logs` | Application log files |
| `./instance` (bind) | `/app/instance` | Instance-specific config overrides |
| `./docker/db/init` (bind) | `/docker-entrypoint-initdb.d` | Database initialization scripts |
| `./docker/db/conf` (bind) | `/etc/mysql/conf.d` | MariaDB configuration overrides |

### Networking

All containers communicate over the `dsm-net` bridge network. Only the web container exposes a port to the host (`${DSM_PORT:-8080}`).

### Startup Process

1. MariaDB starts and initializes (creates database and user from `MARIADB_*` env vars on first run)
2. Redis starts and passes health check
3. Web container starts and runs `docker-entrypoint.sh`:
   - Runs `flask db upgrade` to apply any pending migrations
   - Runs `flask seed-db` to seed default data (idempotent)
   - In production mode, either step failing causes the container to exit with code 1
   - Starts Gunicorn with 2 workers and 4 threads
4. Worker and beat containers start after their dependencies are healthy

### Image Build

The Dockerfile uses a multi-stage build:

- **Stage 1 (builder)**: Installs build dependencies (gcc, libmysqlclient-dev) and pip packages into a prefix directory
- **Stage 2 (runtime)**: Copies only the installed packages and application code. Runs as a non-root `dsm` user. Includes `curl` for health checks.

The resulting image supports both ARM64 (Raspberry Pi) and x86-64 architectures.
