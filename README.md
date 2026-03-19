# Dive Service Management (DSM)

A web-based service order management system designed for dive equipment repair businesses. Tracks customers, service orders, inventory, invoicing, and provides reporting and specialized repair tools.

While initially built for a drysuit repair shop, the architecture supports any item-repair business workflow.

## Features

- **Customer Management** — individual and business customer records with contact info, service history, and lifetime value tracking
- **Service Orders** — full workflow from intake through pickup, with status tracking, technician assignment, priority management, and kanban-style views
- **Service Items** — equipment tracking by serial number with drysuit-specific fields (seals, zippers, valves, materials)
- **Inventory** — parts and materials management with stock levels, reorder alerts, purchase cost and resale price tracking
- **Price Lists** — categorized service pricing with associated parts lists for quick order building
- **Invoicing** — invoice generation from service orders, line item management, payment recording, and status tracking
- **Reports** — revenue, orders, inventory, customer, and accounts receivable aging reports with Chart.js visualizations
- **Repair Tools** — seal size calculator, material estimator, pricing calculator, leak test log, valve reference guide, unit converter
- **Notifications** — in-app alerts for low stock, order status changes, and payment events; email notifications via SMTP
- **Saved Searches** — per-user saved filter combinations with reusable macro across all list views
- **Data Export** — CSV and XLSX export for customers, inventory, orders, and invoices; streaming CSV for large datasets
- **Data Import** — column mapping wizard with fuzzy auto-detect, CSV and XLSX support, row-level validation
- **File Attachments** — polymorphic file uploads with mobile camera capture (HTML5 capture="environment")
- **Admin Panel** — user management with role-based access control (admin, technician, viewer), editable system settings, audit log viewer, application log viewer, data management with backup/import
- **Inline Quick-Create** — dropdown creation for customers, inventory items, price list categories, and tags without leaving the current form
- **In-App Documentation** — built-in docs viewer accessible from the sidebar
- **Theme Support** — light, dark, and auto themes via Bootstrap 5 with company branding

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12+, Flask 3.1 |
| Database | MariaDB 11 LTS (SQLite for development/testing) |
| ORM | SQLAlchemy 2.0 with Flask-Migrate (Alembic) |
| Auth | Flask-Security-Too (argon2 password hashing, role-based access) |
| Frontend | Jinja2 templates, Bootstrap 5.3, HTMX 2.0, Alpine.js 3.14 |
| Charts | Chart.js 4.x |
| PDF | fpdf2 (invoices, price lists) |
| Email | smtplib (SMTP notifications, configurable from admin UI) |
| Server | Gunicorn (production), Flask dev server (development) |
| Container | Docker + Docker Compose |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd Dive_Service_Management

# Copy environment configuration
cp .env.example .env
# Edit .env with your settings (database passwords, secret key)

# Build and start containers
# Migrations and database seeding run automatically on startup
docker compose up -d --build

# Create an admin user (first time only)
docker compose exec web flask create-admin
```

The application will be available at `http://localhost:8080`.

Database migrations and default seeding (roles, price list categories) run
automatically each time the web container starts via `docker-entrypoint.sh`.
You do not need to run `flask db upgrade` or `flask seed-db` manually.

### Demo Accounts

After seeding (automatic on startup), these demo accounts are available
in development/testing mode (`DSM_DEBUG=true`):

| Email | Password | Role |
|-------|----------|------|
| admin@example.com | admin123 | Admin |
| tech@example.com | tech123 | Technician |
| viewer@example.com | viewer123 | Viewer |

## Development

### Local Development (without Docker)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up environment
cp .env.example .env
# SQLite is used by default in development

# Initialize database
flask db upgrade
flask seed-db

# Run development server
flask run --port 8080
```

### Running Tests

```bash
# Run all tests
python3 -m pytest

# Run specific test categories
python3 -m pytest -m smoke      # Smoke tests
python3 -m pytest -m unit       # Unit tests
python3 -m pytest -m blueprint  # Route/blueprint tests

