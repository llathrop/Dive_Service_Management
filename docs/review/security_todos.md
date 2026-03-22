# Security & Infrastructure Audit -- 2026-03-22

## P0 -- Critical

_(No P0 findings. The application has no critical vulnerabilities that enable remote code execution, authentication bypass, or mass data exposure.)_

## P1 -- High

- [ ] **Missing CSRF token in admin import preview form.** The confirm-import form in `app/templates/admin/import_preview.html:91` submits a POST without a CSRF token. An attacker could craft a page that auto-submits an import, modifying database records. Add `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` inside the form.

- [ ] **Missing CSRF token in admin import upload form.** The file upload form in `app/templates/admin/import_form.html:36` submits a POST without a CSRF token. Add `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` inside the form.

- [ ] **No security headers beyond X-Content-Type-Options.** The application only sets `X-Content-Type-Options: nosniff` on uploaded file responses (`app/__init__.py:189`). Missing from all responses: `X-Frame-Options`, `Content-Security-Policy`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy`. Add an `@app.after_request` handler in `app/__init__.py` to set these on every response.

- [ ] **No session cookie security flags configured.** `app/config.py` does not set `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, or `SESSION_COOKIE_SAMESITE`. Flask defaults `HTTPONLY=True` and `SAMESITE=Lax`, but `SECURE` is False by default, meaning cookies are sent over HTTP. At minimum, `ProductionConfig` should set `SESSION_COOKIE_SECURE = True`.

- [ ] **No rate limiting on login or API endpoints.** There is no rate limiting anywhere in the application (no `flask-limiter` or equivalent). The login endpoint, password reset, and quick-create JSON endpoints are vulnerable to brute-force and abuse. Add `flask-limiter` with sensible defaults (e.g., 5 login attempts per minute).

- [ ] **Export endpoints lack role-based access control.** All four export routes in `app/blueprints/export.py:26-87` only require `@login_required` but no `@roles_accepted`. Any authenticated user (including `viewer` role) can export all customers, inventory, orders, and invoices as CSV/XLSX. Add `@roles_accepted("admin", "technician")` at minimum.

- [ ] **Report endpoints lack role-based access control.** All five report routes in `app/blueprints/reports.py:12-69` only require `@login_required` but no `@roles_accepted`. Revenue and customer reports may expose sensitive financial data to viewer-role users. Add `@roles_accepted("admin", "technician")`.

## P2 -- Medium

- [ ] **SQL injection risk in SQLite table stats.** In `app/services/data_management_service.py:58`, table names from `sqlite_master` are interpolated into a SQL query via f-string: `text(f'SELECT COUNT(*) FROM "{table}"')`. While the table names come from the database itself (not user input) and are double-quoted, this is still a code-smell. Use parameterized queries or validate table names against an allowlist.

- [ ] **Docs `|safe` filter renders Markdown HTML without sanitization.** In `app/templates/docs/detail.html:39`, `{{ content|safe }}` renders Markdown-to-HTML output unsanitized. The content comes from server-side `.md` files (not user input) via an allowlisted slug lookup in `app/blueprints/docs.py:63`, so the risk is low. However, if a doc file were ever to contain user-contributed content, this would be an XSS vector. Consider using `bleach` or `nh3` to sanitize the HTML output from `markdown.markdown()`.

- [ ] **Redis has no authentication configured.** The Redis container in `docker-compose.yml:66-79` runs without `requirepass`. Any process on the Docker network can read/write Redis data including session state and task queues. Add `--requirepass ${REDIS_PASSWORD}` to the Redis command and update the `DSM_REDIS_URL` to include credentials.

- [ ] **Database backup downloads not rate-limited or audit-logged.** The `admin.download_backup` route at `app/blueprints/admin/data.py:46-67` returns a full SQL dump as a download. While it requires admin role, there is no audit log entry for backup downloads, and no rate limit. Add audit logging and consider adding a confirmation step.

- [ ] **Password policy is minimal.** User creation in `app/blueprints/admin/users.py:45` only enforces `len(password) < 8`. There are no complexity requirements (uppercase, digit, special char). The `SystemConfig` has a `security.password_min_length` setting but it is not enforced in the user creation route. Wire the config value into validation.

