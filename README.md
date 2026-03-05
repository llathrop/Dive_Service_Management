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
- **Notifications** — in-app alerts for low stock, order status changes, and payment events
- **Data Export** — CSV and XLSX export for customers, inventory, orders, and invoices
- **Admin Panel** — user management with role-based access control (admin, technician, viewer), system settings, and data management
- **Theme Support** — light, dark, and auto themes via Bootstrap 5

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12+, Flask 3.1 |
| Database | MariaDB 11 LTS (SQLite for development/testing) |
| ORM | SQLAlchemy 2.0 with Flask-Migrate (Alembic) |
| Auth | Flask-Security-Too (argon2 password hashing, role-based access) |
| Frontend | Jinja2 templates, Bootstrap 5.3, HTMX 2.0, Alpine.js 3.14 |
| Charts | Chart.js 4.x |
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
docker compose up -d --build

# Run database migrations
docker compose exec web flask db upgrade

# Seed default data (roles, demo users, price list categories)
docker compose exec web flask seed-db

# Create an admin user (interactive)
docker compose exec web flask create-admin
```

The application will be available at `http://localhost:8080`.

### Demo Accounts

After running `flask seed-db`, these accounts are available:

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
docker compose -f docker-compose.test.yml run --rm test
```

## Project Structure

```
app/
  __init__.py          # Application factory
  config.py            # Configuration classes
  extensions.py        # Flask extension initialization
  blueprints/          # Route handlers (15 blueprints)
  models/              # SQLAlchemy models
  services/            # Business logic layer
  forms/               # WTForms form classes
  templates/           # Jinja2 templates
  static/              # CSS, JS, images
  cli/                 # Flask CLI commands
migrations/            # Alembic database migrations
tests/                 # Test suite (757+ tests)
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

Both containers support ARM64 (Raspberry Pi) and x86-64 architectures.

### Raspberry Pi

The application runs on Raspberry Pi 4+ with 4GB RAM. Use the standard Docker Compose setup; all container images provide multi-architecture support.

## License

See [LICENSE](LICENSE) for details.