# Run with coverage report
python3 -m pytest --cov=app --cov-report=html
```

### Docker-based Testing

```bash
# One-off test run
docker compose -f docker-compose.test.yml run --rm test

# Persistent test container (avoids rebuild overhead)
docker compose -f docker-compose.test.yml up -d test
docker compose -f docker-compose.test.yml exec test pytest
```

## Project Structure

```
app/
  __init__.py          # Application factory
  config.py            # Configuration classes
  extensions.py        # Flask extension initialization
  blueprints/          # Route handlers (17 blueprints)
  models/              # SQLAlchemy models
  services/            # Business logic layer
  forms/               # WTForms form classes
  templates/           # Jinja2 templates
  static/              # CSS, JS, images
  cli/                 # Flask CLI commands
migrations/            # Alembic database migrations
tests/                 # Test suite (1418 tests)
  smoke/               # Application startup and health tests
  unit/                # Model and service unit tests
  blueprint/           # Route and view tests
  uat/                 # User acceptance test infrastructure
docs/                  # Documentation and UAT scripts
```

## Architecture

The application follows the **app factory** pattern with a layered architecture:

- **Blueprints** handle HTTP routing and request/response processing
- **Services** contain business logic and data operations
- **Models** define the data schema using SQLAlchemy ORM
- **Forms** handle input validation using WTForms

Role-based access control is enforced at the blueprint level using Flask-Security-Too decorators. Database operations use soft deletes where appropriate to prevent accidental data loss.

## Configuration

All configuration is managed through environment variables (prefixed with `DSM_`). See `.env.example` for the full list of available settings.

Key configuration:

| Variable | Description |
|----------|-------------|
| `DSM_SECRET_KEY` | Flask secret key (required) |
| `DSM_DATABASE_URL` | Database connection string |
| `DSM_PORT` | Application port (default: 8080) |
| `DSM_DEBUG` | Enable debug mode (default: false) |

## Deployment

### Docker Compose (Recommended)

The included `docker-compose.yml` provides a production-ready setup with:

- **web** — Flask application with Gunicorn
- **db** — MariaDB 11 LTS with health checks and persistent storage
- **redis** — Redis for Celery broker and caching
- **worker** — Celery worker for background tasks
- **beat** — Celery Beat for scheduled tasks (low stock checks, overdue alerts)

Both containers support ARM64 (Raspberry Pi) and x86-64 architectures.

### Raspberry Pi

The application runs on Raspberry Pi 4+ with 4GB RAM. Use the standard Docker Compose setup; all container images provide multi-architecture support.

## Documentation

Detailed documentation is available in the `docs/` directory:

- [Architecture](docs/architecture.md) — system design, data model, service layer patterns
- [User Guide](docs/user_guide.md) — task-oriented guide by user role
- [Installation](docs/installation.md) — setup for Docker, Pi, and cloud deployments
- [Configuration](docs/configuration.md) — environment variables and system settings reference
- [Cloud Deployment](docs/cloud_deployment.md) — AWS, GCP, and Azure deployment guides

## Known Limitations & TODOs

The codebase currently has no TODO, FIXME, or HACK comments. The following
items were identified during codebase audit and are tracked here for future
sprint planning:

- **`tag_filter` macro references missing `api.tag_suggestions` endpoint** --
  The `tag_filter` macro in `app/templates/macros/tags.html` calls
  `url_for('api.tag_suggestions', ...)` but no `api` blueprint or
  `tag_suggestions` route exists. The macro is currently unused in any
  template, so this causes no runtime errors. Implementing the endpoint
  or removing the macro should happen before any template uses it.

- **`export_service.py` CSV functions are duplicated between buffered and
  streaming paths** -- The column definitions and row extractors appear in
  both the `export_*_csv()` functions and the `_STREAMING_ENTITY_DEFS`
  registry. A future refactor could unify them.

## License

See [LICENSE](LICENSE) for details.
