---

# Dive Service Management -- Project Plan

## Synopsis

This is a customer/service item/inventory management tool for a dive equipment repair business. It tracks customers, service orders, serviceable items (primarily drysuits and related components), parts inventory, billing/invoicing, and provides reporting and utility tools. The initial deployment target is a scuba drysuit repair shop, but the architecture is designed to be reusable for any item-repair business.

The system runs as a containerized web application deployable on Raspberry Pi (ARM64) or standard x86-64 Docker hosts, with a separate MariaDB database container.

---

## 1. Technology Stack

### 1.1 Backend: Python 3.12+ with Flask 3.1.x

**Why Flask over FastAPI:**
- Jinja2 is Flask's native, first-class template engine. With an HTMX-driven frontend, the server returns rendered HTML fragments on nearly every request. Flask's `render_template()` and template inheritance are built for exactly this workflow.
- FastAPI is designed around JSON API responses and async request handling. While FastAPI can serve Jinja2 templates, it is bolted on rather than native -- the ergonomics are awkward (manual `Request` object passing, no built-in `url_for` in templates without extra configuration, no flash messaging).
- Flask has a richer ecosystem of server-rendered extensions (Flask-Login, Flask-WTF, Flask-Security, Flask-Admin) that assume HTML responses. FastAPI's ecosystem is oriented toward API-first applications.
- HTMX does not need async server capabilities. Each HTMX request is a simple HTTP round-trip returning an HTML fragment. Flask's synchronous WSGI model handles this naturally without the complexity of async/await.
- For a small-team internal tool on a Raspberry Pi, Flask's simplicity, lower memory footprint, and mature documentation are practical advantages.

