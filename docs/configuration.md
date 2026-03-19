# Configuration Reference

Complete reference for all configuration options in Dive Service Management (DSM).

## Table of Contents

- [Environment Variables](#environment-variables)
- [Database-Stored Settings](#database-stored-settings)
- [Docker Compose Services](#docker-compose-services)
- [MariaDB Tuning](#mariadb-tuning)

---

## Environment Variables

Environment variables are defined in the `.env` file (copied from `.env.example`) and loaded by both Docker Compose and the Flask application. All application-specific variables use the `DSM_` prefix. MariaDB variables use the `MARIADB_` prefix expected by the official Docker image.

### Flask Application

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_SECRET_KEY` | `change-me-in-production` | Secret key for session signing, CSRF tokens, and cryptographic operations. **Must be changed in production.** Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `DSM_SECURITY_PASSWORD_SALT` | `change-me-salt-in-production` | Salt for Flask-Security-Too password hashing. **Must be changed in production.** Generate separately from the secret key. |
| `DSM_ENV` | `development` | Application environment. Determines which config class is loaded. Values: `development`, `production`, `testing`. Takes precedence over the deprecated `FLASK_ENV`. |
| `DSM_DEBUG` | `false` | Enable Flask debug mode. **Never enable in production.** |
| `DSM_LOG_LEVEL` | `INFO` | Logging verbosity. Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

### Network and Server

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_PORT` | `8080` | Host-side port for the web application. The container always listens on port 8080 internally. |
| `DSM_BIND_ADDRESS` | `0.0.0.0` | Network interface to bind to. `0.0.0.0` accepts connections on all interfaces. Use `127.0.0.1` to restrict to localhost. |
| `DSM_WORKERS` | `2` | Number of Gunicorn worker processes. Use 2 for Raspberry Pi, 2-4 for x86-64 servers. General rule: `(2 * CPU_cores) + 1`. |
| `DSM_THREADS` | `4` | Number of threads per Gunicorn worker. |

### Database (MariaDB)

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_DATABASE_URL` | `mysql+mysqldb://dsm:dsm@db:3306/dsm` | Full SQLAlchemy database URI. The default points to the Docker Compose `db` service. For external databases, use: `mysql+mysqldb://user:pass@host:3306/dbname?charset=utf8mb4`. |
| `MARIADB_ROOT_PASSWORD` | *(none, required)* | Root password for the MariaDB Docker container. Set on first run only. |
| `MARIADB_DATABASE` | `dsm` | Database name created by the MariaDB container on first run. Must match the database in `DSM_DATABASE_URL`. |
| `MARIADB_USER` | `dsm` | Application database user created by the MariaDB container on first run. Must match the user in `DSM_DATABASE_URL`. |
| `MARIADB_PASSWORD` | *(none, required)* | Password for the application database user. Must match the password in `DSM_DATABASE_URL`. |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_REDIS_URL` | `redis://redis:6379/0` | Redis connection URL for caching and session storage. |

### Celery Task Queue

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_CELERY_BROKER_URL` | `redis://redis:6379/1` | Celery message broker URL. Uses Redis database 1 (separate from the cache database). |
| `DSM_CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | Celery result storage URL. Uses Redis database 2. |

### File Uploads

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_UPLOAD_FOLDER` | `/app/uploads` | Directory for uploaded files inside the container. Mapped to `./uploads` on the host via Docker volume. |
| `DSM_MAX_CONTENT_LENGTH` | `16777216` (16 MB) | Maximum upload file size in bytes. Requests exceeding this limit receive a 413 error. |

### Mail (Placeholder)

These variables are defined but mail functionality is not yet active:

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_MAIL_SERVER` | `localhost` | SMTP server hostname. |
| `DSM_MAIL_PORT` | `25` | SMTP server port. |
| `DSM_MAIL_USE_TLS` | `false` | Enable TLS for SMTP connections. |
| `DSM_MAIL_USERNAME` | *(none)* | SMTP authentication username. |
| `DSM_MAIL_PASSWORD` | *(none)* | SMTP authentication password. |

### Database Maintenance

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_AUTO_BACKUP_ON_UPGRADE` | `true` | When `true`, the web container automatically creates a compressed `mariadb-dump` backup before applying pending Alembic migrations. Backups are stored in `./backups/` on the host. Set to `false` to disable. The backup is best-effort: if it fails, a warning is logged but migration proceeds normally. |

### Deployment Profile

| Variable | Default | Description |
|----------|---------|-------------|
| `DSM_DEPLOYMENT_PROFILE` | `full` | Deployment profile. `full` uses Celery for background tasks. `lightweight` is reserved for a future Huey-based alternative suitable for Raspberry Pi. |

### ENV Override Variables

These environment variables, when set, override the corresponding database-stored settings and make them read-only in the admin UI:

| Variable | Overrides Config Key | Description |
|----------|---------------------|-------------|
| `DSM_COMPANY_NAME` | `company.name` | Company name displayed in the header and on invoices. |
| `DSM_PAGINATION_SIZE` | `display.pagination_size` | Default number of rows per page in list views. |
| `DSM_PASSWORD_MIN_LENGTH` | `security.password_min_length` | Minimum password length for new accounts. |
| `DSM_SESSION_LIFETIME_HOURS` | `security.session_lifetime_hours` | Session timeout in hours. |

---

## Database-Stored Settings

System configuration is stored in the `system_config` table and managed via the Admin > Settings page. Each setting has a key, value, type, category, and description. The seed command creates 29 default entries on first run.

Settings are resolved in order: ENV variable (if mapped) > database value > default.

### Company Settings

| Key | Default | Type | Description |
|-----|---------|------|-------------|
| `company.name` | `Dive Service Management` | string | Company name displayed in the page header and on invoices. |
| `company.address` | *(empty)* | string | Company street address for invoices and correspondence. |
| `company.phone` | *(empty)* | string | Company phone number. |
| `company.email` | *(empty)* | string | Company contact email address. |
| `company.logo_path` | *(empty)* | string | Path to the uploaded company logo file. |
| `company.website` | *(empty)* | string | Company website URL. |

### Invoice Settings

| Key | Default | Type | Description |
|-----|---------|------|-------------|
| `invoice.prefix` | `INV` | string | Prefix for generated invoice numbers (e.g., INV-2026-00001). |
| `invoice.next_number` | `1` | integer | Next sequential invoice number. Incremented automatically after each invoice is created. |
| `invoice.default_terms` | `Net 30` | string | Default payment terms text printed on invoices. |
| `invoice.default_due_days` | `30` | integer | Number of days from issue date until an invoice is due. |
| `invoice.footer_text` | *(empty)* | string | Text printed at the bottom of invoices (e.g., "Thank you for your business"). |

### Tax Settings

| Key | Default | Type | Description |
|-----|---------|------|-------------|
| `tax.default_rate` | `0.0000` | float | Default tax rate as a decimal fraction. For example, `0.0825` represents 8.25%. The UI displays this multiplied by 100. |
| `tax.label` | `Sales Tax` | string | Label for the tax line on invoices (e.g., "Sales Tax", "VAT", "GST"). |

### Service Settings

| Key | Default | Type | Description |
|-----|---------|------|-------------|
| `service.order_prefix` | `SO` | string | Prefix for generated order numbers (e.g., SO-2026-00001). |
| `service.next_order_number` | `1` | integer | Next sequential order number. Incremented automatically after each order is created. |
| `service.default_labor_rate` | `75.00` | float | Default hourly rate for labor entries (in the configured currency). |
| `service.rush_fee_default` | `50.00` | float | Default rush fee applied to rush-priority orders. |

### Notification Settings

| Key | Default | Type | Description |
|-----|---------|------|-------------|
| `notification.low_stock_check_hours` | `6` | integer | Hours between automatic low-stock inventory checks. The Celery beat scheduler triggers this check periodically. |
| `notification.overdue_check_time` | `08:00` | string | Time of day (HH:MM format) for the scheduled overdue invoice check. |
| `notification.retention_days` | `90` | integer | Number of days to keep notifications before they are eligible for cleanup. |
| `notification.order_due_warning_days` | `2` | integer | Number of days before an order's promised date to generate an "approaching due" notification. |

### Display Settings

| Key | Default | Type | Description |
|-----|---------|------|-------------|
| `display.date_format` | `%Y-%m-%d` | string | Python strftime format string for date display throughout the UI. |
| `display.currency_symbol` | `$` | string | Currency symbol displayed before monetary values. |
| `display.currency_code` | `USD` | string | ISO 4217 currency code. |
| `display.pagination_size` | `25` | integer | Default number of rows per page in list views. |

### Security Settings

| Key | Default | Type | Description |
|-----|---------|------|-------------|
| `security.password_min_length` | `8` | integer | Minimum password length for new user accounts and password changes. |
| `security.lockout_attempts` | `5` | integer | Number of consecutive failed login attempts before an account is temporarily locked. |
| `security.lockout_duration_minutes` | `15` | integer | Duration of account lockout in minutes after exceeding failed attempt threshold. |
| `security.session_lifetime_hours` | `24` | integer | How long a user session remains valid without activity. |

---

## Docker Compose Services

The `docker-compose.yml` file defines five services connected over a private bridge network (`dsm-net`).

### web

The main Flask application served by Gunicorn.

| Setting | Value |
|---------|-------|
| Image | `dsm-web:latest` (built from Dockerfile) |
| Port | `${DSM_PORT:-8080}` mapped to container port 8080 |
| Depends on | `db` (healthy), `redis` (healthy) |
| Volumes | `./uploads:/app/uploads`, `./logs:/app/logs`, `./instance:/app/instance` |
| Health check | `curl -f http://localhost:8080/health` every 30s |
| Restart | `unless-stopped` |
| Entrypoint | `docker-entrypoint.sh` -- runs migrations and seeding before starting Gunicorn |
| Command | `gunicorn --bind 0.0.0.0:8080 --workers 2 --threads 4 --timeout 120 app:create_app()` |

### db

MariaDB 11 LTS database server.

| Setting | Value |
|---------|-------|
| Image | `mariadb:lts` |
| Volumes | `dsm-db-data:/var/lib/mysql` (named volume, persistent), `./docker/db/init:/docker-entrypoint-initdb.d`, `./docker/db/conf:/etc/mysql/conf.d` |
| Environment | `MARIADB_ROOT_PASSWORD`, `MARIADB_DATABASE`, `MARIADB_USER`, `MARIADB_PASSWORD` |
| Health check | `healthcheck.sh --connect --innodb_initialized` every 10s |
| Restart | `unless-stopped` |

On first start, the MariaDB container creates the database and user from environment variables. The `docker/db/init/` directory can contain `.sql` files that run during initialization.

### redis

Redis 7 Alpine for caching, sessions, and Celery message brokering.

| Setting | Value |
|---------|-------|
| Image | `redis:7-alpine` |
| Command | `redis-server --appendonly yes --maxmemory 64mb --maxmemory-policy allkeys-lru` |
| Volumes | `dsm-redis-data:/data` (named volume, persistent) |
| Health check | `redis-cli ping` every 10s |
| Restart | `unless-stopped` |

Redis is configured with:
- **AOF persistence** (`--appendonly yes`) for data durability across restarts
- **64 MB memory limit** with **LRU eviction** to prevent unbounded growth
- No external port exposure (accessible only within `dsm-net`)

### worker

Celery worker for asynchronous task processing.

| Setting | Value |
|---------|-------|
| Image | `dsm-web:latest` (same image as web) |
| Command | `celery -A app.celery_app worker --loglevel=info --concurrency=2` |
| Depends on | `db` (healthy), `redis` (healthy) |
| Volumes | `./uploads:/app/uploads`, `./logs:/app/logs` |
| Health check | `celery inspect ping` every 60s |
| Restart | `unless-stopped` |

The worker does not run migrations or seeding (the entrypoint script only runs those for Gunicorn). Concurrency is set to 2 (suitable for Pi hardware).

### beat

Celery Beat scheduler for periodic tasks.

| Setting | Value |
|---------|-------|
| Image | `dsm-web:latest` (same image as web) |
| Command | `celery -A app.celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule` |
| Depends on | `redis` (healthy) |
| Health check | `pgrep -f 'celery.*beat'` every 60s |
| Restart | `unless-stopped` |

The beat schedule file is stored in `/tmp/` inside the container and does not need to persist across restarts.

### Named Volumes

| Volume | Container Mount | Purpose |
|--------|----------------|---------|
| `dsm-db-data` | `/var/lib/mysql` | Database files. Persists across container recreation and host restarts. |
| `dsm-redis-data` | `/data` | Redis AOF data. Persists across container restarts. |

### Bind Mounts

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `./uploads` | `/app/uploads` | User-uploaded files (logos, CSV imports, export downloads, attachments). |
| `./logs` | `/app/logs` | Application log files. |
| `./instance` | `/app/instance` | Instance-specific Python config overrides (`instance/config.py`). |
| `./docker/db/init` | `/docker-entrypoint-initdb.d` | SQL scripts run on first database initialization. |
| `./docker/db/conf` | `/etc/mysql/conf.d` | MariaDB configuration overrides (`custom.cnf`). |

---

## MariaDB Tuning

The file `docker/db/conf/custom.cnf` provides default MariaDB configuration tuned for memory-constrained environments (Raspberry Pi with 4 GB RAM). All parameters are in the `[mysqld]` section.

### Character Set

| Parameter | Value | Description |
|-----------|-------|-------------|
| `character-set-server` | `utf8mb4` | Full Unicode support including emoji and CJK characters. |
| `collation-server` | `utf8mb4_unicode_ci` | Case-insensitive Unicode collation for sorting and comparisons. |

### InnoDB Engine

| Parameter | Value | Description |
|-----------|-------|-------------|
| `innodb_buffer_pool_size` | `128M` | Memory allocated for caching table data and indexes. This is the most impactful tuning parameter. For systems with 8+ GB RAM, increase to 256M-512M. |
| `innodb_log_file_size` | `32M` | Size of the redo log files. Larger values improve write performance for batch operations but increase recovery time. |
| `innodb_flush_log_at_trx_commit` | `2` | Flush log to OS cache (not disk) on each commit. Provides good performance with acceptable durability -- data is safe unless the OS crashes (not just the database process). Set to `1` for strict durability at the cost of write speed. |
| `innodb_flush_method` | `O_DIRECT` | Bypass the OS file cache for data files (InnoDB manages its own cache via buffer pool). Reduces double-buffering and memory waste. |

### Full-Text Search

| Parameter | Value | Description |
|-----------|-------|-------------|
| `innodb_ft_min_token_size` | `2` | Minimum word length for InnoDB FULLTEXT indexes. Set to 2 to support short part numbers and abbreviations (e.g., "O2", "DI"). The default (3) would exclude these. |

### Connection Limits

| Parameter | Value | Description |
|-----------|-------|-------------|
| `max_connections` | `30` | Maximum simultaneous database connections. Sufficient for the web app (2 Gunicorn workers with connection pooling), worker (2 concurrent tasks), and beat. Increase for higher-traffic deployments. |
| `thread_cache_size` | `4` | Number of threads to cache for reuse. Reduces thread creation overhead for frequently opening/closing connections. |

### Memory Allocation

| Parameter | Value | Description |
|-----------|-------|-------------|
| `key_buffer_size` | `16M` | Buffer for MyISAM index blocks. Kept small since DSM uses InnoDB exclusively. |
| `table_open_cache` | `200` | Number of open table descriptors to cache. Sufficient for the application's ~20 tables with concurrent access. |
| `tmp_table_size` | `16M` | Maximum size for in-memory temporary tables before they spill to disk. |
| `max_heap_table_size` | `16M` | Maximum size for MEMORY engine tables. Should match `tmp_table_size`. |

### Performance Schema

| Parameter | Value | Description |
|-----------|-------|-------------|
| `performance_schema` | `OFF` | Disabled to save approximately 100 MB of RAM. Enable on x86-64 servers with sufficient memory if you need query performance analysis. |

### Logging

| Parameter | Value | Description |
|-----------|-------|-------------|
| `slow_query_log` | `ON` | Enable logging of slow queries. |
| `slow_query_log_file` | `/var/log/mysql/slow.log` | Path to the slow query log file inside the container. |
| `long_query_time` | `2` | Queries taking longer than 2 seconds are logged as slow. |

### Tuning for Larger Systems

For x86-64 servers with 8+ GB RAM, consider these adjustments:

```ini
[mysqld]
innodb_buffer_pool_size = 512M
max_connections = 100
thread_cache_size = 16
table_open_cache = 400
tmp_table_size = 64M
max_heap_table_size = 64M
performance_schema = ON
```

For very high write loads, also consider:

```ini
innodb_log_file_size = 128M
innodb_flush_log_at_trx_commit = 1  # strict durability
```