- [ ] **SMTP password stored in SystemConfig.** Email SMTP password is stored via `config_service` in the database (`app/blueprints/admin/__init__.py:106`). While the settings form skips displaying it (PasswordField handling at line 175), the value is stored in the `system_config` table. Verify it is stored with `is_sensitive=True` so it is not exposed via any config listing endpoint.

- [ ] **Upload route accepts `<path:filename>` without path normalization.** The upload serving route at `app/__init__.py:184` uses `send_from_directory` with a `<path:filename>` parameter. While `send_from_directory` has built-in path traversal protection, this is defense-in-depth territory. Consider adding explicit validation that the resolved path stays within `UPLOAD_FOLDER`.

- [ ] **Default bind address is 0.0.0.0.** In `.env.example:41`, `DSM_BIND_ADDRESS=0.0.0.0` and in `docker-compose.yml:15`, the port mapping defaults to `0.0.0.0`. This exposes the application on all network interfaces. For local/LAN deployments, consider defaulting to `127.0.0.1` and documenting how to open to the network.

## P3 -- Low

- [ ] **Subprocess call in backup service has no shell injection risk but passes password on command line.** In `app/services/data_management_service.py:136-143`, `mariadb-dump` is called with `--password=` on the command line. The password comes from the DB URL config (not user input), but it may appear in process listings (`ps aux`). Consider using `MYSQL_PWD` environment variable instead (as `docker-entrypoint.sh` already does).

- [ ] **Docker image uses `python:3.12-slim` -- not Alpine.** `Dockerfile:9,27` uses `python:3.12-slim` (Debian-based). This is a reasonable choice for compatibility but has a larger attack surface than Alpine. Consider periodic `apt-get update && apt-get upgrade` in the build or switching to a pinned digest.

- [ ] **Gunicorn timeout is 120 seconds.** `Dockerfile:78` sets `--timeout 120`. This is generous and could allow slow-loris style resource exhaustion. Consider reducing to 30-60 seconds for most routes.

- [ ] **MariaDB root password is in `.env` file.** While `.env` is gitignored (`.gitignore:48`), the root password is available to all containers via `env_file: .env`. Consider using Docker secrets for production deployments.

- [ ] **Health endpoints return dependency version info.** The `/health/ready` endpoint at `app/blueprints/health.py:45-75` returns Redis/DB status. The `/health` endpoint returns database status. This is standard but could reveal infrastructure details. For public-facing deployments behind a reverse proxy, ensure these endpoints are not exposed externally.

- [ ] **Celery worker and beat share the same Docker image as web.** `docker-compose.yml:85,112` use the same `dsm-web:latest` image for worker/beat. The worker runs as the `dsm` user (from Dockerfile), which is correct, but the full web application code is available in the container. Consider a slimmer worker image for defense-in-depth.

- [ ] **No Content-Disposition header sanitization for invoice PDF filenames.** In `app/blueprints/invoices.py:395-401`, the invoice number is used directly in the Content-Disposition filename. If invoice numbers contained special characters, this could cause header injection. The risk is low since invoice numbers are auto-generated.

- [ ] **`gunicorn==22.0.0` is pinned but not the latest.** The current latest is 23.x. While no critical CVEs are known for 22.0.0, keeping dependencies current is good practice.

## Auth/Authz Matrix