**Specific versions and libraries:**

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.12+ | Runtime (3.12 is widely supported on ARM64 and has good performance) |
| Flask | 3.1.x | Web framework |
| SQLAlchemy | 2.0.x | ORM and database abstraction |
| Flask-SQLAlchemy | 3.1.x | Flask-SQLAlchemy integration |
| Flask-Migrate (Alembic) | 4.1.x | Database schema migrations |
| Flask-Login | 0.6.x | Session management and authentication |
| Flask-WTF / WTForms | 1.2.x / 3.1.x | Form handling and CSRF protection |
| Flask-Security-Too | 5.7.x | Role-based auth, password hashing, user management |
| Flask-Principal | 0.4.x | Identity and permission management (bundled with Flask-Security) |
| Gunicorn | 22.x | Production WSGI server |
| mysqlclient | 2.2.x | MariaDB/MySQL driver (C extension, fastest) |
| fpdf2 | 2.8.x | PDF generation for invoices, price lists, and reports (lightweight, no system dependencies, fast on ARM64) |
| WeasyPrint | 67.x | (Optional — not included by default) Complex HTML-to-PDF rendering — evaluated but not adopted. Has heavy system dependencies (Pango, Cairo) that are slow to install on ARM64. The project uses fpdf2 exclusively. System deps are commented out in the Dockerfile for reference. |
| openpyxl | 3.1.x | XLSX export |
| python-dotenv | 1.0.x | Environment variable management |
| Celery | 5.4.x | Background task queue (notifications, report generation, exports) — default for full deployments |
| Huey | 2.5.x | (Optional — not included by default) Lightweight task queue — evaluated as alternative to Celery for Pi deployments but not adopted. The project uses Celery exclusively. |
| Redis | 7.x | Celery/Huey broker and result backend, also used for caching |
| Marshmallow | 3.22.x | (Optional — not included by default) Evaluated for import/export serialization but not adopted. The project uses direct CSV/XLSX handling via openpyxl and built-in csv module. |
| click | 8.x | CLI commands (Flask's native CLI extension) |
| Pytest | 8.x | Test runner and framework |
| Pytest-Flask | 1.3.x | Flask test client fixtures and helpers |
| pytest-cov | 6.x | Code coverage reporting |
| pytest-xdist | 3.x | Parallel test execution (optional, for faster CI runs) |
| factory-boy | 3.3.x | Test data factories for models |
| Faker | 30.x | Realistic fake data generation for tests |
| responses | 0.25.x | Mock HTTP requests for external integrations (future) |
| freezegun | 1.4.x | Mock datetime for time-sensitive tests (overdue invoices, etc.) |

### 1.2 Frontend: Jinja2 + HTMX + Bootstrap 5

| Library | Version | Purpose |
|---------|---------|---------|
| HTMX | 2.0.x | Dynamic page behavior without JavaScript build step |
| Bootstrap 5 | 5.3.x | Responsive CSS framework with dark/light theme support |
| Bootstrap Icons | 1.11.x | Icon set |
| Alpine.js | 3.14.x | Minimal JS for client-side interactivity (dropdowns, modals, local state) |
| Chart.js | 4.4.x | Dashboard and report charts |
| Tom Select | 2.3.x | (Optional — not included by default) Evaluated for searchable dropdowns but not adopted. The project uses native HTML select elements with HTMX-powered inline creation modals instead. |

No build step required. All frontend dependencies served via CDN or vendored static files.

### 1.3 Database: MariaDB 11.x LTS

- Official Docker image supports ARM64 and x86-64 natively
- InnoDB storage engine for ACID compliance and FULLTEXT index support
- Character set: `utf8mb4` with collation `utf8mb4_unicode_ci`
- Full-text indexing on InnoDB for search functionality

**Raspberry Pi (ARM64) tuning** — applied via `docker/db/conf/custom.cnf`:

```ini
[mysqld]
# Memory-constrained settings for Pi (1-4GB total system RAM)
innodb_buffer_pool_size = 128M      # Default 128M is fine; do NOT increase on Pi
innodb_log_file_size = 32M          # Smaller than default 48M
innodb_ft_min_token_size = 2        # Allow short part numbers in FULLTEXT
key_buffer_size = 16M
max_connections = 30                # Fewer connections than default 151
table_open_cache = 200
thread_cache_size = 4
tmp_table_size = 16M
max_heap_table_size = 16M
# Disable performance_schema to save ~100MB RAM
performance_schema = OFF
```

These settings target ~200-250MB RAM for MariaDB. On x86-64 hosts with more RAM, remove or increase these limits.

### 1.4 Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Containerization | Docker + Docker Compose | Multi-container orchestration |
| WSGI Server | Gunicorn | Production application server |
| Reverse Proxy | Nginx (optional) | SSL termination, static file serving |
| Task Queue | Celery + Redis (default) or Huey + Redis/SQLite (lightweight) | Async tasks (PDF generation, exports, notifications) |
| Cache | Redis | Session cache, query cache, rate limiting |
| PDF Generation | fpdf2 (primary) or WeasyPrint (optional) | Invoice, price list, and report PDF export |

---

## 2. Data Model

All tables use InnoDB engine. All `id` fields are auto-incrementing unsigned integers unless otherwise noted. All timestamps are UTC. Soft deletes (via `is_deleted` flag and `deleted_at` timestamp) are used on Customer, ServiceOrder, ServiceItem, and InventoryItem to prevent data loss. Required fields are marked with **(R)**.

### 2.1 User

Handles authentication and role assignment.

```
users
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  username            VARCHAR(80), UNIQUE, NOT NULL (R)
  email               VARCHAR(255), UNIQUE, NOT NULL (R)
  password_hash       VARCHAR(255), NOT NULL (R)
  first_name          VARCHAR(100), NOT NULL (R)
  last_name           VARCHAR(100), NOT NULL (R)
  is_active           BOOLEAN, DEFAULT TRUE, NOT NULL
  confirmed_at        DATETIME, NULLABLE
  last_login_at       DATETIME, NULLABLE
  last_login_ip       VARCHAR(45), NULLABLE
  current_login_at    DATETIME, NULLABLE
  current_login_ip    VARCHAR(45), NULLABLE
  login_count         INT UNSIGNED, DEFAULT 0
  fs_uniquifier       VARCHAR(64), UNIQUE, NOT NULL  -- Flask-Security requirement
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP
```

### 2.2 Role and UserRole

```
roles
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  name                VARCHAR(80), UNIQUE, NOT NULL (R)
  description         VARCHAR(255), NULLABLE
  permissions         TEXT, NULLABLE  -- comma-separated permission strings
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP

user_roles (join table)
  user_id             INT UNSIGNED, FK -> users.id, NOT NULL
  role_id             INT UNSIGNED, FK -> roles.id, NOT NULL
  PRIMARY KEY (user_id, role_id)
```

### 2.3 Customer

```
customers
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  customer_type       ENUM('individual','business'), DEFAULT 'individual', NOT NULL (R)
  -- Individual fields
  first_name          VARCHAR(100), NULLABLE
  last_name           VARCHAR(100), NULLABLE
  -- Business fields
  business_name       VARCHAR(255), NULLABLE
  contact_person      VARCHAR(200), NULLABLE
  -- Contact info
  email               VARCHAR(255), NULLABLE
  phone_primary       VARCHAR(20), NULLABLE
  phone_secondary     VARCHAR(20), NULLABLE
  address_line1       VARCHAR(255), NULLABLE
  address_line2       VARCHAR(255), NULLABLE
  city                VARCHAR(100), NULLABLE
  state_province      VARCHAR(100), NULLABLE
  postal_code         VARCHAR(20), NULLABLE
  country             VARCHAR(100), DEFAULT 'US', NULLABLE
  -- Preferences and metadata
  preferred_contact   ENUM('email','phone','text','none'), DEFAULT 'email'
  tax_exempt          BOOLEAN, DEFAULT FALSE
  tax_id              VARCHAR(50), NULLABLE
  -- Billing defaults
  payment_terms       VARCHAR(100), NULLABLE   -- e.g., "Net 30", "Due on receipt" — overrides system default
  credit_limit        DECIMAL(10,2), NULLABLE  -- optional credit limit; warn tech if balance would exceed
  -- Service flags
  do_not_service      BOOLEAN, DEFAULT FALSE   -- blocks new orders; requires admin override with reason
  do_not_service_reason VARCHAR(500), NULLABLE -- e.g., "Outstanding balance", "Abusive to staff"
  notes               TEXT, NULLABLE
  -- Referral / acquisition tracking
  referral_source     VARCHAR(100), NULLABLE
  -- Soft delete and audit
  is_deleted          BOOLEAN, DEFAULT FALSE, NOT NULL
  deleted_at          DATETIME, NULLABLE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP
  created_by          INT UNSIGNED, FK -> users.id, NULLABLE

  FULLTEXT INDEX ft_customer (first_name, last_name, business_name, email, phone_primary, notes)
  INDEX idx_customer_name (last_name, first_name)
  INDEX idx_customer_business (business_name)
  INDEX idx_customer_email (email)
```

**Validation rule:** Either (`first_name` AND `last_name`) OR `business_name` must be non-null, enforced at the application layer.

### 2.4 Service Order

Represents a work order from a customer, containing one or more service items.

```
service_orders
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  order_number        VARCHAR(20), UNIQUE, NOT NULL (R)  -- generated, e.g., "SO-2026-00042"
  customer_id         INT UNSIGNED, FK -> customers.id, NOT NULL (R)
  -- Status workflow
  status              ENUM('intake','assessment','awaiting_approval','in_progress',
                           'awaiting_parts','completed','ready_for_pickup',
                           'picked_up','cancelled'), DEFAULT 'intake', NOT NULL (R)
  priority            ENUM('low','normal','high','rush'), DEFAULT 'normal', NOT NULL
  -- Assignment
  assigned_tech_id    INT UNSIGNED, FK -> users.id, NULLABLE
  -- Dates
  date_received       DATE, NOT NULL (R)
  date_promised       DATE, NULLABLE
  date_completed      DATE, NULLABLE
  date_picked_up      DATE, NULLABLE
  -- Description
  description         TEXT, NULLABLE  -- general description of requested work
  internal_notes      TEXT, NULLABLE  -- tech-only notes not visible on customer docs
  -- Pricing
  estimated_total     DECIMAL(10,2), NULLABLE
  rush_fee            DECIMAL(10,2), DEFAULT 0.00
  discount_percent    DECIMAL(5,2), DEFAULT 0.00
  discount_amount     DECIMAL(10,2), DEFAULT 0.00
  actual_total        DECIMAL(10,2), NULLABLE          -- final total after all services/parts/labor calculated
  -- Customer approval
  approved_at         DATETIME, NULLABLE               -- when customer approved the work estimate
  approved_by_name    VARCHAR(200), NULLABLE            -- name of person who approved (may not be a system user)
  approval_method     ENUM('in_person','phone','email','text','signature'), NULLABLE
  -- Pickup
  picked_up_by_name   VARCHAR(200), NULLABLE            -- name of person who picked up (may differ from customer)
  pickup_notes        VARCHAR(500), NULLABLE            -- condition at pickup, special instructions given, etc.
  -- Soft delete and audit
  is_deleted          BOOLEAN, DEFAULT FALSE, NOT NULL
  deleted_at          DATETIME, NULLABLE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP
  created_by          INT UNSIGNED, FK -> users.id, NULLABLE

  FULLTEXT INDEX ft_order (order_number, description, internal_notes)
  INDEX idx_order_status (status)
  INDEX idx_order_customer (customer_id)
  INDEX idx_order_date (date_received)
  INDEX idx_order_tech (assigned_tech_id)
```

### 2.5 Service Item

Represents a physical item brought in for service (e.g., a specific drysuit). Tracked by serial number across visits.

```
service_items
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  -- Identification
  serial_number       VARCHAR(100), NULLABLE  -- UNIQUE when not null (partial unique index)
  name                VARCHAR(255), NOT NULL (R)  -- e.g., "DUI CF200X Drysuit"
  -- Item classification
  item_category       VARCHAR(100), NULLABLE  -- e.g., "Drysuit", "BCD", "Regulator"
  -- Serviceability
  serviceability      ENUM('serviceable','non_serviceable','conditional','retired'),
                      DEFAULT 'serviceable', NOT NULL (R)
  serviceability_notes TEXT, NULLABLE  -- reason if non-serviceable or conditional

  -- Generic item fields (apply to any service item type)
  brand               VARCHAR(100), NULLABLE
  model               VARCHAR(100), NULLABLE
  year_manufactured   SMALLINT UNSIGNED, NULLABLE
  notes               TEXT, NULLABLE
  last_service_date   DATE, NULLABLE  -- denormalized; updated when an order containing this item is completed

  -- Customer ownership
  customer_id         INT UNSIGNED, FK -> customers.id, NULLABLE

  -- Custom fields (JSON for extensibility)
  custom_fields       JSON, NULLABLE

  -- Soft delete and audit
  is_deleted          BOOLEAN, DEFAULT FALSE, NOT NULL
  deleted_at          DATETIME, NULLABLE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP
  created_by          INT UNSIGNED, FK -> users.id, NULLABLE

  FULLTEXT INDEX ft_service_item (name, serial_number, brand, model, notes)
  INDEX idx_si_serial (serial_number)
  INDEX idx_si_customer (customer_id)
  INDEX idx_si_category (item_category)
  INDEX idx_si_serviceability (serviceability)
```

### 2.6 Drysuit Details (1:1 extension of Service Item)

Drysuit-specific fields stored in a separate table to keep `service_items` clean for non-drysuit items. Only populated when `item_category = 'Drysuit'`. Linked 1:1 via `service_item_id`.

```
drysuit_details
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  service_item_id     INT UNSIGNED, FK -> service_items.id, UNIQUE, NOT NULL (R)
  -- Suit info
  size                VARCHAR(50), NULLABLE  -- e.g., "M", "ML", "Custom"
  material_type       VARCHAR(100), NULLABLE  -- e.g., "Trilaminate", "Crushed Neoprene", "Neoprene", "Hybrid"
  material_thickness  VARCHAR(50), NULLABLE  -- e.g., "3mm", "4mm", "7mm"
  color               VARCHAR(100), NULLABLE
  suit_entry_type     VARCHAR(50), NULLABLE  -- e.g., "Front-entry", "Back-entry", "Shoulder-entry"
  -- Seal info
  neck_seal_type      VARCHAR(50), NULLABLE  -- e.g., "Latex", "Silicone", "Neoprene"
  neck_seal_system    VARCHAR(100), NULLABLE -- e.g., "SI Tech Quick Neck", "DUI ZipSeal", "Glued"
  wrist_seal_type     VARCHAR(50), NULLABLE  -- e.g., "Latex", "Silicone", "Neoprene"
  wrist_seal_system   VARCHAR(100), NULLABLE -- e.g., "SI Tech Quick Cuff", "DUI ZipSeal", "Glued"
  -- Zipper info
  zipper_type         VARCHAR(100), NULLABLE -- e.g., "YKK Metal Brass", "TiZip Plastic", "BDM Metal"
  zipper_length       VARCHAR(50), NULLABLE  -- e.g., "28 inch"
  zipper_orientation  VARCHAR(50), NULLABLE  -- e.g., "Front", "Back", "Shoulder-to-hip"
  -- Valve info
  inflate_valve_brand VARCHAR(100), NULLABLE -- e.g., "Apeks", "SI Tech"
  inflate_valve_model VARCHAR(100), NULLABLE
  inflate_valve_position VARCHAR(50), NULLABLE -- e.g., "Chest left", "Chest right"
  dump_valve_brand    VARCHAR(100), NULLABLE -- e.g., "Apeks", "SI Tech"
  dump_valve_model    VARCHAR(100), NULLABLE
  dump_valve_type     VARCHAR(50), NULLABLE  -- e.g., "Shoulder", "Forearm", "Wrist", "Cuff"
  -- Boot info
  boot_type           VARCHAR(50), NULLABLE  -- e.g., "Integrated Rock Boot", "Integrated Sock", "Attached"
  boot_size           VARCHAR(20), NULLABLE
  -- Audit
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP
```

When a new drysuit-category service item is created, a `drysuit_details` row is auto-created. The UI shows drysuit-specific fields only when `item_category = 'Drysuit'`. This pattern is extensible — future equipment types (BCD, regulator) can get their own details tables without bloating the core service_items table.

### 2.7 Service Order Items (join: order to service items with per-order data)

Links a service item to a specific service order, with order-specific work data.

```
service_order_items
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  order_id            INT UNSIGNED, FK -> service_orders.id, NOT NULL (R)
  service_item_id     INT UNSIGNED, FK -> service_items.id, NOT NULL (R)
  -- Per-order item info
  work_description    TEXT, NULLABLE  -- specific work requested for this item on this order
  status              ENUM('pending','in_progress','completed','cancelled','returned_unserviceable'),
                      DEFAULT 'pending', NOT NULL
  -- Condition at intake
  condition_at_receipt TEXT, NULLABLE  -- tech documents item condition when received
  -- Customer approval per item
  customer_approved   BOOLEAN, DEFAULT FALSE  -- customer approved work on this specific item
  -- Diagnostics (assessment results)
  diagnosis           TEXT, NULLABLE
  -- Warranty tracking
  warranty_type       ENUM('none','standard','extended','manufacturer'), DEFAULT 'none', NOT NULL
  warranty_start_date DATE, NULLABLE
  warranty_end_date   DATE, NULLABLE
  warranty_notes      VARCHAR(500), NULLABLE  -- e.g., "DUI lifetime warranty on seams"
  -- Completion
  completed_at        DATETIME, NULLABLE
  completed_by        INT UNSIGNED, FK -> users.id, NULLABLE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP

  UNIQUE INDEX uq_order_item (order_id, service_item_id)
```

### 2.8 Service Notes

Dated, tech-attributed notes on a service order item.

```
service_notes
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  service_order_item_id INT UNSIGNED, FK -> service_order_items.id, NOT NULL (R)
  note_text           TEXT, NOT NULL (R)
  note_type           ENUM('diagnostic','repair','testing','general','customer_communication'),
                      DEFAULT 'general', NOT NULL
  created_by          INT UNSIGNED, FK -> users.id, NOT NULL (R)
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP

  FULLTEXT INDEX ft_service_notes (note_text)
  INDEX idx_sn_order_item (service_order_item_id)
```

### 2.9 Inventory Item (Parts)

```
inventory_items
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  sku                 VARCHAR(50), UNIQUE, NULLABLE  -- optional internal SKU
  name                VARCHAR(255), NOT NULL (R)
  description         TEXT, NULLABLE
  -- Classification
  category            VARCHAR(100), NOT NULL (R)  -- e.g., "Seals", "Zippers", "Valves", "Adhesive", "Patches"
  subcategory         VARCHAR(100), NULLABLE       -- e.g., "Neck Seals", "Wrist Seals"
  manufacturer        VARCHAR(100), NULLABLE
  manufacturer_part_number VARCHAR(100), NULLABLE
  -- Pricing
  purchase_cost       DECIMAL(10,2), NULLABLE       -- what we pay
  resale_price        DECIMAL(10,2), NULLABLE       -- what we charge
  markup_percent      DECIMAL(5,2), NULLABLE        -- auto-calculated or manual
  -- Stock
  quantity_in_stock   INT, DEFAULT 0, NOT NULL
  reorder_level       INT UNSIGNED, DEFAULT 0       -- triggers low-stock notification
  reorder_quantity    INT UNSIGNED, NULLABLE         -- suggested reorder amount
  -- Unit
  unit_of_measure     VARCHAR(50), DEFAULT 'each'   -- e.g., "each", "ft", "ml", "oz"
  -- Location
  storage_location    VARCHAR(100), NULLABLE         -- e.g., "Shelf A3", "Bin 12"
  -- Status
  is_active           BOOLEAN, DEFAULT TRUE, NOT NULL
  is_for_resale       BOOLEAN, DEFAULT FALSE         -- can be sold individually (not just used in service)
  -- Supplier info
  preferred_supplier  VARCHAR(255), NULLABLE
  supplier_url        VARCHAR(500), NULLABLE
  minimum_order_quantity INT UNSIGNED, NULLABLE  -- minimum qty per supplier order
  supplier_lead_time_days INT UNSIGNED, NULLABLE -- typical delivery time in days
  -- Expiration tracking (for adhesives, sealants, etc.)
  expiration_date     DATE, NULLABLE            -- items past this date should not be used
  -- Notes and custom
  notes               TEXT, NULLABLE
  custom_fields       JSON, NULLABLE

  -- Soft delete and audit
  is_deleted          BOOLEAN, DEFAULT FALSE, NOT NULL
  deleted_at          DATETIME, NULLABLE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP
  created_by          INT UNSIGNED, FK -> users.id, NULLABLE

  FULLTEXT INDEX ft_inventory (name, description, manufacturer, sku, notes)
  INDEX idx_inv_category (category, subcategory)
  INDEX idx_inv_stock (quantity_in_stock, reorder_level)
  INDEX idx_inv_active (is_active)
```

### 2.10 Parts Used (links inventory to service order items)

Tracks which parts from inventory were used on which service order item, with price snapshot at time of use.

```
parts_used
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  service_order_item_id INT UNSIGNED, FK -> service_order_items.id, NOT NULL (R)
  inventory_item_id   INT UNSIGNED, FK -> inventory_items.id, NOT NULL (R)
  -- Linkage to applied service (if this part was auto-deducted from a price list service)
  applied_service_id  INT UNSIGNED, FK -> applied_services.id, NULLABLE
  is_auto_deducted    BOOLEAN, DEFAULT FALSE, NOT NULL  -- TRUE if auto-added by an applied service's linked parts
  -- Quantity and pricing
  quantity            DECIMAL(10,2), NOT NULL, DEFAULT 1 (R)  -- decimal for fractional units (e.g., 2.5 ft of tape)
  -- Price snapshot at time of use
  unit_cost_at_use    DECIMAL(10,2), NOT NULL (R)    -- purchase cost at time
  unit_price_at_use   DECIMAL(10,2), NOT NULL (R)    -- charge price at time
  notes               VARCHAR(500), NULLABLE
  added_by            INT UNSIGNED, FK -> users.id, NULLABLE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  INDEX idx_pu_order_item (service_order_item_id)
  INDEX idx_pu_inventory (inventory_item_id)
  INDEX idx_pu_applied_service (applied_service_id)
```

### 2.11 Labor Entry

```
labor_entries
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  service_order_item_id INT UNSIGNED, FK -> service_order_items.id, NOT NULL (R)
  tech_id             INT UNSIGNED, FK -> users.id, NOT NULL (R)
  -- Time tracking
  hours               DECIMAL(5,2), NOT NULL (R)
  hourly_rate         DECIMAL(8,2), NOT NULL (R)  -- rate snapshot at time of entry
  -- Description
  description         VARCHAR(500), NULLABLE
  -- Date of work
  work_date           DATE, NOT NULL (R)
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP

  INDEX idx_labor_order_item (service_order_item_id)
  INDEX idx_labor_tech (tech_id)
  INDEX idx_labor_date (work_date)
```

### 2.12 Invoice

Designed for internal tracking with data model extensibility for future payment gateway integration.

```
invoices
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  invoice_number      VARCHAR(20), UNIQUE, NOT NULL (R)  -- generated, e.g., "INV-2026-00107"
  customer_id         INT UNSIGNED, FK -> customers.id, NOT NULL (R)
  -- NOTE: Invoice-to-order linkage is many-to-many via invoice_orders join table (see 2.21)
  -- An invoice may cover one or more service orders, and an order may appear on multiple invoices
  -- (e.g., split billing, progress invoicing)
  -- Status
  status              ENUM('draft','sent','viewed','partially_paid','paid',
                           'overdue','void','refunded'), DEFAULT 'draft', NOT NULL (R)
  -- Dates
  issue_date          DATE, NOT NULL (R)
  due_date            DATE, NULLABLE
  paid_date           DATE, NULLABLE
  -- Amounts
  subtotal            DECIMAL(10,2), NOT NULL, DEFAULT 0.00
  tax_rate            DECIMAL(5,4), DEFAULT 0.0000  -- e.g., 0.0825 for 8.25%
  tax_amount          DECIMAL(10,2), DEFAULT 0.00
  discount_amount     DECIMAL(10,2), DEFAULT 0.00
  total               DECIMAL(10,2), NOT NULL, DEFAULT 0.00
  amount_paid         DECIMAL(10,2), DEFAULT 0.00
  balance_due         DECIMAL(10,2), NOT NULL, DEFAULT 0.00
  -- Payment info (future integration readiness)
  payment_method      VARCHAR(50), NULLABLE   -- e.g., "cash", "check", "credit_card", "stripe", "quickbooks"
  payment_reference   VARCHAR(255), NULLABLE  -- check number, transaction ID, etc.
  external_id         VARCHAR(255), NULLABLE  -- ID in external system (QuickBooks, Stripe, etc.)
  external_system     VARCHAR(50), NULLABLE   -- "quickbooks", "stripe", etc.
  external_sync_at    DATETIME, NULLABLE      -- last sync timestamp
  -- Notes
  notes               TEXT, NULLABLE           -- internal notes
  customer_notes      TEXT, NULLABLE           -- notes printed on invoice for customer
  terms               TEXT, NULLABLE           -- payment terms text
  -- Audit
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP
  created_by          INT UNSIGNED, FK -> users.id, NULLABLE

  FULLTEXT INDEX ft_invoice (invoice_number, notes, customer_notes)
  INDEX idx_inv_status (status)
  INDEX idx_inv_customer (customer_id)
  INDEX idx_inv_date (issue_date)
  INDEX idx_inv_due (due_date)
  INDEX idx_inv_external (external_system, external_id)
```

### 2.13 Invoice Line Items

```
invoice_line_items
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  invoice_id          INT UNSIGNED, FK -> invoices.id, NOT NULL (R)
  -- Line item details
  line_type           ENUM('service','labor','part','fee','discount','other'), NOT NULL (R)
  description         VARCHAR(500), NOT NULL (R)
  quantity            DECIMAL(10,2), NOT NULL, DEFAULT 1
  unit_price          DECIMAL(10,2), NOT NULL (R)
  line_total          DECIMAL(10,2), NOT NULL (R)  -- quantity * unit_price
  -- Source references (for traceability back to the work that generated this line)
  applied_service_id  INT UNSIGNED, FK -> applied_services.id, NULLABLE  -- if line_type='service'
  labor_entry_id      INT UNSIGNED, FK -> labor_entries.id, NULLABLE     -- if line_type='labor'
  parts_used_id       INT UNSIGNED, FK -> parts_used.id, NULLABLE       -- if line_type='part'
  -- Sort
  sort_order          INT UNSIGNED, DEFAULT 0
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  INDEX idx_ili_invoice (invoice_id)
```

### 2.14 Payment Records (future integration readiness)

```
payments
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  -- Linkage: either to an invoice OR directly to a service order (for deposits before invoice exists)
  invoice_id          INT UNSIGNED, FK -> invoices.id, NULLABLE   -- NULL for deposits/prepayments
  service_order_id    INT UNSIGNED, FK -> service_orders.id, NULLABLE  -- for deposit payments tied to an order
  -- Payment classification
  payment_type        ENUM('payment','deposit','refund'), DEFAULT 'payment', NOT NULL
  amount              DECIMAL(10,2), NOT NULL (R)
  payment_date        DATE, NOT NULL (R)
  payment_method      VARCHAR(50), NOT NULL (R)
  reference_number    VARCHAR(255), NULLABLE
  -- External integration
  external_id         VARCHAR(255), NULLABLE
  external_system     VARCHAR(50), NULLABLE
  -- Notes
  notes               VARCHAR(500), NULLABLE
  recorded_by         INT UNSIGNED, FK -> users.id, NULLABLE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  INDEX idx_pay_invoice (invoice_id)
  INDEX idx_pay_order (service_order_id)
  INDEX idx_pay_date (payment_date)
  INDEX idx_pay_type (payment_type)
```

**Validation rule**: At least one of `invoice_id` or `service_order_id` must be non-null (enforced at application layer). When an invoice is later generated for an order that has deposits, the deposits are automatically linked to the invoice and credited toward the balance.

### 2.15 Tags and Tagging System

Polymorphic tagging system that can tag any entity.

```
tags
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  name                VARCHAR(100), UNIQUE, NOT NULL (R)
  slug                VARCHAR(100), UNIQUE, NOT NULL (R)  -- URL-safe version
  color               VARCHAR(7), NULLABLE  -- hex color for UI display, e.g., "#FF5733"
  tag_group           VARCHAR(50), NULLABLE  -- optional grouping, e.g., "repair_type", "priority"
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  INDEX idx_tag_group (tag_group)

taggables (polymorphic join table)
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  tag_id              INT UNSIGNED, FK -> tags.id, NOT NULL
  taggable_type       VARCHAR(50), NOT NULL  -- 'customer', 'service_order', 'service_item', 'inventory_item'
  taggable_id         INT UNSIGNED, NOT NULL
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  UNIQUE INDEX uq_taggable (tag_id, taggable_type, taggable_id)
  INDEX idx_taggable_entity (taggable_type, taggable_id)
```

### 2.16 Audit Log

Tracks all significant data changes for accountability.

```
audit_log
  id                  BIGINT UNSIGNED, PK, AUTO_INCREMENT
  user_id             INT UNSIGNED, FK -> users.id, NULLABLE  -- null for system actions
  action              ENUM('create','update','delete','restore','login','logout',
                           'export','status_change','invoice_generate'), NOT NULL (R)
  entity_type         VARCHAR(50), NOT NULL (R)  -- 'customer', 'service_order', etc.
  entity_id           INT UNSIGNED, NOT NULL (R)
  -- Change details
  field_name          VARCHAR(100), NULLABLE  -- which field changed (null for create/delete)
  old_value           TEXT, NULLABLE
  new_value           TEXT, NULLABLE
  -- Context
  ip_address          VARCHAR(45), NULLABLE
  user_agent          VARCHAR(500), NULLABLE
  additional_data     JSON, NULLABLE  -- any extra context
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  INDEX idx_audit_entity (entity_type, entity_id)
  INDEX idx_audit_user (user_id)
  INDEX idx_audit_date (created_at)
  INDEX idx_audit_action (action)
```

### 2.17 System Configuration

```
system_config
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  config_key          VARCHAR(100), UNIQUE, NOT NULL (R)
  config_value        TEXT, NULLABLE
  config_type         ENUM('string','integer','float','boolean','json'), DEFAULT 'string', NOT NULL
  category            VARCHAR(50), NOT NULL (R)  -- 'company','invoice','notification','display','tax', etc.
  description         VARCHAR(500), NULLABLE
  is_sensitive        BOOLEAN, DEFAULT FALSE  -- mask in UI (e.g., API keys)
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP
  updated_by          INT UNSIGNED, FK -> users.id, NULLABLE

  INDEX idx_config_category (category)
```

### 2.18 Notifications

```
notifications
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  -- Target
  user_id             INT UNSIGNED, FK -> users.id, NULLABLE  -- null = broadcast
  -- Content
  notification_type   VARCHAR(50), NOT NULL (R)  -- 'low_stock', 'overdue_invoice', 'order_status', etc.
  title               VARCHAR(255), NOT NULL (R)
  message             TEXT, NOT NULL (R)
  -- Reference
  entity_type         VARCHAR(50), NULLABLE
  entity_id           INT UNSIGNED, NULLABLE
  -- Status
  is_read             BOOLEAN, DEFAULT FALSE, NOT NULL
  read_at             DATETIME, NULLABLE
  -- Urgency
  severity            ENUM('info','warning','critical'), DEFAULT 'info', NOT NULL
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  INDEX idx_notif_user (user_id, is_read)
  INDEX idx_notif_type (notification_type)
  INDEX idx_notif_date (created_at)
```

### 2.19 Saved Searches / Filters

```
saved_searches
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  user_id             INT UNSIGNED, FK -> users.id, NOT NULL (R)
  name                VARCHAR(100), NOT NULL (R)
  search_type         VARCHAR(50), NOT NULL (R)  -- 'customer', 'order', 'inventory', 'invoice'
  filters_json        JSON, NOT NULL (R)         -- serialized filter criteria
  is_default          BOOLEAN, DEFAULT FALSE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP

  INDEX idx_ss_user (user_id, search_type)
```

### 2.20 Service Price List

Editable catalog of standard services with flat-rate pricing. Based on industry-standard drysuit repair pricing models where parts and labor are bundled into a single published price. Non-price-list (custom/ad-hoc) line items can also be added to any order.

```
price_list_categories
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  name                VARCHAR(100), NOT NULL (R)  -- e.g., "Leak Testing", "Seal Replacement", "Zipper Replacement"
  description         VARCHAR(500), NULLABLE
  sort_order          INT UNSIGNED, DEFAULT 0
  is_active           BOOLEAN, DEFAULT TRUE, NOT NULL
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP

  INDEX idx_plc_active (is_active, sort_order)
```

```
price_list_items
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  category_id         INT UNSIGNED, FK -> price_list_categories.id, NOT NULL (R)
  -- Identification
  code                VARCHAR(30), UNIQUE, NULLABLE  -- optional short code, e.g., "SVC-ZIP-BRS"
  name                VARCHAR(255), NOT NULL (R)     -- e.g., "YKK Brass Zipper Replacement"
  description         TEXT, NULLABLE                 -- detailed description shown to tech and on invoice
  -- Pricing
  price               DECIMAL(10,2), NOT NULL (R)    -- flat-rate price (parts + labor bundled)
  cost                DECIMAL(10,2), NULLABLE        -- internal cost basis for margin tracking
  -- Pricing tiers (optional, for material/brand variants)
  price_tier          VARCHAR(50), NULLABLE  -- e.g., "Standard", "Premium", "Neoprene Surcharge"
  -- Scope
  is_per_unit         BOOLEAN, DEFAULT TRUE, NOT NULL  -- TRUE = priced per item (e.g., per seal), FALSE = flat regardless
  default_quantity    DECIMAL(10,2), DEFAULT 1         -- e.g., 2 for "wrist seals (pair)"
  unit_label          VARCHAR(50), DEFAULT 'each'      -- e.g., "each", "pair", "per inch", "per patch"
  -- Inventory linkage (optional: auto-deduct parts when this service is applied)
  auto_deduct_parts   BOOLEAN, DEFAULT FALSE
  -- Tax
  is_taxable          BOOLEAN, DEFAULT TRUE, NOT NULL
  -- Display
  sort_order          INT UNSIGNED, DEFAULT 0
  is_active           BOOLEAN, DEFAULT TRUE, NOT NULL
  -- Notes
  internal_notes      TEXT, NULLABLE  -- tech-facing notes (e.g., "requires 24hr cure time")
  -- Audit
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP
  updated_by          INT UNSIGNED, FK -> users.id, NULLABLE

  FULLTEXT INDEX ft_price_item (name, description, code)
  INDEX idx_pli_category (category_id, sort_order)
  INDEX idx_pli_active (is_active)
  INDEX idx_pli_tier (price_tier)
```

```
price_list_item_parts (links a price list item to inventory parts it consumes)
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  price_list_item_id  INT UNSIGNED, FK -> price_list_items.id, NOT NULL (R)
  inventory_item_id   INT UNSIGNED, FK -> inventory_items.id, NOT NULL (R)
  quantity            DECIMAL(10,2), NOT NULL, DEFAULT 1 (R)
  notes               VARCHAR(255), NULLABLE  -- e.g., "size depends on measurement"
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  INDEX idx_plip_item (price_list_item_id)
  INDEX idx_plip_inv (inventory_item_id)
```

```
applied_services (links price list items to a service order item — the "line items" of work)
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  service_order_item_id INT UNSIGNED, FK -> service_order_items.id, NOT NULL (R)
  -- Source: either from price list or custom
  price_list_item_id  INT UNSIGNED, FK -> price_list_items.id, NULLABLE  -- NULL = custom/ad-hoc item
  -- Snapshot at time of application (so price changes don't affect past orders)
  service_name        VARCHAR(255), NOT NULL (R)
  service_description TEXT, NULLABLE
  -- Pricing
  quantity            DECIMAL(10,2), NOT NULL, DEFAULT 1 (R)
  unit_price          DECIMAL(10,2), NOT NULL (R)     -- price snapshot from price list, or manually entered
  discount_percent    DECIMAL(5,2), DEFAULT 0.00      -- per-line discount
  line_total          DECIMAL(10,2), NOT NULL (R)     -- (quantity * unit_price) * (1 - discount_percent/100)
  is_taxable          BOOLEAN, DEFAULT TRUE, NOT NULL
  -- Override flag
  price_overridden    BOOLEAN, DEFAULT FALSE  -- TRUE if tech manually changed price from list price
  -- Customer approval (per-service granularity)
  customer_approved   BOOLEAN, DEFAULT FALSE  -- customer approved this specific service/charge
  -- Notes
  notes               VARCHAR(500), NULLABLE
  -- Audit
  added_by            INT UNSIGNED, FK -> users.id, NULLABLE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL
  updated_at          DATETIME, ON UPDATE CURRENT_TIMESTAMP

  INDEX idx_as_order_item (service_order_item_id)
  INDEX idx_as_price_item (price_list_item_id)
```

**Default Price List Categories and Example Items** (seeded on first install, fully editable):

Based on industry-standard drysuit repair pricing (sources: DUI, Dive Right In Scuba, Drysuits Plus, Extreme Exposure, Paragon Dive Group, The Drysuit Lady):

| Category | Example Items | Typical Price Range |
|----------|--------------|-------------------|
| **Leak Testing / Diagnostics** | Basic leak test, Full diagnostic evaluation, Annual service (leak test + clean + valve check), Rush diagnostic (24-48hr) | $25 - $500 |
| **Seal Replacement — Glue-On** | Latex neck seal, Latex wrist seals (pair), Latex ankle seals (pair), Custom neoprene neck seal, Custom neoprene wrist seals (pair) | $110 - $200 |
| **Seal Replacement — Ring Systems** | SI Tech Quick Neck + latex, SI Tech Quick Neck + silicone, SI Tech wrist rings (pair) + latex, DUI ZipSeal neck, DUI ZipSeal wrist, Kubi dry glove system, SANTI Smart Seal | $286 - $490 |
| **Zipper Replacement** | YKK plastic zipper, YKK brass zipper, YKK heavy-duty metal, TiZip plastic, Relief/pee zipper (12"), Front-entry surcharge | $325 - $537 |
| **Valve Service / Installation** | SI Tech inflation valve, SI Tech exhaust valve, Apeks inflation valve, Apeks exhaust valve, Valve relocation, P-valve installation (customer valve), P-valve with valve (Halcyon/SI Tech/etc.) | $50 - $375 |
| **Boot / Sock Replacement** | Neoprene socks (pair), Vulcanized rubber boots (pair), Turbo/flex sole boots (pair), Boot labor only (customer-provided) | $175 - $650 |
| **Patching / Seam Repair** | Small patch (~3"), Large patch (4-5"), Additional patches (each), Full re-seam / re-tape | $19 - $350+ |
| **Accessories / Modifications** | Kevlar knee pads (pair), Pocket installation, Pocket removal, Suspender/brace install, Crotch strap, D-ring installation | $17 - $270 |
| **Neoprene Surcharges** | Neoprene-to-latex cuff changeover, Neoprene neck build-up, Neoprene hood build-up | $30 - $75 |
| **Service Plans / Packages** | Annual maintenance plan, Seal + leak test bundle, Full overhaul package | Configurable |

### 2.21 Invoice-Order Join Table

Enables many-to-many relationship between invoices and service orders. An invoice may cover multiple orders (e.g., combined billing), and an order may be split across multiple invoices (e.g., deposit invoice + final invoice).

```
invoice_orders
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  invoice_id          INT UNSIGNED, FK -> invoices.id, NOT NULL (R)
  order_id            INT UNSIGNED, FK -> service_orders.id, NOT NULL (R)
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  UNIQUE INDEX uq_invoice_order (invoice_id, order_id)
  INDEX idx_io_order (order_id)
```

### 2.22 Attachments (Polymorphic File Uploads)

Polymorphic file attachment system. Supports photos, documents, and other files attached to any entity (service items, service order items, service notes, etc.).

```
attachments
  id                  INT UNSIGNED, PK, AUTO_INCREMENT
  -- Polymorphic reference
  attachable_type     VARCHAR(50), NOT NULL (R)  -- 'service_item', 'service_order_item', 'service_note', 'invoice', etc.
  attachable_id       INT UNSIGNED, NOT NULL (R)
  -- File info
  filename            VARCHAR(255), NOT NULL (R)  -- original filename
  stored_filename     VARCHAR(255), NOT NULL (R)  -- unique filename on disk (UUID-based to avoid collisions)
  file_path           VARCHAR(500), NOT NULL (R)  -- relative path within uploads/attachments/
  file_size           INT UNSIGNED, NOT NULL       -- bytes
  mime_type           VARCHAR(100), NOT NULL (R)   -- e.g., "image/jpeg", "application/pdf"
  -- Metadata
  description         VARCHAR(500), NULLABLE
  -- Audit
  uploaded_by         INT UNSIGNED, FK -> users.id, NULLABLE
  created_at          DATETIME, DEFAULT CURRENT_TIMESTAMP, NOT NULL

  INDEX idx_attach_entity (attachable_type, attachable_id)
  INDEX idx_attach_type (mime_type)
```

**Upload constraints** (configurable via system config):
- Max file size: 16MB (default, matches `DSM_MAX_CONTENT_LENGTH`)
- Allowed MIME types: images (JPEG, PNG, GIF, WebP), documents (PDF), spreadsheets (CSV, XLSX)
- Files stored in `uploads/attachments/<attachable_type>/<year>/<month>/`

### Entity Relationship Summary

```
Customer 1 ---< ServiceOrder
Customer 1 ---< ServiceItem (ownership)
Customer 1 ---< Invoice
ServiceOrder >---< Invoice (via invoice_orders join table)
ServiceOrder 1 ---< ServiceOrderItem >--- 1 ServiceItem
ServiceItem 1 ---0..1 DrysuitDetails (1:1 extension, only for drysuit items)
ServiceOrderItem 1 ---< ServiceNote
ServiceOrderItem 1 ---< PartsUsed >--- 1 InventoryItem
PartsUsed 0..1 --- 0..1 AppliedService (if auto-deducted)
ServiceOrderItem 1 ---< LaborEntry
ServiceOrderItem 1 ---< AppliedService >---0..1 PriceListItem
PriceListCategory 1 ---< PriceListItem
PriceListItem 1 ---< PriceListItemParts >--- 1 InventoryItem
Invoice 1 ---< InvoiceLineItem
InvoiceLineItem >---0..1 AppliedService (traceability, line_type='service')
InvoiceLineItem >---0..1 LaborEntry (traceability, line_type='labor')
InvoiceLineItem >---0..1 PartsUsed (traceability, line_type='part')
Invoice 1 ---< Payment
Payment >---0..1 ServiceOrder (deposit payments, before invoice exists)
User 1 ---< ServiceOrder (assigned tech)
User 1 ---< LaborEntry (tech)
User 1 ---< ServiceNote (created_by)
Tag >---< Any Entity (via taggables polymorphic join)
Attachment >--- Any Entity (via attachable polymorphic reference)
```

---

## 3. UI / Page Structure

### 3.1 Global Layout (base template)

All pages share a common base template (`base.html`):

```
+------------------------------------------------------------------+
|  HEADER BAR: Logo | App Name | Search Bar | Notifications | User |
+----------+-------------------------------------------------------+
|          |  TAB BAR: [Tab1] [Tab2] [Tab3] [+]                     |
|  LEFT    +-------------------------------------------------------+
|  NAV     |                                                        |
|  MENU    |  MAIN CONTENT AREA                                     |
|          |  (data entry, tables, forms, dashboards)               |
|  - Dash  |                                                        |
|  - Cust  |                                                        |
|  - Orders|                                                        |
|  - Inv   |                                                        |
|  - Prices|                                                        |
|  - Invoic|                                                        |
|  - Report|                                                        |
|  - Tools |                                                        |
|  - Admin |                                                        |
|          |                                                        |
+----------+-------------------------------------------------------+
|  FOOTER: Version | Status indicators                              |
+------------------------------------------------------------------+
```

- **Left Nav Menu**: Collapsible sidebar. Active section highlighted. Icons + text labels. Collapses to icons-only on small screens.
- **Tab Bar**: Browser-like tabs for open work items. Allows having multiple orders, customers, etc. open simultaneously. Tabs persist in session. Implemented via HTMX + session storage. Each tab loads its content into the main content area.
- **Header**: Global search (searches across all entities), notification bell with unread count badge, user dropdown (profile, logout).
- **Theme**: Bootstrap 5 `data-bs-theme` attribute for dark/light mode toggle. Custom CSS variables for corporate branding. Logo uploaded via admin config.

### 3.2 Dashboard (`/dashboard`)

- **Summary Cards Row**: 
  - Open Service Orders count (with breakdown by status)
  - Items Awaiting Pickup count
  - Low Stock Alerts count (links to filtered inventory view)
  - Overdue Invoices count + total amount
  - Revenue this month
- **Recent Activity Feed**: Last 20 audit log entries (filterable by type)
- **My Assigned Orders** (for techs): Table of orders assigned to current user, sorted by priority then date
- **Upcoming Due Dates**: Orders approaching their promised date
- **Quick Actions**: Buttons for "New Service Order", "New Customer", "Quick Inventory Lookup"
- **Charts** (Chart.js):
  - Orders by status (doughnut chart)
  - Revenue trend (last 6 months, line chart)
  - Top repair types (bar chart)

### 3.3 Customer Management

**Customer List** (`/customers`)
- Searchable, sortable, paginated table
- Columns: Name/Business, Phone, Email, Open Orders, Last Visit, Balance Due, Tags
- Filters: customer type, has open orders, has balance due, tags, date range
- Bulk actions: export selected, tag selected
- "Add Customer" button opens form (inline or modal via HTMX)

**Customer Detail** (`/customers/<id>`)
- **Header section**: Name, contact info, tags, edit button
- **Tabs within customer view**:
  - **Overview**: Contact details, preferences, referral source, notes
  - **Service Orders**: Table of all orders for this customer (with status badges)
  - **Service Items**: All items owned by this customer (with serviceability indicators)
  - **Invoices**: Invoice history with status and balance
  - **Activity**: Audit log entries for this customer
- **Quick actions**: New Order (pre-fills customer), New Invoice, Edit, Archive

**Customer Form** (`/customers/new`, `/customers/<id>/edit`)
- Form sections: Contact Type toggle (Individual/Business), Contact Info, Address, Preferences, Notes, Tags
- HTMX form submission with validation feedback
- "Save and Add Order" shortcut button

### 3.4 Service Order Workflow

**Order List** (`/orders`)
- Kanban view toggle (cards by status column) OR table view toggle
- Table columns: Order #, Customer, Items, Status, Priority, Tech, Received, Promised, Est. Total
- Filters: status, priority, assigned tech, date range, tags, customer
- Color-coded priority and status badges
- Bulk status updates for selected orders

**Order Detail** (`/orders/<id>`)
- **Header**: Order #, status badge with dropdown to change status, priority badge, customer link, assigned tech
- **Info bar**: Date received, date promised (highlighted if overdue), estimated total
- **Service Items section**: 
  - List of items on this order, each expandable
  - "Add Item" button: Search by serial number (HTMX autocomplete). If found, shows history. If not found, prompts to create new item.
  - For each item:
    - Item details summary (name, serial, serviceability)
    - Work description for this order
    - Diagnosis field
    - **Applied Services** (primary way to add work to an order):
      - Table showing services applied to this item, with columns: Service, Qty, Unit Price, Discount, Line Total, Actions
      - **"Add Service" button** opens a searchable price list picker (Tom Select, grouped by category). Selecting an item auto-fills name, description, quantity, and price from the price list. Quantity and price are editable (override flag set if price changed).
      - **"Add Custom Item" button** for non-price-list work — opens a blank row where tech enters name, description, quantity, and price manually. `price_list_item_id` is NULL for these.
      - Per-line discount field (percent) for negotiated pricing
      - If a price list item has `auto_deduct_parts = TRUE` with linked inventory parts, those parts are automatically added to the Parts Used table when the service is applied (tech can adjust)
      - Running subtotal of applied services shown below the table
    - **Parts Used**: Table with add/remove. Part picker uses Tom Select searchable dropdown from inventory. Shows current stock. Quantity field. Auto-calculates line cost. Can add new inventory item inline. (Parts may also be auto-populated from applied services with linked inventory items.)
    - **Labor Entries**: Table with add/remove. Tech (auto-fills current user), hours, rate (from config default, editable), description, date. (Note: for flat-rate price list services, labor is bundled into the service price and separate labor entries are optional — used only for internal tracking or for custom work not covered by the price list.)
    - **Service Notes**: Chronological list of dated, tech-attributed notes. Add note form at bottom with type selector.
- **Order Summary sidebar**:
  - Applied services total
  - Additional parts total (parts not covered by applied services)
  - Additional labor total (labor not covered by applied services)
  - Fees (rush fee, etc.)
  - Discounts
  - Estimated total
  - "Generate Invoice" button
- **Order timeline**: Visual timeline of status changes with timestamps and who changed them

**Order Form** (`/orders/new`, `/orders/<id>/edit`)
- Customer picker (Tom Select, searchable, can create new inline)
- Priority selector
- Description field
- Date received (auto-fills today), promised date
- Assigned tech selector
- After save, redirects to order detail to add items

### 3.5 Service Item Pages

**Item Lookup** (`/items/lookup`)
- Single search bar focused on serial number lookup
- On enter: if found, shows item detail with full history. If not found, offers to create.
- This is the primary entry point for techs receiving equipment.

**Item Detail** (`/items/<id>`)
- **Header**: Name, serial, serviceability badge, customer link
- **Details section**: All drysuit-specific fields displayed in organized groups (Suit Info, Seals, Zipper, Valves, Boots)
- **Service History**: Chronological list of all service orders this item has been on, with dates, work performed, notes
- **Tags**
- **Edit button** opens form with all fields

### 3.6 Inventory Management

**Inventory List** (`/inventory`)
- Searchable, sortable, paginated table
- Columns: SKU, Name, Category, In Stock, Reorder Level, Purchase Cost, Resale Price, Location, Status
- Filters: category, subcategory, low stock only, active/inactive, for resale
- Stock level visual indicators (green/yellow/red based on reorder level)
- Bulk actions: export, adjust stock, update prices

**Inventory Detail** (`/inventory/<id>`)
- All fields displayed
- **Stock adjustment**: Quick +/- buttons with reason tracking
- **Usage history**: Where this part has been used (links to service orders)
- **Price history**: Chart showing cost/price changes over time (from audit log)

**Inventory Form** (`/inventory/new`, `/inventory/<id>/edit`)
- Category/subcategory selectors (with ability to add new categories)
- All fields organized in logical groups
- Custom fields editor (key-value pair interface)

**Low Stock Report** (`/inventory/low-stock`)
- Filtered view showing only items below reorder level
- Columns include suggested reorder quantity and estimated cost
- "Generate Purchase Order" future feature placeholder

### 3.7 Invoice / Billing Pages

**Invoice List** (`/invoices`)
- Table with: Invoice #, Customer, Issue Date, Due Date, Total, Paid, Balance, Status
- Filters: status, date range, customer, overdue only
- Status badge colors: draft=gray, sent=blue, overdue=red, paid=green, void=strikethrough

**Invoice Detail** (`/invoices/<id>`)
- Print-ready layout (also serves as PDF template)
- Company header (logo, address, phone -- from system config)
- Customer billing info
- Line items table: Description, Qty, Unit Price, Total
- Subtotal, tax, discount, total, amount paid, balance due
- Payment records section
- Actions: Mark as Sent, Record Payment, Void, Print, Download PDF, Email (future)
- Status change buttons contextual to current status

**Invoice Generation** (`/orders/<id>/generate-invoice`)
- Pre-populated from service order data. Line items are generated from three sources in this priority:
  1. **Applied services** — each `applied_services` row becomes an invoice line item (type: `service`), with price snapshot preserved. This is the primary source for flat-rate priced work.
  2. **Additional parts used** — parts in `parts_used` that are NOT already covered by an applied service's auto-deducted parts become invoice line items (type: `part`).
  3. **Additional labor entries** — labor in `labor_entries` that represents work beyond what's bundled in applied services becomes invoice line items (type: `labor`).
- Review screen groups line items by service item, showing the source of each line (price list service, manual part, manual labor)
- All line items are editable before final generation (add/remove/modify line items, add custom ad-hoc lines)
- Per-line taxable flag inherited from the applied service / price list item
- Tax rate from system config (editable per invoice)
- Terms from system config (editable per invoice)
- Customer notes field

**Billing Search** (`/billing/search`)
- Dedicated search page for billing/financial queries
- Search by: invoice number, customer name, date range, amount range, status
- Results show invoice details with payment history
- Summary totals at bottom of results

### 3.8 Reports Section

**Reports Hub** (`/reports`)
- Card-based layout with report categories
- Each card shows report name, description, and icon

Individual report pages described in Section 11.

### 3.9 Tools Section

**Tools Hub** (`/tools`)
- Grid of available tools with icons and descriptions

Individual tools described in Section 12.

### 3.10 Price List Management

**Price List** (`/price-list`) — Accessible to all roles (view), editable by Admin and Technician

The price list is a first-class section in the left nav, not buried in admin settings, because techs reference it constantly when building orders.

- Organized by category with collapsible sections (accordion)
- Each category shows its items in a table: Code, Service Name, Price, Unit, Tier, Active, Actions
- Search bar filters across all categories in real time (HTMX)
- "Print Price List" button generates a customer-facing PDF (via fpdf2) with company logo, suitable for posting in-shop or emailing. Inactive items and internal notes are excluded from the printable version.
- "Export Price List" button — CSV/XLSX/JSON/PDF

**Price List Item Detail/Edit** (`/price-list/<id>/edit`) — Admin only for price changes; Technician can view

- All fields from the `price_list_items` model
- **Linked Inventory Parts** section: Table of parts auto-deducted when this service is applied. Add/remove parts with quantity. Shows current stock level for each linked part.
- Price history (from audit log) showing when prices were last changed and by whom
- "Duplicate" button to quickly create a variant (e.g., duplicate "Latex Neck Seal" to create "Silicone Neck Seal" with different price)

**Price List Category Management** (`/price-list/categories`) — Admin only

- Reorderable list of categories (drag-and-drop via HTMX sortable, or up/down buttons)
- Add/edit/deactivate categories
- Deactivating a category hides all its items from the picker but preserves historical data

**Applying Services on the Order Detail page** (see Section 3.4):

- When a tech clicks "Add Service" on a service order item, an HTMX-driven modal/dropdown shows the price list grouped by category
- Tom Select searchable picker with category grouping — typing filters by name, code, or description
- Selecting an item populates the applied service row with snapshot values
- "Add Custom Item" adds a blank row for ad-hoc / non-price-list charges (e.g., unusual repair, custom fabrication, third-party subcontracted work)
- Both price list and custom items appear in the same applied services table and flow identically into invoice generation

### 3.11 Admin / Configuration Pages

**Admin Hub** (`/admin`) -- Admin role required

- **User Management** (`/admin/users`)
  - User list with roles, status, last login
  - Create/edit user form with role assignment
  - Deactivate/reactivate users
  - Password reset

- **Company Settings** (`/admin/settings/company`)
  - Company name, address, phone, email
  - Logo upload
  - Tax rate(s)
  - Default payment terms

- **Price List Settings** (`/admin/settings/price-list`)
  - Enable/disable price list feature globally
  - Default markup percent for new price list items
  - Whether to show prices on customer-facing documents (some shops prefer "call for quote")
  - Import/export entire price list (CSV/JSON) for bulk updates or migration between installations

- **Service Settings** (`/admin/settings/service`)
  - Default labor rate
  - Order number format/prefix
  - Invoice number format/prefix
  - Status workflow customization (which statuses are enabled)
  - Default priority

- **Inventory Settings** (`/admin/settings/inventory`)
  - Default categories and subcategories management
  - Low stock notification threshold defaults
  - Unit of measure options management

- **Display Settings** (`/admin/settings/display`)
  - Theme selection (dark/light/auto)
  - Custom CSS override
  - Logo position and size
  - Date format preference
  - Currency symbol and format
  - Pagination default page size

- **Notification Settings** (`/admin/settings/notifications`)
  - Enable/disable notification types
  - Low stock check frequency
  - Overdue invoice check frequency
  - Notification retention period

- **Data Management** (`/admin/data`)
  - One-click database backup download (via mariadb-dump)
  - Live database statistics (table sizes, row counts, DB version)
  - Migration status (current revision, pending migrations)
  - Export all data (CSV/XLSX format selector)
  - Simplified CSV import for customers and inventory (fixed column order, preview + confirm)
  - *Future*: Import with column mapping wizard (drag-and-drop mapping for arbitrary CSV/XLSX)
  - *Future*: Audit log viewer with filters (requires AuditLog model from section 2.15)
  - *Future*: Generalized logging access (login/logout events, notification history, app logs, Docker logs)

- **Integration Settings** (`/admin/settings/integrations`) -- Placeholder for future
  - QuickBooks connection settings
  - Stripe API keys
  - Email service configuration (SMTP)

---

## 4. Authentication and Authorization

### 4.1 Authentication

- Implemented via Flask-Security-Too (wraps Flask-Login)
- Password hashing: argon2 (via `argon2-cffi`)
- Session-based auth (no JWT needed for server-rendered app)
- Session stored in Redis for horizontal scalability
- Login page at `/login`
- "Remember me" functionality (configurable duration)
- Password complexity requirements configurable via system config
- Account lockout after N failed attempts (configurable, default: 5 attempts, 15 minute lockout)
- All password-related routes served over HTTPS (enforced in production via Nginx)

### 4.2 Roles

Three default roles:

| Role | Description |
|------|-------------|
| **admin** | Full system access. Can manage users, configuration, delete records, view audit logs, access all reports. |
| **technician** | Can create/edit customers, orders, items, inventory. Can generate invoices. Can view reports relevant to their work. Cannot manage users or system config. |
| **viewer** | Read-only access to customers, orders, items, inventory, invoices. Can run reports and exports. Cannot create or modify records. |

### 4.3 Permission Matrix

| Action | Admin | Technician | Viewer |
|--------|:-----:|:----------:|:------:|
| View dashboard | Yes | Yes | Yes |
| Create/edit customer | Yes | Yes | No |
| Delete/archive customer | Yes | No | No |
| Create/edit service order | Yes | Yes | No |
| Change order status | Yes | Yes | No |
| Delete order | Yes | No | No |
| Create/edit service item | Yes | Yes | No |
| Change serviceability | Yes | Yes | No |
| Delete service item | Yes | No | No |
| Add service notes | Yes | Yes | No |
| Create/edit inventory | Yes | Yes | No |
| Adjust stock levels | Yes | Yes | No |
| Delete inventory item | Yes | No | No |
| Generate invoice | Yes | Yes | No |
| Edit invoice | Yes | Yes (own) | No |
| Void invoice | Yes | No | No |
| Record payment | Yes | Yes | No |
| View reports | Yes | Yes | Yes |
| Export data | Yes | Yes | Yes |
| Import data | Yes | No | No |
| Manage users | Yes | No | No |
| System configuration | Yes | No | No |
| View audit log | Yes | No | No |
| View price list | Yes | Yes | Yes |
| Apply services from price list | Yes | Yes | No |
| Add custom (non-price-list) items | Yes | Yes | No |
| Edit price list items/categories | Yes | No | No |
| Override price on applied service | Yes | Yes | No |
| Print/export price list | Yes | Yes | Yes |
| Manage tags | Yes | Yes | No |
| Upload/view attachments | Yes | Yes | Yes (view) |
| Delete attachments | Yes | No | No |
| Record deposit payment | Yes | Yes | No |
| Override do-not-service flag | Yes | No | No |

### 4.4 Implementation

- Permissions enforced via decorators: `@roles_required('admin')`, `@roles_accepted('admin', 'technician')`
- Custom permission decorator for fine-grained checks: `@permission_required('invoice.void')`
- Jinja2 template helpers for conditional UI rendering: `{% if current_user.has_role('admin') %}`
- All authorization failures return 403 with a user-friendly error page
- API endpoints (for HTMX) return 403 status which HTMX can handle with `hx-on::response-error`

---

## 5. Search and Indexing

### 5.1 Full-Text Search Strategy

MariaDB InnoDB FULLTEXT indexes on key text columns (as defined in the data model above).

**Global search bar** (in header):
- Searches across: customers (name, business, email, phone), service orders (order number, description), service items (name, serial, brand, model), inventory items (name, SKU, description), invoices (invoice number)
- Implemented as a single HTMX endpoint (`/search`) that queries multiple tables and returns a categorized dropdown of results
- Results grouped by entity type with icons
- Debounced input (300ms) via HTMX `hx-trigger="keyup changed delay:300ms"`
- Minimum 2 characters to trigger search
- Clicking a result navigates to the entity detail page (or opens in a new tab)

### 5.2 MariaDB FULLTEXT Configuration

```sql
-- Set minimum word length to 2 for short part numbers and codes
SET GLOBAL innodb_ft_min_token_size = 2;
-- Custom stopword table (reduce default stopwords that may be meaningful)
-- Applied via Alembic migration
```

### 5.3 Per-Entity Search

Each entity list page has its own search bar that uses FULLTEXT search on that entity's indexed columns. Additionally, structured filters (dropdowns, date ranges, checkboxes) can be combined with text search.

### 5.4 Tag-Based Search

- Tags are searchable and filterable on all entity list pages
- Tag filter is a multi-select dropdown: selecting tags shows entities that have ANY of the selected tags (OR logic), with toggle for ALL (AND logic)
- Tags are auto-suggested as user types (HTMX autocomplete from `/api/tags/suggest?q=`)
- Clicking a tag anywhere in the UI filters the current list by that tag

### 5.5 Saved Searches (Implemented)

- Users can save their current filter combination as a named saved search
- Saved searches appear in a dropdown on the entity list page via reusable Jinja macro
- Per-user, per-entity-type JSON filter storage with full CRUD API
- `SavedSearch` model with Alembic migration `g7b8c9d0e1f2`

### 5.6 Dedicated Billing Search

A specialized search page (`/billing/search`) with fields specifically designed for financial queries:
- Invoice number (exact or partial match)
- Customer name/business
- Date range (issue date, due date, paid date)
- Amount range (min/max)
- Status filter
- Payment method filter
- Overdue only toggle
- Results include running totals of amount billed, paid, and outstanding

---

## 6. Import / Export

### 6.1 Export Formats and What is Exportable

| Entity | CSV | XLSX | JSON | PDF |
|--------|:---:|:----:|:----:|:---:|
| Customer list | Yes | Yes | Yes | Yes |
| Service orders | Yes | Yes | Yes | Yes |
| Service order detail (single) | No | No | Yes | Yes |
| Service items | Yes | Yes | Yes | No |
| Inventory items | Yes | Yes | Yes | Yes |
| Invoices (list) | Yes | Yes | Yes | No |
| Invoice (single) | No | No | Yes | Yes |
| Billing/payment report | Yes | Yes | Yes | Yes |
| Price list | Yes | Yes | Yes | Yes |
| Audit log | Yes | Yes | Yes | No |
| All reports | Yes | Yes | No | Yes |

### 6.2 Export Implementation

- Export triggered from list pages via "Export" button with format selector dropdown
- Export respects current filters (exports what is currently displayed/filtered)
- Large exports (>1000 records) run as background Celery tasks with download notification when complete
- CSV: Python `csv` module, UTF-8 with BOM for Excel compatibility
- XLSX: `openpyxl` with styled headers, auto-column-widths, data type formatting
- JSON: `Marshmallow` schemas for clean serialization, pretty-printed, includes metadata header
- PDF: `fpdf2` for invoices, price lists, and tabular reports (lightweight, no system dependencies). `WeasyPrint` available as optional backend for complex HTML-to-PDF rendering (styled reports, custom layouts). The PDF utility layer (`app/utils/pdf.py`) abstracts the backend so either can be used based on configuration.

### 6.3 Import Implementation

- Import available from Admin > Data Management and from individual entity list pages (Admin/Technician roles)
- Supported import formats: CSV, JSON, XLSX
- Import workflow:
  1. Upload file
  2. System auto-detects columns and shows mapping interface (HTMX-driven)
  3. User maps source columns to destination fields
  4. Preview shows first 10 rows with validation results
  5. User confirms import
  6. Import runs as Celery task for large files (>100 records)
  7. Results page shows: imported count, skipped count, error details with row numbers
- Duplicate handling: configurable per import (skip, update, or flag for review)
- Validation: same validators as the web forms (WTForms validators applied to import data)

### 6.4 Specific Export Types

- **Invoice PDF**: Formatted, print-ready document with company letterhead, line items, totals. Suitable for giving to customers.
- **Customer export**: All customer fields plus summary stats (order count, lifetime value, last visit date)
- **Service order export**: Order details with all items, parts used, labor, totals
- **Inventory export**: All inventory fields plus usage stats (units used this month/quarter/year)
- **Billing export**: Designed for accountant/bookkeeper use. Includes all invoices with line items, payments, aging data.

---

## 7. Notification System

### 7.1 Notification Types

| Notification | Trigger | Severity | Recipients |
|-------------|---------|----------|------------|
| Low Stock Alert | Stock falls below reorder_level | warning | Admin, assigned techs |
| Critical Stock (zero) | Stock reaches 0 | critical | Admin |
| Overdue Invoice | Invoice due_date passes without full payment | warning | Admin |
| Order Status Change | Status updated on any order | info | Assigned tech, Admin |
| Order Approaching Due | 2 days before promised date, order not completed | warning | Assigned tech |
| Order Overdue | Promised date passed, order not completed | critical | Admin, assigned tech |
| New Order Assigned | Order assigned to a tech | info | Assigned tech |
| Item Serviceability Change | Item marked non-serviceable | warning | Admin |
| Payment Received | Payment recorded on invoice | info | Admin |
| Inventory Expiring | Item expiration_date within 30 days | warning | Admin, assigned techs |
| Warranty Expiring | Service order item warranty_end_date within 30 days | info | Admin |
| Deposit Received | Deposit payment recorded against a service order | info | Admin, assigned tech |
| Do Not Service Override | Order created for customer with do_not_service flag | critical | Admin |
| System Backup Reminder | Weekly backup not detected | critical | Admin |

### 7.2 Notification Delivery

- **In-app notifications**: Stored in `notifications` table, shown via bell icon in header with unread count badge
- Notification dropdown (HTMX-loaded) shows latest 20 notifications
- Full notification list page at `/notifications`
- Mark as read individually or "mark all read"
- Notifications link to the relevant entity when clicked
- **Scheduled checks**: Celery Beat runs periodic tasks:
  - Low stock check: every 6 hours (configurable)
  - Overdue invoice check: daily at 8:00 AM (configurable)
  - Order approaching due: daily at 8:00 AM
- **Email notifications**: SMTP-based delivery via `email_service.py`, reads config from SystemConfig at send-time, Celery async delivery. SMTP settings editable from admin UI.

### 7.3 Implementation

- `NotificationService` class handles creation and delivery
- Celery tasks for scheduled checks
- HTMX polling on the notification badge: `hx-get="/api/notifications/count" hx-trigger="every 60s"` to update unread count
- Notifications auto-expire after configurable retention period (default: 90 days)

---

## 8. Docker Architecture

### 8.1 Container Definitions

Five containers orchestrated via Docker Compose (three in lightweight Pi profile):

**1. `dsm-web` (Application Container)**
- Base image: `python:3.12-slim` (multi-arch: amd64, arm64)
- Runs: Gunicorn with Flask app, via `docker-entrypoint.sh`
- **Entrypoint** (`docker-entrypoint.sh`): On startup, if the process is gunicorn, automatically runs `flask db upgrade` (applies any pending migrations) and `flask seed-db` (ensures roles, categories, and defaults exist) before starting the server. Worker and beat containers skip this step.
- Exposes: port 8080 (configurable)
- Volumes:
  - `./uploads:/app/uploads` (uploaded logos, import files)
  - `./logs:/app/logs` (application logs)
  - `./instance:/app/instance` (Flask instance folder for local config overrides)
- Environment variables for all configuration (see Section 9)
- Health check: `curl -f http://localhost:8080/health || exit 1`
- Resource limits (recommended for Pi): `mem_limit: 512m`

**2. `dsm-db` (Database Container)**
- Base image: `mariadb:11-lts` (multi-arch: amd64, arm64)
- Exposes: port 3306 (configurable, default not exposed to host; only on internal network)
- Volumes:
  - `dsm-db-data:/var/lib/mysql` (named volume for persistence)
  - `./docker/db/init:/docker-entrypoint-initdb.d` (initialization scripts)
  - `./docker/db/conf:/etc/mysql/conf.d` (custom MariaDB config)
- Environment variables: `MARIADB_ROOT_PASSWORD`, `MARIADB_DATABASE`, `MARIADB_USER`, `MARIADB_PASSWORD`
- Health check: `healthcheck --connect --innodb_initialized` (mariadb-healthcheck)
- Resource limits (recommended for Pi): `mem_limit: 512m`
- Custom MariaDB config for InnoDB FULLTEXT: `innodb_ft_min_token_size=2`

**3. `dsm-redis` (Cache/Queue Container)**
- Base image: `redis:7-alpine` (multi-arch: amd64, arm64)
- Exposes: port 6379 (internal only)
- Volumes: `dsm-redis-data:/data` (optional persistence)
- Resource limits: `mem_limit: 128m`
- Config: `maxmemory 100mb`, `maxmemory-policy allkeys-lru`

**4. `dsm-worker` (Celery Worker Container) -- uses same image as dsm-web**
- Runs: `celery -A app.celery worker --loglevel=info --concurrency=2`
- No port exposure
- Shares same environment variables as dsm-web
- Resource limits: `mem_limit: 256m`

**5. `dsm-beat` (Celery Beat Container) -- uses same image as dsm-web**
- Runs: `celery -A app.celery beat --loglevel=info`
- No port exposure
- Resource limits: `mem_limit: 128m`

### 8.2 Hard Constraints: Data Persistence and Upgrades

These are non-negotiable requirements for the production deployment:

1. **Database persistence**: The production database MUST use a named Docker volume (`dsm-db-data`) so that all data survives container restarts, host reboots, and image rebuilds. User-created data (customers, orders, invoices, users) must never be lost due to routine container operations.

2. **Upload/file persistence**: All user-uploaded files (logos, imports, exports, attachments) MUST be stored on bind-mounted host directories (`./uploads/`, `./logs/`, `./instance/`) that persist independently of the container lifecycle.

3. **Automatic schema migration on startup**: The web container's entrypoint script (`docker-entrypoint.sh`) MUST run `flask db upgrade` before starting the application server. This ensures that when the application code is updated (e.g., `docker compose pull && docker compose up -d`), any new Alembic migration scripts are applied automatically without manual intervention. The application must be able to detect that the database schema is from a prior version and upgrade to the current version.

4. **Automatic seeding on startup**: The entrypoint MUST also run `flask seed-db` to ensure required reference data (roles, price list categories) exists. The seed command must be idempotent — it skips records that already exist.

5. **Migration-only for schema changes**: Every database schema change MUST be accompanied by an Alembic migration script. Direct DDL changes against production are not permitted. The migration chain must be linear and unbroken so that `flask db upgrade` can always advance from any prior state to HEAD.

6. **UAT environment is ephemeral**: The UAT compose (`docker-compose.uat.yml`) intentionally uses `tmpfs` for the database — it gets a fresh copy each time. UAT is for testing only; production data lives exclusively in the production compose.

7. **Graceful migration failures**: If `flask db upgrade` fails on startup (e.g., due to a corrupt migration chain), the entrypoint logs a warning but still attempts to start the application. This allows debugging access via the running container rather than a crash loop.

### 8.3 Docker Compose Configuration

```yaml
# docker-compose.yml structure
version: '3.8'

services:
  web:
    build: .
    image: dsm-web:latest
    ports:
      - "${DSM_PORT:-8080}:8080"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    env_file: .env
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
      - ./instance:/app/instance
    restart: unless-stopped
    networks:
      - dsm-net

  db:
    image: mariadb:11-lts
    volumes:
      - dsm-db-data:/var/lib/mysql
      - ./docker/db/init:/docker-entrypoint-initdb.d
      - ./docker/db/conf:/etc/mysql/conf.d
    env_file: .env
    restart: unless-stopped
    networks:
      - dsm-net
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - dsm-redis-data:/data
    restart: unless-stopped
    networks:
      - dsm-net

  worker:
    build: .
    image: dsm-web:latest
    command: celery -A app.celery_app worker --loglevel=info --concurrency=2
    depends_on:
      - db
      - redis
    env_file: .env
    restart: unless-stopped
    networks:
      - dsm-net

  beat:
    build: .
    image: dsm-web:latest
    command: celery -A app.celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule
    depends_on:
      - redis
    env_file: .env
    restart: unless-stopped
    networks:
      - dsm-net

volumes:
  dsm-db-data:
  dsm-redis-data:

networks:
  dsm-net:
    driver: bridge
```

### 8.4 ARM/x86 Compatibility

- All base images (`python:3.12-slim`, `mariadb:11-lts`, `redis:7-alpine`) provide multi-architecture images supporting both `linux/amd64` and `linux/arm64`
- The application Dockerfile uses no architecture-specific dependencies
- `mysqlclient` compiles from source against the target architecture (build dependencies included in Dockerfile: `default-libmysqlclient-dev`, `build-essential`)
- fpdf2 is a pure-Python library with no system dependencies — works identically on both architectures with no special build steps
- WeasyPrint (optional) requires system dependencies (`libpango-1.0-0`, `libpangocairo-1.0-0`, etc.) which are available on both architectures via apt but add ~150MB to the image and are slow to install on ARM64. For lightweight Pi deployments, omit WeasyPrint and use fpdf2 exclusively.
- Build for specific platform: `docker compose build --platform linux/arm64`
- Multi-arch build for registry: `docker buildx build --platform linux/amd64,linux/arm64 -t dsm-web:latest .`

### 8.5 Networking

- All containers share `dsm-net` bridge network
- Only `dsm-web` port is exposed to host (configurable via `DSM_PORT` env var)
- For remote database: set `DSM_DATABASE_URL` environment variable to point to external host, and either remove or do not start the `db` service
- Network adapter binding: Gunicorn binds to `0.0.0.0:8080` inside container; Docker `-p` flag controls host binding (e.g., `-p 192.168.1.100:8080:8080` to bind to specific adapter)
- Docker Compose `ports` syntax: `"${DSM_BIND_ADDRESS:-0.0.0.0}:${DSM_PORT:-8080}:8080"`

### 8.6 Dockerfile

```dockerfile
# Multi-stage build
FROM python:3.12-slim AS base

# System dependencies for mysqlclient (required) and WeasyPrint (optional)
# For lightweight Pi deployments, remove the WeasyPrint deps (libpango, libcairo, etc.)
# and use fpdf2 exclusively for PDF generation.
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    libffi-dev \
    curl \
    # WeasyPrint dependencies (optional — remove for lightweight builds)
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create non-root user
RUN useradd -m -r dsm && chown -R dsm:dsm /app
USER dsm

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run migrations and seed on startup, then start gunicorn
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "app:create_app()"]
```

### 8.7 Lightweight Deployment Profile (Pi-Optimized)

A `docker-compose.lightweight.yml` override file provides a reduced-resource configuration for Raspberry Pi:

- **Task queue**: Uses Huey with Redis backend instead of Celery. Single process replaces both worker and beat containers.
- **PDF engine**: Uses fpdf2 only (no WeasyPrint). Dockerfile omits Pango/Cairo system dependencies (~150MB smaller image).
- **Container count**: 3 instead of 5 (web, db, redis — Huey runs inside the web process).
- **Estimated RAM**: ~400-500MB total (vs. ~700-900MB with full Celery stack).

Usage: `docker compose -f docker-compose.yml -f docker-compose.lightweight.yml up -d`

The setup script auto-detects Pi hardware and offers the lightweight profile during first-time setup.

### 8.8 Deployment Script and First-Time Setup

A single interactive setup script (`scripts/setup.sh`) handles first-time installation on a fresh host. The goal is: clone the repo, run one script, answer a few prompts, and the system is running.

**`scripts/setup.sh`** — Idempotent (safe to re-run):

```bash
#!/usr/bin/env bash
# Dive Service Management — First-Time Setup
# Supports: Raspberry Pi OS (Debian/ARM64), Ubuntu/Debian (x86-64), Windows WSL2
# Usage: ./scripts/setup.sh [--non-interactive]
```

**What it does, step by step:**

1. **Pre-flight checks**
   - Detects OS and architecture (ARM64 vs x86-64)
   - Checks for Docker and Docker Compose; if missing, offers to install via official Docker convenience script (`get.docker.com`) or prints manual instructions
   - Checks for `git` (already present if they cloned the repo)
   - Verifies minimum resources (disk space, memory) and warns if below recommended thresholds (1GB RAM, 4GB disk)

2. **Generate configuration**
   - If `.env` does not exist, copies `.env.example` to `.env`
   - Generates a cryptographically secure `DSM_SECRET_KEY` (via `python3 -c "import secrets; print(secrets.token_hex(32))"` or `openssl rand -hex 32`)
   - Generates a secure random `MARIADB_ROOT_PASSWORD` and `MARIADB_PASSWORD`
   - Prompts for (or uses defaults in `--non-interactive` mode):
     - Application port (`DSM_PORT`, default: 8080)
     - Bind address (`DSM_BIND_ADDRESS`, default: 0.0.0.0)
     - Company name (stored in DB config on first boot, default: "Dive Service Management")
   - Writes all values into `.env`
   - If `.env` already exists, skips generation and prints "Using existing .env"

3. **Create required directories**
   - `uploads/logos/`, `uploads/imports/`, `uploads/exports/`
   - `logs/`
   - `instance/`
   - Sets appropriate permissions

4. **Build and start containers**
   - `docker compose build` (builds the application image)
   - `docker compose up -d` (starts all 5 services in detached mode)
   - Waits for health checks to pass (polls `docker compose ps` with timeout)
   - Prints status of each container

5. **Run database migrations**
   - `docker compose exec web flask db upgrade` (Alembic migrations)
   - On first run, this creates all tables from scratch

6. **Seed initial data**
   - `docker compose exec web flask seed-db` — populates:
     - Default roles (admin, technician, viewer)
     - Default system configuration values
     - Default price list categories and example service items (drysuit repair pricing)
     - Default inventory categories
   - Skips if data already exists (idempotent)

7. **Create admin user**
   - Prompts for admin username, email, and password (or uses defaults in `--non-interactive`: admin/admin@localhost/changeme)
   - `docker compose exec web flask create-admin --username <user> --email <email> --password <pass>`
   - Skips if an admin user already exists

8. **Print summary**
   - Access URL: `http://<detected-ip>:<port>`
   - Admin credentials reminder
   - Next steps: change default password, upload company logo, review price list, configure tax rate
   - Location of logs, config, and backup scripts

**`--non-interactive` flag**: Uses all defaults, no prompts. Useful for scripted/automated deployments and CI.

**`scripts/setup.sh` also supports these subcommands for day-2 operations:**

| Command | Description |
| --- | --- |
| `./scripts/setup.sh` | Full first-time setup (default) |
| `./scripts/setup.sh upgrade` | Pull latest code, rebuild images, run migrations, restart |
| `./scripts/setup.sh status` | Show container status, disk usage, DB size, last backup time |
| `./scripts/setup.sh backup` | Run database backup to `backups/` directory with timestamped filename |
| `./scripts/setup.sh restore <file>` | Restore database from a backup file |
| `./scripts/setup.sh reset` | Stop containers, drop DB, re-run full setup (with confirmation prompt) |
| `./scripts/setup.sh logs` | Tail live application logs (all containers) |
| `./scripts/setup.sh stop` | Stop all containers |
| `./scripts/setup.sh start` | Start all containers |

**Makefile** shortcuts (for developers who prefer `make`):

```makefile
build:          docker compose build
up:             docker compose up -d
down:           docker compose down
logs:           docker compose logs -f
shell:          docker compose exec web bash
flask-shell:    docker compose exec web flask shell
migrate:        docker compose exec web flask db migrate -m "$(msg)"
upgrade:        docker compose exec web flask db upgrade
seed:           docker compose exec web flask seed-db
create-admin:   docker compose exec web flask create-admin
test:           docker compose exec web pytest
test-smoke:     docker compose exec web pytest tests/smoke/ -x
test-unit:      docker compose exec web pytest tests/unit/ -x --tb=short
test-blueprint: docker compose exec web pytest tests/blueprint/ -x --tb=short
test-validation:docker compose exec web pytest tests/validation/ -v --tb=long
test-fast:      docker compose exec web pytest tests/smoke/ tests/unit/ -x --tb=short
test-cov:       docker compose exec web pytest --cov=app --cov-report=term-missing --cov-report=html
test-failed:    docker compose exec web pytest --lf --tb=long
backup:         ./scripts/backup.sh
setup:          ./scripts/setup.sh
```

**Updated `scripts/` directory:**

```
scripts/
|-- setup.sh                  # Main setup/management script (see above)
|-- backup.sh                 # Database backup (called by setup.sh backup)
|-- restore.sh                # Database restore (called by setup.sh restore)
|-- generate_secret_key.py    # Standalone secret key generator
|-- healthcheck.sh            # Container health check helper
```

---

## 9. Configuration System

### 9.1 Configuration Hierarchy (highest priority wins)

1. **Environment variables** (highest priority -- used for secrets and deployment config)
2. **Instance config file** (`instance/config.py` -- local overrides, not committed to version control)
3. **Database system_config table** (runtime-changeable settings via admin UI)
4. **Application defaults** (in `config.py` -- committed to version control)

### 9.2 Environment Variables

All prefixed with `DSM_` for namespacing.

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_SECRET_KEY` | (required) | Flask secret key for sessions/CSRF |
| `DSM_DATABASE_URL` | `mysql+mysqldb://dsm:dsm@db:3306/dsm` | SQLAlchemy database URI |
| `DSM_REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `DSM_PORT` | `8080` | Application port |
| `DSM_BIND_ADDRESS` | `0.0.0.0` | Network adapter to bind to |
| `DSM_DEBUG` | `false` | Enable debug mode (never in production) |
| `DSM_LOG_LEVEL` | `INFO` | Logging level |
| `DSM_WORKERS` | `2` | Gunicorn worker count |
| `DSM_THREADS` | `4` | Gunicorn threads per worker |
| `MARIADB_ROOT_PASSWORD` | (required) | MariaDB root password |
| `MARIADB_DATABASE` | `dsm` | Database name |
| `MARIADB_USER` | `dsm` | Database user |
| `MARIADB_PASSWORD` | (required) | Database password |
| `DSM_CELERY_BROKER_URL` | `redis://redis:6379/1` | Celery broker URL |
| `DSM_CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | Celery result backend |
| `DSM_UPLOAD_FOLDER` | `/app/uploads` | File upload directory |
| `DSM_MAX_CONTENT_LENGTH` | `16777216` | Max upload size (16MB) |

### 9.3 Database-Stored Configuration (editable via Admin UI)

> **Implementation status**: Complete. The `system_config` table, `config_service.py`, and tabbed settings UI at `/admin/settings` are fully implemented (Admin Overhaul PRs #19-#23). All entries below are editable from the admin UI. Settings controlled by environment variables (e.g., `DSM_SECRET_KEY`, `DSM_DATABASE_URL`) are shown as read-only with an explanation that they are ENV-locked. The admin audit log viewer at `/admin/audit` displays all configuration changes.

Organized by category in the `system_config` table:

**Company Settings:**
- `company.name` -- Company name (default: "Dive Service Management")
- `company.address` -- Full address
- `company.phone` -- Phone number
- `company.email` -- Contact email
- `company.logo_path` -- Path to uploaded logo file
- `company.website` -- Company website URL

**Invoice Settings:**
- `invoice.prefix` -- Invoice number prefix (default: "INV")
- `invoice.next_number` -- Next invoice sequential number (default: 1)
- `invoice.default_terms` -- Default payment terms text (default: "Net 30")
- `invoice.default_due_days` -- Days until due (default: 30)
- `invoice.footer_text` -- Text printed at bottom of invoices

**Tax Settings:**
- `tax.default_rate` -- Default tax rate as decimal (default: 0.0000)
- `tax.label` -- Tax label on invoices (default: "Sales Tax")

**Service Settings:**
- `service.order_prefix` -- Order number prefix (default: "SO")
- `service.next_order_number` -- Next order sequential number (default: 1)
- `service.default_labor_rate` -- Default hourly labor rate (default: 75.00)
- `service.rush_fee_default` -- Default rush fee (default: 50.00)

**Notification Settings:**
- `notification.low_stock_check_hours` -- Hours between low stock checks (default: 6)
- `notification.overdue_check_time` -- Time of day for overdue checks (default: "08:00")
- `notification.retention_days` -- Days to keep notifications (default: 90)
- `notification.order_due_warning_days` -- Days before due date to warn (default: 2)

**Display Settings:**
- `display.theme` -- "light", "dark", or "auto" (default: "auto")
- `display.date_format` -- Date display format (default: "%Y-%m-%d")
- `display.currency_symbol` -- Currency symbol (default: "$")
- `display.currency_code` -- ISO currency code (default: "USD")
- `display.pagination_size` -- Default rows per page (default: 25)
- `display.custom_css` -- Custom CSS overrides

**Security Settings:**
- `security.password_min_length` -- Minimum password length (default: 8)
- `security.lockout_attempts` -- Failed attempts before lockout (default: 5)
- `security.lockout_duration_minutes` -- Lockout duration (default: 15)
- `security.session_lifetime_hours` -- Session lifetime (default: 24)

### 9.4 Configuration File Structure

```python
# config.py
class Config:
    """Base configuration with defaults."""
    # All defaults defined here
    
class DevelopmentConfig(Config):
    DEBUG = True
    
class ProductionConfig(Config):
    DEBUG = False
    
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
```

### 9.5 .env.example

A documented `.env.example` file is included in the repository with all configurable variables, descriptions, and example values. Users copy to `.env` and customize.

---

## 10. Project Directory Structure

```
Dive_Service_Management/
|
|-- README.md                          # Project overview and quick start
|-- README.plan                        # This planning document
|-- LICENSE                            # License file
|-- .env.example                       # Documented environment variable template
|-- .gitignore                         # Git ignore rules
|-- docker-compose.yml                 # Docker Compose orchestration
|-- docker-compose.override.yml        # Local development overrides
|-- docker-compose.lightweight.yml     # Pi-optimized: Huey instead of Celery, no WeasyPrint
|-- Dockerfile                         # Application container build
|-- Makefile                           # Common commands (make build, make up, make test, etc.)
|-- requirements.txt                   # Python dependencies (pinned)
|-- requirements-dev.txt               # Development/test dependencies
|-- pyproject.toml                     # Project metadata and tool configuration
|
|-- docker/                            # Docker-related configuration files
|   |-- db/
|   |   |-- init/
|   |   |   |-- 01-schema.sql          # Initial schema (also managed by Alembic)
|   |   |   |-- 02-seed-data.sql       # Default roles, admin user, config defaults
|   |   |-- conf/
|   |       |-- custom.cnf             # MariaDB custom configuration
|   |-- nginx/
|       |-- nginx.conf                 # Optional Nginx reverse proxy config
|       |-- ssl/                       # SSL certificates (gitignored)
|
|-- app/                               # Main application package
|   |-- __init__.py                    # Application factory (create_app)
|   |-- config.py                      # Configuration classes
|   |-- extensions.py                  # Flask extension initialization (db, migrate, login, etc.)
|   |-- celery_app.py                  # Celery application factory
|   |
|   |-- models/                        # SQLAlchemy models
|   |   |-- __init__.py                # Model imports
|   |   |-- user.py                    # User, Role, UserRole
|   |   |-- customer.py               # Customer
|   |   |-- service_order.py           # ServiceOrder, ServiceOrderItem
|   |   |-- service_item.py            # ServiceItem, DrysuitDetails
|   |   |-- service_note.py            # ServiceNote
|   |   |-- attachment.py              # Attachment (polymorphic file uploads)
|   |   |-- inventory.py               # InventoryItem
|   |   |-- parts_used.py              # PartsUsed
|   |   |-- labor.py                   # LaborEntry
|   |   |-- invoice.py                 # Invoice, InvoiceLineItem, InvoiceOrder, Payment
|   |   |-- tag.py                     # Tag, Taggable
|   |   |-- audit.py                   # AuditLog
|   |   |-- config.py                  # SystemConfig
|   |   |-- notification.py            # Notification
|   |   |-- saved_search.py            # SavedSearch
|   |   |-- price_list.py             # PriceListCategory, PriceListItem, PriceListItemParts, AppliedService
|   |   |-- mixins.py                  # Common model mixins (TimestampMixin, SoftDeleteMixin, AuditMixin)
|   |
|   |-- blueprints/                    # Flask blueprints (17 total)
|   |   |-- __init__.py
|   |   |-- auth.py                    # Login, logout, password management
|   |   |-- dashboard.py               # Dashboard views
|   |   |-- customers.py               # Customer CRUD and search
|   |   |-- orders/                    # Service order package (split from monolithic file)
|   |   |   |-- __init__.py            # Blueprint registration, list/create/edit/delete routes
|   |   |   |-- items.py               # Order item management routes
|   |   |   |-- labor.py               # Labor entry routes
|   |   |   |-- notes.py               # Service note routes
|   |   |   |-- parts.py               # Parts used routes
|   |   |   |-- services.py            # Applied service routes
|   |   |   |-- status.py              # Status change routes
|   |   |-- items.py                   # Service item CRUD, serial lookup
|   |   |-- inventory.py               # Inventory CRUD, stock management
|   |   |-- invoices.py                # Invoice CRUD, generation, payments
|   |   |-- price_list.py              # Price list management, apply services
|   |   |-- reports.py                 # Report generation views
|   |   |-- tools.py                   # Calculator and tool views
|   |   |-- admin/                     # Admin package (split from monolithic file)
|   |   |   |-- __init__.py            # Blueprint registration
|   |   |   |-- users.py               # User management routes
|   |   |   |-- settings.py            # System settings routes
|   |   |   |-- data.py                # Data management and import routes
|   |   |   |-- audit.py               # Audit log viewer routes
|   |   |   |-- logs.py                # Application log viewer routes
|   |   |-- search.py                  # Global search endpoint
|   |   |-- notifications.py           # Notification endpoints
|   |   |-- export.py                  # Export endpoints (CSV, XLSX, PDF)
|   |   |-- health.py                  # Health check endpoints (/health, /health/ready, /health/live)
|   |   |-- attachments.py             # File upload and camera capture endpoints
|   |   |-- docs.py                    # In-app documentation viewer
|   |
|   |-- services/                      # Business logic layer
|   |   |-- __init__.py
|   |   |-- customer_service.py        # Customer business logic
|   |   |-- order_service.py           # Order workflow, status transitions
|   |   |-- inventory_service.py       # Stock management, reorder logic
|   |   |-- invoice_service.py         # Invoice generation, payment processing
|   |   |-- search_service.py          # Search and indexing logic
|   |   |-- notification_service.py    # Notification creation and delivery
|   |   |-- export_service.py          # Export generation logic
|   |   |-- import_service.py          # Import processing and validation
|   |   |-- attachment_service.py       # File upload, storage, retrieval, deletion
|   |   |-- audit_service.py           # Audit log recording
|   |   |-- config_service.py          # System config read/write
|   |   |-- price_list_service.py       # Price list CRUD, apply/remove services, price snapshots
|   |   |-- tag_service.py             # Tag management
|   |   |-- report_service.py          # Report data aggregation
|   |   |-- email_service.py           # SMTP email delivery (reads config from SystemConfig)
|   |   |-- saved_search_service.py    # Per-user saved search CRUD
|   |   |-- log_service.py             # Application log file reading (allowlist-based path safety)
|   |   |-- data_management_service.py # DB stats, backup, migration status
|   |
|   |-- forms/                         # WTForms form classes
|   |   |-- __init__.py
|   |   |-- auth.py                    # Login, registration forms
|   |   |-- customer.py                # Customer form
|   |   |-- order.py                   # Service order form
|   |   |-- item.py                    # Service item form (with drysuit fields)
|   |   |-- inventory.py               # Inventory item form
|   |   |-- invoice.py                 # Invoice form, line item form
|   |   |-- price_list.py             # Price list item/category forms, applied service form
|   |   |-- labor.py                   # Labor entry form
|   |   |-- note.py                    # Service note form
|   |   |-- admin.py                   # User management, config forms
|   |   |-- search.py                  # Search and filter forms
|   |   |-- import_form.py             # Import configuration form
|   |
|   |-- templates/                     # Jinja2 templates
|   |   |-- base.html                  # Master layout (nav, tabs, header, footer)
|   |   |-- macros/                    # Reusable template macros
|   |   |   |-- forms.html             # Form field rendering macros
|   |   |   |-- pagination.html        # Pagination controls
|   |   |   |-- tables.html            # Sortable table macros
|   |   |   |-- modals.html            # Modal dialog macros
|   |   |   |-- tags.html              # Tag display and editor macros
|   |   |   |-- status_badges.html     # Status badge macros
|   |   |-- partials/                  # HTMX partial templates (HTML fragments)
|   |   |   |-- search_results.html
|   |   |   |-- notification_dropdown.html
|   |   |   |-- notification_count.html
|   |   |   |-- order_item_row.html
|   |   |   |-- parts_used_row.html
|   |   |   |-- labor_entry_row.html
|   |   |   |-- note_entry.html
|   |   |   |-- tag_editor.html
|   |   |   |-- stock_adjustment.html
|   |   |   |-- customer_picker.html
|   |   |   |-- item_lookup_result.html
|   |   |   |-- applied_service_row.html
|   |   |   |-- price_list_picker.html
|   |   |-- auth/
|   |   |   |-- login.html
|   |   |   |-- change_password.html
|   |   |-- dashboard/
|   |   |   |-- index.html
|   |   |-- customers/
|   |   |   |-- list.html
|   |   |   |-- detail.html
|   |   |   |-- form.html
|   |   |-- orders/
|   |   |   |-- list.html
|   |   |   |-- detail.html
|   |   |   |-- form.html
|   |   |   |-- kanban.html
|   |   |-- items/
|   |   |   |-- lookup.html
|   |   |   |-- detail.html
|   |   |   |-- form.html
|   |   |-- inventory/
|   |   |   |-- list.html
|   |   |   |-- detail.html
|   |   |   |-- form.html
|   |   |   |-- low_stock.html
|   |   |-- invoices/
|   |   |   |-- list.html
|   |   |   |-- detail.html
|   |   |   |-- form.html
|   |   |   |-- generate.html         # Invoice generation/preview from order
|   |   |   |-- print.html            # Print-optimized layout (also used for PDF)
|   |   |-- price_list/
|   |   |   |-- list.html              # Full price list view with categories
|   |   |   |-- item_form.html         # Price list item create/edit
|   |   |   |-- categories.html        # Category management
|   |   |   |-- print.html             # Customer-facing printable price list
|   |   |-- billing/
|   |   |   |-- search.html
|   |   |-- reports/
|   |   |   |-- hub.html
|   |   |   |-- revenue.html
|   |   |   |-- orders.html
|   |   |   |-- inventory.html
|   |   |   |-- technician.html
|   |   |   |-- customer.html
|   |   |   |-- aging.html
|   |   |-- tools/
|   |   |   |-- hub.html
|   |   |   |-- seal_calculator.html
|   |   |   |-- material_estimator.html
|   |   |   |-- pricing_calculator.html
|   |   |   |-- leak_test_log.html
|   |   |-- admin/
|   |   |   |-- hub.html
|   |   |   |-- users/
|   |   |   |   |-- list.html
|   |   |   |   |-- form.html
|   |   |   |-- settings/
|   |   |   |   |-- company.html
|   |   |   |   |-- service.html
|   |   |   |   |-- inventory.html
|   |   |   |   |-- display.html
|   |   |   |   |-- notifications.html
|   |   |   |   |-- integrations.html
|   |   |   |-- data/
|   |   |       |-- management.html
|   |   |       |-- import.html
|   |   |       |-- audit_log.html
|   |   |-- errors/
|   |       |-- 403.html
|   |       |-- 404.html
|   |       |-- 500.html
|   |
|   |-- static/                        # Static assets
|   |   |-- css/
|   |   |   |-- style.css             # Application styles
|   |   |   |-- themes/
|   |   |   |   |-- dark.css          # Dark theme overrides
|   |   |   |   |-- light.css         # Light theme overrides
|   |   |   |-- print.css             # Print and PDF styles
|   |   |-- js/
|   |   |   |-- app.js                # Application JavaScript
|   |   |   |-- htmx.min.js           # HTMX (vendored)
|   |   |   |-- alpine.min.js         # Alpine.js (vendored)
|   |   |   |-- chart.min.js          # Chart.js (vendored)
|   |   |   |-- tom-select.min.js     # Tom Select (vendored)
|   |   |-- img/
|   |   |   |-- logo-default.png      # Default application logo
|   |   |   |-- favicon.ico
|   |   |-- vendor/                    # Other vendored libraries
|   |
|   |-- tasks/                         # Celery task definitions
|   |   |-- __init__.py
|   |   |-- notification_tasks.py      # Scheduled notification checks
|   |   |-- export_tasks.py            # Background export generation
|   |   |-- import_tasks.py            # Background import processing
|   |   |-- maintenance_tasks.py       # Cleanup, retention, etc.
|   |
|   |-- utils/                         # Utility modules
|   |   |-- __init__.py
|   |   |-- decorators.py             # Custom decorators (permission_required, etc.)
|   |   |-- formatters.py             # Date, currency, number formatting helpers
|   |   |-- validators.py             # Custom validators
|   |   |-- pdf.py                    # PDF generation helpers
|   |   |-- calculators.py            # Tool calculation logic
|   |   |-- number_generator.py       # Order/invoice number generation
|   |
|   |-- cli/                           # Flask CLI commands
|       |-- __init__.py
|       |-- seed.py                    # flask seed-db (populate defaults)
|       |-- create_admin.py            # flask create-admin
|       |-- backup.py                  # flask backup-db
|
|-- migrations/                        # Alembic migration scripts (auto-generated)
|   |-- alembic.ini
|   |-- env.py
|   |-- versions/
|
|-- tests/                             # Test suite (see Section 14 for full testing strategy)
|   |-- __init__.py
|   |-- conftest.py                    # Root fixtures: app, db session, test client, auth helpers
|   |-- factories.py                   # factory-boy model factories for all entities
|   |-- helpers.py                     # Shared test utilities (assert helpers, data builders)
|   |
|   |-- unit/                          # Unit tests — run after each code change
|   |   |-- __init__.py
|   |   |-- models/                    # Model unit tests (CRUD, validation, relationships, computed fields)
|   |   |   |-- __init__.py
|   |   |   |-- test_user.py
|   |   |   |-- test_customer.py
|   |   |   |-- test_service_order.py
|   |   |   |-- test_service_item.py
|   |   |   |-- test_service_note.py
|   |   |   |-- test_inventory.py
|   |   |   |-- test_invoice.py
|   |   |   |-- test_price_list.py
|   |   |   |-- test_applied_service.py
|   |   |   |-- test_parts_used.py
|   |   |   |-- test_labor.py
|   |   |   |-- test_tag.py
|   |   |   |-- test_audit.py
|   |   |   |-- test_notification.py
|   |   |   |-- test_mixins.py
|   |   |-- services/                  # Service layer unit tests (business logic, isolated from HTTP)
|   |   |   |-- __init__.py
|   |   |   |-- test_customer_service.py
|   |   |   |-- test_order_service.py
|   |   |   |-- test_inventory_service.py
|   |   |   |-- test_invoice_service.py
|   |   |   |-- test_price_list_service.py
|   |   |   |-- test_search_service.py
|   |   |   |-- test_notification_service.py
|   |   |   |-- test_export_service.py
|   |   |   |-- test_import_service.py
|   |   |   |-- test_audit_service.py
|   |   |   |-- test_config_service.py
|   |   |   |-- test_report_service.py
|   |   |-- forms/                     # Form validation unit tests
|   |   |   |-- __init__.py
|   |   |   |-- test_customer_form.py
|   |   |   |-- test_order_form.py
|   |   |   |-- test_item_form.py
|   |   |   |-- test_inventory_form.py
|   |   |   |-- test_invoice_form.py
|   |   |   |-- test_price_list_form.py
|   |   |   |-- test_auth_forms.py
|   |   |-- utils/                     # Utility function unit tests
|   |   |   |-- __init__.py
|   |   |   |-- test_formatters.py
|   |   |   |-- test_validators.py
|   |   |   |-- test_calculators.py
|   |   |   |-- test_number_generator.py
|   |
|   |-- blueprint/                     # Blueprint/route tests (HTTP request/response, HTMX fragments)
|   |   |-- __init__.py
|   |   |-- test_auth_routes.py
|   |   |-- test_dashboard_routes.py
|   |   |-- test_customer_routes.py
|   |   |-- test_order_routes.py
|   |   |-- test_item_routes.py
|   |   |-- test_inventory_routes.py
|   |   |-- test_invoice_routes.py
|   |   |-- test_price_list_routes.py
|   |   |-- test_billing_routes.py
|   |   |-- test_report_routes.py
|   |   |-- test_tools_routes.py
|   |   |-- test_admin_routes.py
|   |   |-- test_search_routes.py
|   |   |-- test_notification_routes.py
|   |   |-- test_export_routes.py
|   |   |-- test_import_routes.py
|   |
|   |-- validation/                    # Validation tests — run at phase/feature completion
|   |   |-- __init__.py
|   |   |-- test_customer_workflow.py       # End-to-end: create customer -> view -> edit -> search -> export
|   |   |-- test_order_workflow.py          # End-to-end: create order -> add items -> apply services -> add parts/labor -> status transitions -> complete
|   |   |-- test_serial_lookup_workflow.py  # Serial entry -> history display -> new item creation -> repeat visit
|   |   |-- test_invoice_workflow.py        # Order -> generate invoice -> review -> edit lines -> send -> record payment -> paid
|   |   |-- test_price_list_workflow.py     # Create category -> add items -> link parts -> apply to order -> verify invoice lines -> print price list
|   |   |-- test_inventory_workflow.py      # Add stock -> use in order (manual + auto-deduct) -> verify deduction -> low stock alert -> reorder
|   |   |-- test_import_export_workflow.py  # Export customers -> modify CSV -> reimport -> verify round-trip
|   |   |-- test_auth_workflow.py           # Login -> role-based access enforcement -> all permission matrix entries
|   |   |-- test_notification_workflow.py   # Trigger conditions -> verify notification created -> mark read -> expiry
|   |   |-- test_search_workflow.py         # Global search -> per-entity search -> tag search -> saved searches
|   |   |-- test_report_accuracy.py         # Seed known data -> run each report -> verify calculations match expected
|   |   |-- test_pdf_generation.py          # Generate invoice PDF -> verify content, layout, and file integrity
|   |   |-- test_data_integrity.py          # Soft delete cascade, audit log completeness, price snapshot preservation
|   |   |-- test_concurrent_access.py       # Multiple techs editing same order, stock race conditions
|   |
|   |-- smoke/                         # Smoke tests — quick sanity check that the app starts and core paths work
|   |   |-- __init__.py
|   |   |-- test_app_starts.py             # App factory creates app, all blueprints registered, DB connects
|   |   |-- test_all_pages_load.py         # Every registered route returns 200/302 (not 500)
|   |   |-- test_static_assets.py          # All vendored JS/CSS files exist and are served
|
|-- docs/                              # Documentation
|   |-- setup.md                       # Detailed setup instructions
|   |-- configuration.md               # Configuration reference
|   |-- remote_db.md                   # Remote database setup guide
|   |-- user_guide.md                  # End user guide
|   |-- api.md                         # Internal API/endpoint reference
|   |-- development.md                 # Developer guide
|
|-- scripts/                           # Utility and deployment scripts
|   |-- setup.sh                       # Main setup/management script (install, upgrade, backup, etc.)
|   |-- backup.sh                      # Database backup (also called via setup.sh backup)
|   |-- restore.sh                     # Database restore (also called via setup.sh restore)
|   |-- generate_secret_key.py         # Standalone secure secret key generator
|   |-- healthcheck.sh                 # Container health check helper
|
|-- uploads/                           # User uploads (gitignored)
|   |-- logos/
|   |-- imports/
|   |-- exports/
|   |-- attachments/                   # Polymorphic file attachments (photos, documents)
|
|-- instance/                          # Flask instance folder (gitignored)
|   |-- config.py                      # Local config overrides
|
|-- logs/                              # Application logs (gitignored)
```

---

## 11. Reporting

### 11.1 Available Reports

All reports support date range filtering, export to CSV/XLSX/PDF, and are viewable on-screen with Chart.js visualizations where appropriate.

**Revenue Reports** (`/reports/revenue`)
- Revenue by period (daily/weekly/monthly/quarterly/yearly)
- Revenue by service type (repair type tags)
- Revenue by customer (top N customers by spend)
- Revenue breakdown: parts vs. labor vs. fees
- Chart: Stacked bar chart showing revenue components over time

**Service Order Reports** (`/reports/orders`)
- Orders by status (current snapshot)
- Orders completed per period
- Average turnaround time (received to completed)
- Orders by technician
- Orders by repair type (from tags)
- Most common repair types
- Chart: Status distribution doughnut, turnaround trend line

**Inventory Reports** (`/reports/inventory`)
- Current stock levels (all items or filtered by category)
- Low stock report (items below reorder level)
- Stock movement (usage over time)
- Inventory valuation (total purchase cost and resale value of current stock)
- Most used parts (by quantity used in service orders)
- Parts cost analysis (cost vs. charged price, margin analysis)
- Chart: Top 10 most-used parts bar chart, stock value by category pie chart

**Technician Reports** (`/reports/technician`)
- Labor hours by tech per period
- Revenue generated by tech
- Orders completed by tech
- Average time per order by tech
- Parts usage by tech

**Customer Reports** (`/reports/customers`)
- New customers per period
- Customer lifetime value (total billed)
- Repeat customer rate
- Customers with outstanding balances
- Customer acquisition by referral source

**Accounts Receivable Aging Report** (`/reports/aging`)
- Invoices grouped by aging buckets: Current, 1-30 days, 31-60 days, 61-90 days, 90+ days
- Total outstanding per bucket
- Customer breakdown within each bucket
- Chart: Stacked bar by aging bucket

**Item Service History Report** (`/reports/item-history`)
- Search by serial number or item name
- Shows complete service history for an item
- Total parts and labor spent on item over its lifetime
- Serviceability timeline

### 11.2 Report Implementation

- Reports are generated by `report_service.py` which runs aggregation queries
- Each report has a dedicated template for on-screen display
- Chart data is passed to templates as JSON for Chart.js rendering
- Export: the same data is formatted by `export_service.py` into the requested format
- Large reports (>10,000 rows) are generated as background Celery tasks
- Reports are cached in Redis for 15 minutes (cache key includes filter parameters)

---

## 12. Tools / Calculators

### 12.1 Seal Size Calculator (`/tools/seal-calculator`)

- **Purpose**: Determine correct replacement seal size based on measurements
- **Inputs**: 
  - Seal type (neck, wrist)
  - Measurement (circumference in cm or inches, with unit toggle)
  - Seal material (latex, silicone, neoprene)
  - Seal brand/system (SI Tech, DUI ZipSeal, Waterproof, generic)
- **Output**: 
  - Recommended seal size based on manufacturer sizing charts
  - Size range (minimum comfortable to maximum)
  - Notes on sizing considerations
- **Data**: Sizing charts stored in a JSON configuration file, editable via admin
- **Implementation**: Client-side calculation via Alpine.js for instant results, with reference data loaded from server

### 12.2 Material Estimator (`/tools/material-estimator`)

- **Purpose**: Estimate material quantities needed for common repairs
- **Inputs**:
  - Repair type (patch, seam repair, seal replacement, etc.)
  - Suit material type (neoprene thickness, trilaminate type)
  - Damage size/area (length x width for patches, length for seams)
  - Number of seals being replaced
- **Output**:
  - Adhesive/cement quantity needed (ml/oz)
  - Patch material area needed (with 15% waste factor)
  - Recommended specific products from inventory (with current stock levels)
  - Estimated cure/dry time
- **Implementation**: Server-side calculation (HTMX form submit), pulls current inventory data

### 12.3 Pricing Calculator (`/tools/pricing-calculator`)

- **Purpose**: Quick price estimation for common jobs before creating a full service order
- **Inputs**:
  - Repair type(s) -- multi-select checklist of common repairs
  - Parts needed -- auto-populated based on selected repairs, editable quantities
  - Estimated labor hours
  - Rush fee toggle
  - Discount (percent or fixed)
  - Tax rate (from system config, editable)
- **Output**:
  - Itemized estimate (parts list with prices, labor, fees, discounts)
  - Subtotal, tax, total
  - "Create Service Order" button that pre-populates a new order with these details
  - "Print Estimate" button (generates a simple PDF)
- **Data**: Default parts/labor for each repair type stored in a JSON config, editable via admin
- **Implementation**: HTMX-driven, updates totals dynamically as inputs change

### 12.4 Leak Test Logger (`/tools/leak-test-log`)

- **Purpose**: Structured logging interface for pressure/leak testing drysuits
- **Inputs**:
  - Service order item (searchable picker)
  - Test type (pressure hold, water submersion, visual inspection)
  - Test pressure (PSI or bar)
  - Duration (minutes)
  - Result (pass, fail - minor, fail - major)
  - Leak locations (interactive body diagram or text description)
  - Notes
  - Photos (file upload, future feature placeholder)
- **Output**: Saves as a structured service note on the service order item with `note_type='testing'`
- **Implementation**: Custom form that generates a formatted service note

### 12.5 Valve Service Reference (`/tools/valve-reference`)

- **Purpose**: Quick reference for valve specifications, service procedures, and compatibility
- **Content**:
  - Table of common valve brands and models with specifications
  - Thread sizes and compatibility matrix (e.g., SI Tech M33 vs Apeks M38)
  - Service intervals and procedures (filterable by brand/model)
  - O-ring sizes and specifications per valve model
  - Torque specifications
- **Data**: Stored in a JSON reference file, rendered as searchable/filterable tables
- **Implementation**: Static reference page with client-side filtering (Alpine.js)

### 12.6 Unit Converter (`/tools/converter`)

- **Purpose**: Quick conversion between units commonly used in dive equipment service
- **Conversions**:
  - Imperial / Metric length (inches to mm/cm)
  - PSI / Bar / ATM pressure
  - Fahrenheit / Celsius temperature
  - Fluid ounces / ml adhesive quantities
- **Implementation**: Pure client-side (Alpine.js), no server calls needed

---

## 13. Implementation Phases

> All phases are complete. See `PROGRESS.md` for detailed per-phase tracking.

### Phase 1 -- Foundation (Complete, 36 tests)

- Project scaffolding, Docker setup, config system, Makefile, deployment script
- Database schema and Alembic migrations
- Base template with navigation, theme support
- User authentication and role-based access (Flask-Security-Too)
- Flask CLI commands (seed-db, create-admin)
- Health check endpoint

### Phase 2 -- Core Entities (Complete, 377 tests cumulative)

- Customer, ServiceItem, InventoryItem, PriceList CRUD with full service layers
- Tagging system (polymorphic)
- Global search with HTMX autocomplete

### Phase 3 -- Service Workflow (Complete, 516 tests cumulative)

- Service Order CRUD with full status workflow
- Applied Services, Parts Used, Labor Entries, Service Notes
- Order number generation with retry-on-IntegrityError

### Phase 4 -- Billing (Complete, 635 tests cumulative)

- Invoice generation from orders, line item management, payment recording
- Invoice status state machine (INVOICE_STATUS_TRANSITIONS)

### Phase 5 -- Reports, Tools, Polish (Complete, 726 tests cumulative)

- 5 report types with Chart.js visualizations
- 6 repair tools (seal calculator, material estimator, etc.)
- CSV/XLSX export, notification system, Celery background tasks

### Phase 6 -- Production Readiness (Complete, 726 tests)

- Alembic migration for Phases 3-5, Docker verification, security audit

### Post-Phase 6 Reviews (Complete, 809 tests cumulative)

- 3 rounds of external review fixes
- Critical fixes: inventory decimals, notification broadcast reads, status bypass prevention
- Admin overhaul: SystemConfig, editable settings UI, data management, CSV import

### Sprint 2026-03-13 (Complete, 939 tests cumulative)

- Quick-create customer modal, AuditLog model + viewer, UAT admin tests

### Sprint 2026-03-15 Waves 1-3 (Complete, 1246 tests cumulative)

- Audit wiring, PDF invoices (fpdf2), documentation suite
- Dashboard activity feed, health probes (/health/ready, /health/live), kanban board, camera capture
- Service layer refactoring, FULLTEXT search + streaming exports, import column mapping wizard

### Wave 4A-D (Complete, 1418 tests cumulative)

- **4A**: Beat healthcheck fix, vendor frontend libs, extended login form, compose override template, company branding
- **4B**: Email notifications (SMTP), saved searches (per-user), broadcast notification UI, in-app docs viewer
- **4C**: Module splitting (admin/ and orders/ packages), admin log viewer, MariaDB parity tests
- **4D**: Inline dropdown creation (4 quick-create patterns), Docker persistent test container
- **4E**: Planning documentation updates

---

## 14. Testing Strategy

Testing is **not a separate phase** — it is embedded into every development step. The discipline is:

1. **Unit tests are written with each piece of code** and run immediately to verify correctness before proceeding
2. **Validation tests run at phase/feature completion** to verify end-to-end workflows
3. **Full regression suite runs at every dev stop** (end of session) to catch regressions

### 14.1 Test Categories and When They Run

| Category | Scope | When to run | Pytest marker | Typical run time |
| --- | --- | --- | --- | --- |
| **Smoke** | App starts, pages load, authenticated core routes, assets served | After any config/infra change | `@pytest.mark.smoke` | < 10s |
| **Unit** | Single function/method/model in isolation | Immediately after writing the code under test | `@pytest.mark.unit` | < 60s total |
| **Blueprint** | HTTP route request/response cycle | After writing or modifying a route | `@pytest.mark.blueprint` | < 90s total |
| **Validation** | Multi-step end-to-end workflow | At phase/feature completion | `@pytest.mark.validation` | < 5min total |
| **Full regression** | All of the above | At dev stop, before commit, in CI | (no marker — runs everything) | < 8min total |

### 14.2 Development Cadence

**During active development** (the core loop):

```
1. Write/modify code (model, service, route, template)
2. Write unit test(s) for that code
3. Run: pytest tests/unit/ -x --tb=short
         ^^^^^^^^^^^^^^^^^^
         Only the unit tests, stop on first failure
4. Fix any failures before proceeding to the next piece of code
5. Repeat
```

**At feature completion** (e.g., "Customer CRUD is done"):

```
1. Run related validation test(s):
   pytest tests/validation/test_customer_workflow.py -v
2. Fix any issues found
3. Run all unit + blueprint tests to check for regressions:
   pytest tests/unit/ tests/blueprint/ -x --tb=short
```

**At phase completion** (e.g., "Phase 2: Core Entities is done"):

```
1. Run ALL validation tests for this phase:
   pytest tests/validation/ -v --tb=long
2. Run full regression:
   pytest --tb=short
3. Check coverage:
   pytest --cov=app --cov-report=term-missing --cov-fail-under=80
4. Fix any failures or coverage gaps before starting next phase
```

**At dev stop** (end of session, before any commit):

```
1. Full regression with coverage:
   pytest --cov=app --cov-report=term-missing --cov-report=html
2. Review coverage HTML report for untested paths
3. All tests must pass. No committing with known failures.
```

### 14.3 Pytest Configuration

```ini
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "smoke: Quick sanity checks (app starts, pages load)",
    "unit: Unit tests for models, services, forms, utilities",
    "blueprint: HTTP route/response tests",
    "validation: End-to-end workflow tests",
    "slow: Tests that take >5 seconds (excluded from quick runs)",
]
addopts = [
    "--strict-markers",
    "--tb=short",
    "-q",
]
filterwarnings = [
    "ignore::DeprecationWarning",
]

[tool.coverage.run]
source = ["app"]
omit = [
    "app/celery_app.py",
    "app/cli/*",
]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.",
    "if TYPE_CHECKING:",
]
```

### 14.4 Test Fixtures and Factories

**Root fixtures** (`tests/conftest.py`):

```python
# Key fixtures available to all tests:

@pytest.fixture(scope='session')
def app():
    """Create application with TestingConfig (SQLite in-memory)."""

@pytest.fixture(scope='function')
def db(app):
    """Fresh database for each test. Creates tables, yields session, rolls back."""

@pytest.fixture(scope='function')
def client(app):
    """Flask test client for HTTP requests."""

@pytest.fixture(scope='function')
def auth_client(client, db):
    """Pre-authenticated test client (admin role)."""

@pytest.fixture(scope='function')
def tech_client(client, db):
    """Pre-authenticated test client (technician role)."""

@pytest.fixture(scope='function')
def viewer_client(client, db):
    """Pre-authenticated test client (viewer role)."""

@pytest.fixture(scope='function')
def anon_client(client):
    """Unauthenticated test client."""
```

**Factories** (`tests/factories.py`) — using `factory-boy`:

One factory per model, generating realistic test data via Faker. Each factory has sensible defaults but allows per-test overrides. Key factories:

- `UserFactory(role='admin'|'technician'|'viewer')`
- `CustomerFactory(customer_type='individual'|'business')`
- `ServiceOrderFactory(status='intake'|..., customer=...)`
- `ServiceItemFactory(serviceability='serviceable'|..., serial_number=...)`
- `DrysuitDetailsFactory(service_item=...)`
- `AttachmentFactory(attachable_type='service_item', attachable_id=...)`
- `ServiceOrderItemFactory(order=..., service_item=...)`
- `InventoryItemFactory(quantity_in_stock=10, reorder_level=5)`
- `PriceListCategoryFactory(name='Seal Replacement')`
- `PriceListItemFactory(category=..., price=Decimal('110.00'))`
- `AppliedServiceFactory(service_order_item=..., price_list_item=...)`
- `InvoiceFactory(status='draft'|..., customer=..., order=...)`
- `LaborEntryFactory(tech=..., hours=Decimal('2.0'))`
- `PartsUsedFactory(inventory_item=..., quantity=1)`
- `TagFactory(name='leak-repair')`

### 14.5 What Each Test Category Covers

#### Smoke Tests (`tests/smoke/`)

Run in < 10 seconds. Catch broken deployments instantly.

- `test_app_starts.py` — App factory succeeds, all blueprints registered, extensions initialized, DB connectable
- `test_all_pages_load.py` — Iterate all registered URL rules, `GET` each one with an authenticated client, assert no 500 errors (200 or 302 redirect are both acceptable)
- `test_static_assets.py` — Vendored HTMX, Alpine.js, Bootstrap, Chart.js, Tom Select files exist and return 200

#### Unit Tests (`tests/unit/`)

**Models** — For each model, test:

- **Creation**: Create with valid data, verify all fields persisted correctly
- **Required fields**: Attempt to create with each required field missing, verify validation error
- **Defaults**: Create with minimal data, verify all defaults applied correctly
- **Relationships**: Create parent + children, verify FK navigation works both directions
- **Computed properties**: Test any `@property` or `@hybrid_property` methods (e.g., `invoice.balance_due`, `customer.display_name`, `service_order.total_cost`)
- **Constraints**: Test unique constraints raise on duplicate, enum fields reject invalid values
- **Soft delete**: Verify `is_deleted` flag and `deleted_at` timestamp, verify soft-deleted records excluded from default queries
- **Audit mixin**: Verify `created_at`/`updated_at` auto-populated

**Services** — For each service method, test:

- **Happy path**: Correct inputs produce correct outputs and side effects
- **Edge cases**: Empty inputs, zero quantities, boundary values, null optionals
- **Error cases**: Invalid inputs raise appropriate exceptions
- **Business rules**: Status transitions (valid and invalid), stock deduction logic, price snapshot preservation, invoice calculation accuracy
- **Key service-specific tests**:
  - `order_service`: Valid and invalid status transitions, re-assignment, completion requirements
  - `inventory_service`: Stock deduction, negative stock prevention, reorder level triggering
  - `price_list_service`: Apply service with auto-deduct, price override tracking, custom item handling
  - `invoice_service`: Line item generation from applied services + parts + labor, tax calculation, payment recording, balance computation, void/refund logic
  - `search_service`: FULLTEXT match relevance, multi-entity search, tag filtering AND/OR logic
  - `notification_service`: Each trigger condition, recipient resolution, duplicate prevention

**Forms** — For each WTForm, test:

- Valid data passes validation
- Each required field triggers error when missing
- Field-specific validation (email format, phone format, decimal precision, enum values)
- CSRF token presence (via Flask-WTF)

**Utilities** — For each utility function, test:

- `formatters.py`: Currency formatting, date formatting, number formatting with locale
- `validators.py`: Custom validators (serial number format, phone, postal code)
- `calculators.py`: Seal calculator, material estimator, pricing calculator — known inputs produce known outputs
- `number_generator.py`: Order/invoice number generation, sequence incrementing, prefix formatting

#### Blueprint Tests (`tests/blueprint/`)

For each blueprint route, test:

- **HTTP method + status code**: GET returns 200, POST with valid data returns 302 redirect, invalid POST returns 200 with form errors
- **Authentication**: Unauthenticated requests redirect to login
- **Authorization**: Each role tested against the permission matrix — technician can create orders, viewer cannot; admin can void invoices, technician cannot; etc.
- **HTMX fragments**: Requests with `HX-Request: true` header return HTML fragments (not full pages)
- **Form submission**: Valid data creates/updates the record, redirects correctly
- **Flash messages**: Success and error flash messages present in response
- **Key route-specific tests**:
  - `test_order_routes.py`: Add item by serial (existing vs. new), apply service from price list, add custom service, status change via dropdown
  - `test_price_list_routes.py`: List renders all categories, edit saves changes, duplicate creates copy, print generates PDF-ready page
  - `test_invoice_routes.py`: Generate from order populates correct line items, record payment updates balance, void changes status
  - `test_search_routes.py`: Global search returns categorized results, debounce-compatible endpoint
  - `test_admin_routes.py`: Non-admin gets 403 on all admin routes

#### Validation Tests (`tests/validation/`)

End-to-end workflows exercising the full stack (HTTP request through service layer to database and back). Each test simulates a real user session:

- **`test_customer_workflow.py`**: Create individual customer -> verify in list -> edit to add business name -> search by name -> search by phone -> view order history (empty) -> export to CSV -> verify CSV content
- **`test_order_workflow.py`**: Create customer -> create order -> add service item by serial (new) -> apply "Latex Neck Seal" from price list -> apply custom ad-hoc item ("Custom alteration", $150) -> add labor entry -> add manual part -> walk through status transitions (intake -> assessment -> in_progress -> completed -> ready_for_pickup) -> verify timeline entries -> generate invoice -> verify line items match applied services + parts + labor -> verify inventory deducted
- **`test_serial_lookup_workflow.py`**: Enter serial for non-existent item -> create item -> complete order -> enter same serial on new order -> verify history shows previous service -> verify serviceability flag carries forward
- **`test_invoice_workflow.py`**: Generate from completed order -> verify draft totals correct -> edit a line item -> add tax -> send -> verify status change -> record partial payment -> verify balance due -> record remaining payment -> verify status = paid -> void a paid invoice -> verify refund status
- **`test_price_list_workflow.py`**: Create category -> add 3 items with prices -> link inventory parts to one item -> apply linked item to order -> verify auto-deduct of parts -> verify price snapshot preserved after editing price list item -> print price list -> verify inactive items excluded -> export price list CSV -> verify content
- **`test_inventory_workflow.py`**: Create item with stock=10, reorder_level=3 -> use 5 in order (via applied service auto-deduct) -> verify stock=5 -> use 3 manually -> verify stock=2 -> verify low-stock notification created -> adjust stock +10 -> verify notification cleared -> verify usage history shows both orders
- **`test_import_export_workflow.py`**: Seed 20 customers -> export CSV -> modify 5 rows in CSV (programmatically) -> reimport with "update" duplicate handling -> verify 5 updated, 15 unchanged -> reimport with "skip" -> verify all unchanged -> import with 3 invalid rows -> verify error report shows correct row numbers and reasons
- **`test_auth_workflow.py`**: For each role (admin, technician, viewer), iterate every entry in the permission matrix (Section 4.3) and verify access is granted or denied as specified. Test login, logout, remember-me, account lockout after N failed attempts, password change.
- **`test_notification_workflow.py`**: Trigger each notification type (low stock, overdue invoice, order approaching due, etc.) -> verify notification exists with correct severity, message, and recipient -> mark as read -> verify read_at set -> verify old notifications expire after retention period (using freezegun)
- **`test_search_workflow.py`**: Seed data with known values -> global search returns correct entities grouped by type -> per-entity search returns filtered results -> tag search with AND and OR logic -> save search -> load saved search -> verify default saved search auto-applies
- **`test_report_accuracy.py`**: Seed a controlled dataset (known orders, invoices, payments, inventory usage) -> run each report with specific date ranges -> verify every computed number (revenue totals, turnaround averages, stock valuations, aging buckets) matches hand-calculated expected values
- **`test_pdf_generation.py`**: Generate invoice PDF -> verify file is valid PDF -> verify company name, customer name, line items, totals appear in extracted text -> generate printable price list PDF -> verify categories and items present, inactive items absent
- **`test_data_integrity.py`**: Soft-delete a customer with orders -> verify orders still accessible but customer marked deleted -> verify audit log entries complete -> delete price list item -> verify applied_services still have snapshot data -> verify invoice line items unchanged
- **`test_concurrent_access.py`**: Two test clients simultaneously add parts to same order item -> verify no double-deduction of inventory -> Two clients change order status at same time -> verify only one succeeds (optimistic locking or last-write-wins with audit trail)

### 14.6 Test Discipline Per Implementation Phase

Each phase below specifies exactly which tests to write and when to run them.

#### Phase 1 — Foundation

| Step | Write these tests | Run immediately |
| --- | --- | --- |
| App factory + extensions | `smoke/test_app_starts.py` | `pytest tests/smoke/ -x` |
| Config system | `unit/utils/test_config_service.py` (if config_service exists) | `pytest tests/unit/ -x` |
| User model + auth | `unit/models/test_user.py`, `unit/forms/test_auth_forms.py`, `blueprint/test_auth_routes.py` | `pytest tests/unit/models/test_user.py tests/blueprint/test_auth_routes.py -x` |
| Base template + nav | `smoke/test_all_pages_load.py` (initial version with auth routes only) | `pytest tests/smoke/ -x` |
| CLI commands (seed, create-admin) | Unit tests for CLI commands via `CliRunner` | `pytest tests/unit/ -x` |

**Phase 1 gate**: `pytest tests/smoke/ tests/unit/ tests/blueprint/ -v` — all pass, `tests/validation/test_auth_workflow.py` passes.

#### Phase 2 — Core Entities

| Step | Write these tests | Run immediately |
| --- | --- | --- |
| Customer model | `unit/models/test_customer.py` | `pytest tests/unit/models/test_customer.py -x` |
| Customer service | `unit/services/test_customer_service.py` | `pytest tests/unit/services/test_customer_service.py -x` |
| Customer form | `unit/forms/test_customer_form.py` | `pytest tests/unit/forms/test_customer_form.py -x` |
| Customer routes | `blueprint/test_customer_routes.py` | `pytest tests/blueprint/test_customer_routes.py -x` |
| *Customer feature complete* | `validation/test_customer_workflow.py` | `pytest tests/validation/test_customer_workflow.py -v` |
| Service Item (model, service, form, routes) | Same pattern as Customer | Same pattern |
| Inventory Item (model, service, form, routes) | Same pattern as Customer | Same pattern |
| Price List (model, service, form, routes) | `unit/models/test_price_list.py`, `unit/services/test_price_list_service.py`, `blueprint/test_price_list_routes.py` | Same pattern |
| Tags | `unit/models/test_tag.py` | `pytest tests/unit/models/test_tag.py -x` |
| Global search | `unit/services/test_search_service.py`, `blueprint/test_search_routes.py` | Same pattern |

**Phase 2 gate**: `pytest -v` (full regression), plus: `test_customer_workflow`, `test_price_list_workflow` (partial — management only, not yet applied to orders), `test_search_workflow`. Coverage check: `pytest --cov=app --cov-fail-under=80`.

#### Phase 3 — Service Workflow

| Step | Write these tests | Run immediately |
| --- | --- | --- |
| Service Order model + service | `unit/models/test_service_order.py`, `unit/services/test_order_service.py` | `pytest tests/unit/models/test_service_order.py tests/unit/services/test_order_service.py -x` |
| ServiceOrderItem model | `unit/models/test_service_order.py` (extended) | Same file, re-run |
| Applied Services model + service | `unit/models/test_applied_service.py`, extend `unit/services/test_price_list_service.py` | `pytest tests/unit/models/test_applied_service.py -x` |
| Parts Used + auto-deduct | `unit/models/test_parts_used.py`, extend `unit/services/test_inventory_service.py` | Re-run inventory service tests |
| Labor Entry | `unit/models/test_labor.py` | `pytest tests/unit/models/test_labor.py -x` |
| Service Notes | `unit/models/test_service_note.py` | Same pattern |
| Order routes (full CRUD + HTMX) | `blueprint/test_order_routes.py` | `pytest tests/blueprint/test_order_routes.py -x` |
| Status workflow | Extend `unit/services/test_order_service.py` with every valid/invalid transition | Re-run |

**Phase 3 gate**: `pytest -v`, plus: `test_order_workflow`, `test_serial_lookup_workflow`, `test_price_list_workflow` (now full, including apply-to-order), `test_inventory_workflow`, `test_data_integrity`. Coverage: `--cov-fail-under=80`.

#### Phase 4 — Billing

| Step | Write these tests | Run immediately |
| --- | --- | --- |
| Invoice model | `unit/models/test_invoice.py` | `pytest tests/unit/models/test_invoice.py -x` |
| Invoice service (generation, payment, void) | `unit/services/test_invoice_service.py` | `pytest tests/unit/services/test_invoice_service.py -x` |
| Invoice routes | `blueprint/test_invoice_routes.py` | `pytest tests/blueprint/test_invoice_routes.py -x` |
| PDF generation | `unit/utils/test_pdf.py` (if applicable), `validation/test_pdf_generation.py` | `pytest tests/validation/test_pdf_generation.py -v` |
| Billing search | `blueprint/test_billing_routes.py` | Same pattern |

**Phase 4 gate**: `pytest -v`, plus: `test_invoice_workflow`, `test_report_accuracy` (revenue/aging reports now testable), `test_pdf_generation`. Coverage: `--cov-fail-under=80`.

#### Phase 5 — Reports, Tools, Polish

| Step | Write these tests | Run immediately |
| --- | --- | --- |
| Each report | Extend `validation/test_report_accuracy.py` per report added | `pytest tests/validation/test_report_accuracy.py -v` |
| Calculators | `unit/utils/test_calculators.py` | `pytest tests/unit/utils/test_calculators.py -x` |
| Tool routes | `blueprint/test_tools_routes.py` | Same pattern |
| Import/export | `unit/services/test_export_service.py`, `unit/services/test_import_service.py` | Same pattern |
| Notifications | `unit/services/test_notification_service.py`, `unit/models/test_notification.py` | Same pattern |

**Phase 5 gate**: `pytest -v`, plus ALL validation tests pass, plus: `test_import_export_workflow`, `test_notification_workflow`, `test_report_accuracy` (all reports). Coverage: `--cov-fail-under=80`.

#### Phase 6 — Production Readiness

- Fix any remaining coverage gaps to reach 80%+ on all modules
- `test_concurrent_access.py` validated
- Performance profiling of test suite — ensure full run < 8 minutes
- Security-focused tests: CSRF token enforcement, XSS in user-supplied fields (inject `<script>` in customer name, verify escaped in output), SQL injection in search fields
- Run full suite on target hardware (Raspberry Pi Docker) to verify no platform-specific failures

**Phase 6 gate**: `pytest --cov=app --cov-report=html --cov-fail-under=80 -v` — 100% pass, 80%+ coverage, all validation tests green.

### 14.7 Makefile Test Targets

```makefile
# Run targets (these wrap docker compose exec for containerized tests)