| Blueprint | Route | Method | Auth | Roles | Status |
|-----------|-------|--------|------|-------|--------|
| auth | `/` | GET | None | None | OK -- intentional public redirect |
| dashboard | `/dashboard/` | GET | login_required | None | OK |
| dashboard | `/dashboard/activity-feed` | GET | login_required | None | OK |
| health | `/health` | GET | None | None | OK -- intentional public probe |
| health | `/health/ready` | GET | None | None | OK -- intentional public probe |
| health | `/health/live` | GET | None | None | OK -- intentional public probe |
| customers | `/customers/` | GET | login_required | None | OK |
| customers | `/customers/<id>` | GET | login_required | None | OK |
| customers | `/customers/new` | GET/POST | login_required | admin, technician | OK |
| customers | `/customers/<id>/edit` | GET/POST | login_required | admin, technician | OK |
| customers | `/customers/<id>/delete` | POST | login_required | admin | OK |
| items | `/items/` | GET | login_required | None | OK |
| items | `/items/lookup` | GET | login_required | None | OK |
| items | `/items/<id>` | GET | login_required | None | OK |
| items | `/items/new` | GET/POST | login_required | admin, technician | OK |
| items | `/items/<id>/edit` | GET/POST | login_required | admin, technician | OK |
| items | `/items/<id>/delete` | POST | login_required | admin | OK |
| items | `/items/quick-create` | POST | login_required | admin, technician | OK |
| inventory | `/inventory/` | GET | login_required | None | OK |
| inventory | `/inventory/low-stock` | GET | login_required | None | OK |
| inventory | `/inventory/<id>` | GET | login_required | None | OK |
| inventory | `/inventory/new` | GET/POST | login_required | admin, technician | OK |
| inventory | `/inventory/<id>/edit` | GET/POST | login_required | admin, technician | OK |
| inventory | `/inventory/<id>/delete` | POST | login_required | admin | OK |
| inventory | `/inventory/<id>/adjust` | POST | login_required | admin, technician | OK |
| inventory | `/inventory/quick-create` | POST | login_required | admin, technician | OK |
| orders | `/orders/` | GET | login_required | None | OK |
| orders | `/orders/kanban` | GET | login_required | admin, technician | OK |
| orders | `/orders/<id>` | GET | login_required | None | OK |
| orders | `/orders/new` | GET/POST | login_required | admin, technician | OK |
| orders | `/orders/<id>/edit` | GET/POST | login_required | admin, technician | OK |
| orders | `/orders/<id>/delete` | POST | login_required | admin | OK |
| orders | `/orders/quick-create-customer` | POST | login_required | admin, technician | OK |
| orders | `/orders/<id>/items/add` | POST | login_required | admin, technician | OK |
| orders | `/orders/items/<id>/remove` | POST | login_required | admin, technician | OK |
| orders | `/orders/items/<id>/services/add` | POST | login_required | admin, technician | OK |
| orders | `/orders/services/<id>/remove` | POST | login_required | admin, technician | OK |
| orders | `/orders/items/<id>/parts/add` | POST | login_required | admin, technician | OK |
| orders | `/orders/parts/<id>/remove` | POST | login_required | admin, technician | OK |
| orders | `/orders/items/<id>/labor/add` | POST | login_required | admin, technician | OK |
| orders | `/orders/labor/<id>/remove` | POST | login_required | admin, technician | OK |
| orders | `/orders/items/<id>/notes/add` | POST | login_required | admin, technician | OK |
| orders | `/orders/<id>/status` | POST | login_required | admin, technician | OK |
| orders | `/orders/<id>/kanban-status` | POST | login_required | admin, technician | OK |
| invoices | `/invoices/` | GET | login_required | None | OK |
| invoices | `/invoices/<id>` | GET | login_required | None | OK |
| invoices | `/invoices/new` | GET/POST | login_required | admin, technician | OK |
| invoices | `/invoices/<id>/edit` | GET/POST | login_required | admin, technician | OK |
| invoices | `/invoices/<id>/void` | POST | login_required | admin | OK |
| invoices | `/invoices/<id>/status` | POST | login_required | admin, technician | OK |
| invoices | `/invoices/<id>/line-items/add` | POST | login_required | admin, technician | OK |
| invoices | `/invoices/line-items/<id>/remove` | POST | login_required | admin, technician | OK |
| invoices | `/invoices/<id>/payments/add` | POST | login_required | admin, technician | OK |
| invoices | `/invoices/<id>/pdf` | GET | login_required | admin, technician | OK |
| invoices | `/invoices/from-order/<id>/generate` | POST | login_required | admin, technician | OK |
| price_list | `/price-list/` | GET | login_required | None | OK |
| price_list | `/price-list/pdf` | GET | login_required | None | OK |
| price_list | `/price-list/<id>` | GET | login_required | None | OK |
| price_list | `/price-list/new` | GET/POST | login_required | admin | OK |
| price_list | `/price-list/<id>/edit` | GET/POST | login_required | admin | OK |
| price_list | `/price-list/<id>/duplicate` | POST | login_required | admin | OK |
| price_list | `/price-list/categories` | GET | login_required | admin | OK |
| price_list | `/price-list/categories/new` | POST | login_required | admin | OK |
| price_list | `/price-list/categories/<id>/edit` | POST | login_required | admin | OK |
| price_list | `/price-list/quick-create` | POST | login_required | admin, technician | OK |
| notifications | `/notifications/` | GET | login_required | None | OK |
| notifications | `/notifications/count` | GET | login_required | None | OK |
| notifications | `/notifications/<id>/read` | POST | login_required | None | OK |
| notifications | `/notifications/mark-all-read` | POST | login_required | None | OK |
| search | `/search/` | GET | login_required | None | OK |
| search | `/search/autocomplete` | GET | login_required | None | OK |
| search | `/search/saved` | GET | login_required | None | OK |
| search | `/search/saved` | POST | login_required | None | OK |
| search | `/search/saved/<id>` | PUT | login_required | None | OK |
| search | `/search/saved/<id>` | DELETE | login_required | None | OK |
| search | `/search/saved/<id>/default` | POST | login_required | None | OK |
| export | `/export/customers/<format>` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| export | `/export/inventory/<format>` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| export | `/export/orders/<format>` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| export | `/export/invoices/<format>` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| reports | `/reports/` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| reports | `/reports/revenue` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| reports | `/reports/orders` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| reports | `/reports/inventory` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| reports | `/reports/customers` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| reports | `/reports/aging` | GET | login_required | **MISSING ROLES** | FINDING (P1) |
| tools | `/tools/` | GET | login_required | None | OK |
| tools | `/tools/seal-calculator` | GET | login_required | None | OK |
| tools | `/tools/material-estimator` | GET | login_required | None | OK |
| tools | `/tools/pricing-calculator` | GET | login_required | None | OK |
| tools | `/tools/leak-test-log` | GET | login_required | None | OK |
| tools | `/tools/valve-reference` | GET | login_required | None | OK |
| tools | `/tools/converter` | GET | login_required | None | OK |
| docs | `/docs/` | GET | login_required | None | OK |
| docs | `/docs/<slug>` | GET | login_required | None | OK |
| attachments | `/attachments/upload` | POST | login_required | admin, technician | OK |
| attachments | `/attachments/<id>/file` | GET | login_required | None | OK |
| attachments | `/attachments/<id>/thumbnail` | GET | login_required | None | OK |
| attachments | `/attachments/<id>` | DELETE | login_required | admin, technician | OK |
| attachments | `/attachments/gallery/...` | GET | login_required | None | OK |
| attachments | `/attachments/gallery/unified/<id>` | GET | login_required | None | OK |
| admin | `/admin/` | GET | roles_required(admin) | admin | OK |
| admin | `/admin/settings` | GET/POST | roles_required(admin) | admin | OK |
| admin | `/admin/audit-log` | GET | roles_required(admin) | admin | OK |
| admin | `/admin/data` | GET | roles_required(admin) | admin | OK |
| admin | `/admin/data/backup` | GET | roles_required(admin) | admin | OK |
| admin | `/admin/data/import` | GET/POST | roles_required(admin) | admin | OK |
| admin | `/admin/import/wizard` | GET | roles_required(admin) | admin | OK |
| admin | `/admin/import/upload` | POST | roles_required(admin) | admin | OK |
| admin | `/admin/import/preview` | POST | roles_required(admin) | admin | OK |
| admin | `/admin/import/execute` | POST | roles_required(admin) | admin | OK |
| admin | `/admin/users` | GET | roles_required(admin) | admin | OK |
| admin | `/admin/users/new` | GET/POST | roles_required(admin) | admin | OK |
| admin | `/admin/users/<id>/edit` | GET/POST | roles_required(admin) | admin | OK |
| admin | `/admin/users/<id>/toggle-active` | POST | roles_required(admin) | admin | OK |
| admin | `/admin/users/<id>/reset-password` | POST | roles_required(admin) | admin | OK |
| admin | `/admin/logs` | GET | roles_required(admin) | admin | OK |
| admin | `/admin/logs/tail` | GET | roles_required(admin) | admin | OK |
| app | `/uploads/<path:filename>` | GET | login_required | None | OK |