test:               pytest                                         # Full regression
test-smoke:         pytest tests/smoke/ -x                         # Smoke tests only
test-gate:          ./scripts/final_wave_gate.sh                  # Smoke + integration gate
test-unit:          pytest tests/unit/ -x --tb=short               # Unit tests only, stop on first fail
test-blueprint:     pytest tests/blueprint/ -x --tb=short          # Blueprint tests only
test-validation:    pytest tests/validation/ -v --tb=long          # Validation tests, verbose
test-fast:          pytest tests/smoke/ tests/unit/ -x --tb=short  # Smoke + unit (the "quick check")
test-cov:           pytest --cov=app --cov-report=term-missing --cov-report=html  # With coverage
test-failed:        pytest --lf --tb=long                          # Re-run only last-failed tests
test-watch:         ptw tests/unit/ -- -x --tb=short               # Watch mode (requires pytest-watch)
```

### 14.8 User Acceptance Testing (UAT)

UAT scripts validate the application from an end-user perspective using browser
automation via **Playwright**. They complement unit/blueprint tests by exercising
the full stack: Docker containers, Flask app, rendered HTML, HTMX interactions,
and database persistence.

**Infrastructure:**

| Component | File | Purpose |
|-----------|------|---------|
| Dockerfile | `Dockerfile.uat` | Test image with Playwright + Chromium |
| Compose | `docker-compose.uat.yml` | Orchestrates: app (web), db (MariaDB), Playwright runner |
| Requirements | `requirements-uat.txt` | pytest-playwright, playwright |
| Conftest | `tests/uat/conftest.py` | Fixtures: browser, page, admin_page, tech_page, viewer_page |
| Plan | `tests/uat/UAT_PLAN.md` | Full test inventory and timing schedule |

**Marker:** `@pytest.mark.uat` — excluded from standard test runs via `--ignore=tests/uat`.

**UAT Timing Schedule:**

| Phase | UAT Scope | Script File(s) |
|-------|-----------|----------------|
| 1 | Login, logout, dashboard, health | `test_uat_auth.py` |
| 2 | Customer/Item/Inventory CRUD, price list, search | `test_uat_customers.py`, `test_uat_items.py`, `test_uat_inventory.py`, `test_uat_price_list.py`, `test_uat_search.py` |
| 3 | Service order workflow, parts, labor, notes | `test_uat_orders.py` |
| 4 | Invoice generation, payments, billing search | `test_uat_invoices.py` |
| 5 | Reports, calculator tools | `test_uat_reports.py`, `test_uat_tools.py` |
| 6 | **Full E2E suite** — all above + complete workflow | `test_uat_e2e.py` |

**Commands:**

```bash
# Start app + db for UAT
docker compose -f docker-compose.uat.yml up -d web db

# Run all UATs
docker compose -f docker-compose.uat.yml run --rm uat

# Run specific phase
docker compose -f docker-compose.uat.yml run --rm uat pytest tests/uat/test_uat_auth.py -v

# Cleanup
docker compose -f docker-compose.uat.yml down -v
```

UAT scripts are updated progressively as each phase completes to match actual page structure and output.

### 14.9 CI Integration (Future)

When a CI pipeline is added (GitHub Actions, etc.), it should run:

```yaml
# .github/workflows/test.yml (structure)
jobs:
  test:
    steps:
      - Checkout
      - Build Docker images
      - Start services (docker compose up -d)
      - Wait for health checks
      - Run: pytest --cov=app --cov-fail-under=80 --junitxml=results.xml
      - Upload coverage report as artifact
      - Fail the build on any test failure or coverage below threshold
```

---

## 15. Cloud Deployment and Integration Readiness

### 15.1 Deployment Scenarios

The application supports four deployment scenarios:

| Scenario | Target | Database | Redis | Notes |
|----------|--------|----------|-------|-------|
| **Local Docker (Pi)** | Raspberry Pi 4/5 (ARM64) | Local MariaDB container | Local Redis container | Lightweight profile (Huey optional), Pi-optimized MariaDB tuning |
| **Local Docker (x86-64)** | Desktop/server | Local MariaDB container | Local Redis container | Full 5-container stack |
| **Remote DB** | Any Docker host | External managed DB (AWS RDS, GCP Cloud SQL, etc.) | Local or managed Redis | Set `DSM_DATABASE_URL` to external host, omit `db` service |
| **Cloud (managed)** | AWS ECS/Fargate, GCP Cloud Run, Azure Container Apps | Managed MariaDB-compatible (RDS, Cloud SQL, Azure DB) | Managed Redis (ElastiCache, Memorystore, Azure Cache) | Container image pushed to registry, orchestrated by cloud platform |

### 15.2 Cloud Provider Guides

Each cloud guide should cover:

- **Container registry**: Push `dsm-web` image to ECR/GCR/ACR
- **Managed database**: Provision MariaDB-compatible instance, configure `DSM_DATABASE_URL`
- **Managed Redis**: Provision Redis instance, configure `DSM_REDIS_URL` and `DSM_CELERY_BROKER_URL`
- **Secrets management**: Store `DSM_SECRET_KEY`, DB passwords, etc. in AWS Secrets Manager / GCP Secret Manager / Azure Key Vault
- **Networking**: VPC/VNet configuration, security groups for DB and Redis access
- **Health/readiness probes**: `/health` endpoint already exists; cloud platforms use it for load balancer health checks and rolling deployments
- **Persistent storage**: S3/GCS/Azure Blob for uploads (requires future `DSM_STORAGE_BACKEND` abstraction)
- **Backups**: Managed DB automated backups, S3 backup of uploads directory
- **Scaling**: Horizontal scaling of web containers (stateless except uploads); single worker + beat instance

### 15.3 Environment Variable Additions for Cloud

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_STORAGE_BACKEND` | `local` | Storage backend for uploads: `local`, `s3`, `gcs` (future) |
| `DSM_S3_BUCKET` | (none) | S3 bucket name for uploads (when `DSM_STORAGE_BACKEND=s3`) |
| `DSM_S3_REGION` | (none) | AWS region for S3 |
| `DSM_S3_PREFIX` | `uploads/` | Key prefix within S3 bucket |
| `DSM_ALLOWED_HOSTS` | `*` | Comma-separated allowed hostnames (for proxy header validation) |
| `DSM_FORCE_HTTPS` | `false` | Redirect all HTTP to HTTPS |
| `DSM_TRUSTED_PROXIES` | (none) | Comma-separated trusted proxy IPs (for `X-Forwarded-For` handling) |