## Dependency Audit

| Package | Version | Known Issues |
|---------|---------|-------------|
| Flask | 3.1.3 | No known CVEs for 3.1.x |
| Werkzeug | 3.1.6 | No known CVEs for 3.1.x |
| SQLAlchemy | 2.0.36 | No known CVEs |
| Flask-SQLAlchemy | 3.1.1 | No known CVEs |
| Flask-Migrate | 4.1.0 | No known CVEs |
| mysqlclient | 2.2.6 | No known CVEs |
| Flask-Security-Too | 5.7.0 | No known CVEs |
| argon2-cffi | 23.1.0 | No known CVEs |
| Flask-WTF | 1.2.2 | No known CVEs |
| WTForms | 3.1.2 | No known CVEs |
| email-validator | 2.2.0 | No known CVEs |
| marshmallow | 3.26.2 | No known CVEs |
| celery | 5.4.0 | No known CVEs for 5.4.x |
| redis | 5.2.1 | No known CVEs |
| huey | 2.5.2 | No known CVEs |
| fpdf2 | 2.8.2 | No known CVEs |
| openpyxl | 3.1.5 | No known CVEs |
| python-dotenv | 1.0.1 | No known CVEs |
| gunicorn | 22.0.0 | No CVEs, but 23.x is available. Update recommended. |
| Flask-Mail | 0.10.0 | Unmaintained; consider flask-mailman as a replacement |
| Markdown | 3.10.2 | No known CVEs |
| click | 8.1.7 | No known CVEs |