### 15.4 Health and Readiness Endpoints

- `GET /health` — Returns 200 if app is running (already implemented)
- `GET /health/ready` — Returns 200 only if DB and Redis connections are healthy (implemented)
- `GET /health/live` — Returns 200 always (Kubernetes liveness probe, implemented)

---

## 16. Documentation Suite

### 16.1 Architecture Document (`docs/architecture.md`)

Comprehensive technical reference for developers and operators:

- **System overview**: High-level diagram of containers, data flow, and external integrations
- **Application architecture**: Flask app factory, blueprint registration, extension initialization, request lifecycle
- **Data model**: ER diagram, model relationships, migration chain, key design decisions (polymorphic tags, soft deletes, price snapshots, many-to-many invoices)
- **Service layer**: Business logic patterns, when to use services vs. direct model access
- **Authentication and authorization**: Flask-Security-Too configuration, role hierarchy, permission matrix, decorator usage
- **Search architecture**: FULLTEXT index strategy, global search implementation, per-entity search, tag filtering
- **Background tasks**: Celery/Huey task registration, beat schedule, notification checks
- **Configuration hierarchy**: ENV → instance config → DB system_config → app defaults
- **Docker architecture**: Container roles, networking, volume strategy, health checks

### 16.2 User Guide (`docs/user_guide.md`)

Task-oriented guide organized by user role, derived from UAT scripts but restructured for discoverability:

- **Getting Started**: Login, dashboard overview, navigation, theme selection
- **Managing Customers**: Create individual/business customer, search, edit, view history, quick-create from order form
- **Service Orders**: Create order, add items, apply services from price list, add custom charges, add parts/labor, write service notes, change status, view timeline
- **Serial Number Lookup**: Look up equipment by serial, view service history, create new item
- **Inventory Management**: Add parts, adjust stock, view low-stock alerts, track usage
- **Price List**: Browse services by category, understand pricing, apply to orders
- **Invoicing**: Generate invoice from order, edit line items, record payments, track deposits, void/refund
- **Billing Search**: Find invoices by number, customer, date range, amount, status
- **Reports**: Run each report type, filter by date range, export results
- **Tools**: Use seal size calculator, material estimator, pricing calculator, unit converter
- **Admin Tasks**: Manage users, configure settings, view audit log, import/export data, backup database

### 16.3 Installation Guide (`docs/installation.md`)

Step-by-step installation for each deployment scenario:

- **Prerequisites**: Docker, Docker Compose, hardware requirements (Pi: 4GB+ RAM recommended)
- **Quick Start (Local Docker)**: Clone, copy `.env.example`, run `scripts/setup.sh`, access at localhost:8080
- **Raspberry Pi Setup**: OS preparation, Docker installation on ARM64, lightweight profile, Pi-specific MariaDB tuning, performance expectations
- **Remote Database**: Configure external MariaDB, modify `docker-compose.yml` to omit `db` service, set `DSM_DATABASE_URL`
- **Cloud Deployment (AWS)**: ECR push, RDS provisioning, ElastiCache, ECS task definition, ALB configuration
- **Cloud Deployment (GCP)**: GCR push, Cloud SQL, Memorystore, Cloud Run service
- **Cloud Deployment (Azure)**: ACR push, Azure Database for MariaDB, Azure Cache, Container Apps
- **Upgrade procedure**: `scripts/setup.sh upgrade` — pulls latest, runs migrations, restarts
- **Backup and restore**: `scripts/setup.sh backup` / `scripts/setup.sh restore`
- **Troubleshooting**: Common issues (port conflicts, DB connection refused, migration failures, permission errors)