All dependencies are pinned to exact versions, which is good for reproducibility.

**Notes:**
- No `eval()`, `exec()`, `pickle.loads()`, or unsafe `yaml.load()` calls found anywhere in the application code.
- No raw SQL string formatting with user input found; all user-facing queries use SQLAlchemy ORM with parameterized `.ilike()` patterns.
- The one f-string SQL usage (`data_management_service.py:58`) uses table names from `sqlite_master`, not user input.
- Attachment upload validation is solid: extension allowlist, MIME type check, file size validation, UUID-based storage filenames, `secure_filename()` on originals.
- Logo upload includes magic-byte validation to prevent disguised file uploads.
- Log viewer uses strict allowlist-based path validation to prevent path traversal.
- CSRF tokens are present on all forms except the two import forms noted above.
- HTMX DELETE/POST calls in JS consistently include X-CSRFToken headers from the meta tag.

## Infrastructure

**Docker Security:**
- Non-root user (`dsm`) created and used in Dockerfile -- GOOD
- Multi-stage build separates build deps from runtime -- GOOD
- Named volumes for persistent data -- GOOD
- Internal Docker network (`dsm-net`) isolates services -- GOOD
- Health checks on all five services -- GOOD
- Database port (3306) is NOT exposed to the host -- GOOD

**Backup Logic:**
- Auto-backup before migrations in `docker-entrypoint.sh` -- GOOD
- Uses `--single-transaction` for consistent MariaDB backups -- GOOD
- Graceful failure (warns but continues if backup fails) -- GOOD
- Backup files stored in `/app/backups` with timestamps -- GOOD

**Migration Chain:**
- Linear chain from `initial_schema` through `h8c9d0e1f2g3` -- VERIFIED
- Auto-migration on container startup -- GOOD
- Production mode halts on migration failure -- GOOD

**Production Config:**
- `ProductionConfig.init_app()` rejects default `SECRET_KEY` and `SECURITY_PASSWORD_SALT` -- GOOD
- `.env` files are gitignored -- GOOD
- `.env.example` uses obvious placeholder values that must be changed -- GOOD

## Summary

Total findings: 16 (P0: 0, P1: 7, P2: 8, P3: 8)

**Highest priority actions:**
1. Add CSRF tokens to the two admin import forms
2. Add security response headers (X-Frame-Options, CSP, HSTS, Referrer-Policy)
3. Add `@roles_accepted` to export and report endpoints
4. Set `SESSION_COOKIE_SECURE = True` in ProductionConfig
5. Add rate limiting (flask-limiter) to login and API endpoints
6. Add Redis authentication