### 16.4 Configuration Reference (`docs/configuration.md`)

Complete reference for all configuration options:

- **Environment variables**: Full table with variable name, default, description, and which deployment scenarios require it
- **Database-stored settings**: All `system_config` keys by category, with defaults and descriptions
- **Docker Compose profiles**: Full vs. lightweight, port binding, volume configuration
- **MariaDB tuning**: `custom.cnf` parameters explained, Pi-optimized values
- **Security settings**: Password policy, lockout, session lifetime, HTTPS enforcement

---

## 17. Development Process & Quality Gates

### 17.1 Worktree-Based Parallel Development

Development uses git worktrees to enable parallel agent work in isolated directories. Each agent operates in its own worktree, avoiding conflicts between concurrent changes. This allows multiple features or fixes to be developed simultaneously without branch switching or merge conflicts during active development.

### 17.2 Wave Structure

Work is organized into waves for dependency management:

- **Wave A**: Independent tasks with no cross-dependencies (can run in parallel)
- **Wave B**: Tasks that depend on Wave A outputs
- **Wave C**: Integration, audit, and documentation tasks that depend on A+B

Within each wave, tasks are assigned to parallel agents. Dependencies between waves are explicit: Wave B agents receive the merged output of Wave A before starting.

### 17.3 Review Pipeline

Every change goes through a multi-stage review before merge:

1. **Dev agent** implements the feature/fix in an isolated worktree
2. **Lead review** checks architecture alignment, code quality, and test coverage
3. **QA agent** runs targeted tests and verifies acceptance criteria
4. **Security agent** audits for injection, auth bypass, data exposure, and other vulnerabilities
5. **Merge** via cherry-pick into the main branch

### 17.4 Cherry-Pick Merge Strategy

Rather than merging feature branches directly, individual commits are cherry-picked onto master. This keeps the commit history linear and allows selective inclusion of changes. Each cherry-picked commit is verified with a full test suite run before pushing.

### 17.5 Post-Wave Security Audit

At the end of each wave (after all tasks are merged), a dedicated security review examines:

- New routes for auth/role enforcement
- Database queries for injection vectors
- File handling for path traversal
- Input validation completeness
- Audit log coverage for new write paths

### 17.6 Testing Strategy

- **During development**: Run targeted tests related to the feature being built (e.g., `pytest tests/unit/models/test_service_item.py -v`)
- **At wave milestones**: Run the full test suite to catch regressions (`pytest`)
- **Pre-push**: Full suite must pass with no failures
- **Docker-based testing preferred**: Use the persistent test container (`docker-compose.test-dev.yml`) to avoid rebuild overhead and permission issues
- **Resource-capped test containers**: Regenerate sane host-based defaults with `./scripts/configure_test_resources.sh`, then run test Docker commands through `./scripts/test-compose.sh` so the checked-in caps file is required and shell overrides do not silently bypass it
- **Coverage target**: 80% minimum (currently ~92%)

---

### Critical Files for Implementation

- `/home/llathrop/Projects/Dive_Service_Management/app/__init__.py` - Application factory: the entry point where Flask app is created, extensions initialized, blueprints registered. Must be built first as everything depends on it.
- `/home/llathrop/Projects/Dive_Service_Management/app/models/mixins.py` - Shared model mixins (TimestampMixin, SoftDeleteMixin, AuditMixin): defines patterns used by every model in the system, so establishing these correctly first ensures consistency.
- `/home/llathrop/Projects/Dive_Service_Management/app/templates/base.html` - Master layout template: defines the left nav, tab bar, header, footer, and content area structure that every page inherits. All UI work depends on this being right.
- `/home/llathrop/Projects/Dive_Service_Management/docker-compose.yml` - Container orchestration: defines all five services, networking, volumes, and environment variable references. Required for any local development or deployment.
- `/home/llathrop/Projects/Dive_Service_Management/app/services/order_service.py` - Service order business logic: the most complex domain logic in the system, handling status transitions, item attachment, parts/labor aggregation, and invoice generation triggers. Getting this architecture right is critical.
