# Documentation Audit — 2026-03-22

## architecture.md

- [ ] P1: Model count header says "Models (17 total)" but the table lists 23 models (User, Role, Customer, ServiceItem, DrysuitDetails, InventoryItem, PriceListCategory, PriceListItem, PriceListItemPart, Tag, Taggable, ServiceOrder, ServiceOrderItem, AppliedService, PartUsed, LaborEntry, ServiceNote, Invoice, InvoiceLineItem, Payment, Notification, NotificationRead, SystemConfig, AuditLog). Should say "Models (24 total)" — there are also 2 models (Attachment, SavedSearch) present in the codebase but missing from the table entirely, bringing the true total to 26.
- [ ] P1: Models table is missing `Attachment` (`attachments` table, TimestampMixin, entity polymorphic link). The model exists at `app/models/attachment.py` and the migration `f6a7b8c9d0e1` is listed in the migration chain, but the model never appears in the models table.
- [ ] P1: Models table is missing `SavedSearch` (`saved_searches` table, TimestampMixin, User FK). The model exists at `app/models/saved_search.py` and the migration `g7b8c9d0e1f2` is listed in the migration chain, but the model never appears in the models table.
- [ ] P1: ER diagram is missing Attachment and SavedSearch entities and their relationships.
- [ ] P2: Web container health check table (line 439) says `curl -f http://localhost:8080/health` but actual `docker-compose.yml` uses `curl -f http://localhost:8080/health/ready`. The `/health/ready` endpoint checks both DB and Redis, not just DB.
- [ ] P2: Worker health check table (line 442) says `celery inspect ping` but actual `docker-compose.yml` uses a more robust `celery -A app.celery_app inspect ping --timeout 10 2>/dev/null | grep -q OK` command.
- [ ] P2: Beat health check table (line 443) says `pgrep -f 'celery.*beat'` but actual `docker-compose.yml` uses a file-freshness check: `test -f /tmp/celerybeat-schedule && find /tmp/celerybeat-schedule -mmin -3 | grep -q .`
- [ ] P2: Service layer table (lines 281-296) is missing 7 service modules that exist in `app/services/`: `attachment_service.py`, `email_service.py`, `item_service.py`, `log_service.py`, `saved_search_service.py`, `inventory_service.py` (listed but as "Inventory CRUD, stock adjustments" — may need update for refactored scope).
- [ ] P2: Service layer note (line 301) says "Phase 2 blueprints (customers, items, inventory, price_list) access models directly in some routes" — this is outdated. Wave 3a refactored all Phase 2 blueprints to use the service layer. All four now import from `app.services`.
- [ ] P3: Docker volume table (lines 447-456) is missing the `./backups:/app/backups` bind mount that was added for auto-backup in Sprint 2026-03-18.
- [ ] P3: System overview volume diagram (line 50) is missing the `./backups -> /app/backups` volume.

## user_guide.md

- [ ] P2: Settings section (line 514) says "organized into six tabs" but then lists 7 tabs (Company, Invoice, Tax, Service, Notification, Display, Security). Should say "seven tabs".
- [x] P3: Screenshot reference `docs/screenshots/customer_detail.png` (line 118) — captured and added to `docs/screenshots/`.
- [x] P3: Screenshot reference `docs/screenshots/item_detail_service_history.png` (line 165) — captured and added to `docs/screenshots/`.

## installation.md

- [ ] P1: First-time setup section (line 268) says "7 migrations total" but there are actually 11 migration files in `migrations/versions/`. The correct count is 11 (initial_schema, phase_2, phase_3_5, p0_1_inventory_decimal, p0_2_notification_reads, system_config, audit_log, attachments, saved_searches, service_item_customer_required, plus the 11th being the phase_3_5 combined migration).
- [ ] P3: First-time setup says seed-db creates "29 system config entries across 7 categories" — this should be verified against the actual seed function. The configuration.md lists 7 categories which tallies, but the entry count may have changed if email settings were added.

## configuration.md

- [ ] P1: Mail section (lines 67-78) says "These variables are defined but mail functionality is not yet active" — this is outdated. Wave 4B added a working email notification system via `email_service.py` using smtplib. Email is functional, not a placeholder.
- [ ] P2: Worker health check (line 236) says `celery inspect ping` — actual docker-compose.yml uses more robust `celery -A app.celery_app inspect ping --timeout 10 2>/dev/null | grep -q OK`.
- [ ] P2: Beat health check (line 250) says `pgrep -f 'celery.*beat'` — actual docker-compose.yml uses file-freshness check on celerybeat-schedule.
- [ ] P2: Web health check in Docker Compose services section does not document the actual URL used (`/health/ready`). The `web` service table (line 190) says `curl -f http://localhost:8080/health` but actual is `curl -f http://localhost:8080/health/ready`.
- [ ] P3: Missing email-related SystemConfig keys. The email_service reads SMTP settings from SystemConfig but the Database-Stored Settings section does not document any email/SMTP config keys.
- [ ] P3: Missing `DSM_MAIL_*` variables from `.env.example` — the Mail section documents them but they are not present in the actual `.env.example` file. Either add them to `.env.example` or update the docs to note they are configured via the admin UI SystemConfig instead.

## cloud_deployment.md

- [ ] P3: GCP Cloud Run section (line 231) says "Create a Cloud SQL instance with MariaDB 11" but the earlier installation.md GCP section (line 242) says "MariaDB is not natively available" on Cloud SQL. Cloud SQL does support MySQL but not MariaDB directly. The cloud_deployment.md contradicts itself with the installation.md on this point.
- [ ] P3: Azure section (line 325) references "Azure Database for MariaDB flexible server" — Microsoft retired Azure Database for MariaDB. New deployments should use Azure Database for MySQL Flexible Server or a VM-based MariaDB deployment.

## PROJECT_BLUEPRINT.md

- [ ] P3: Section 1.1 lists `WeasyPrint 67.x` as optional — verify this is still an optional dependency or if it was removed entirely. It is not in requirements.txt.
- [ ] P3: Section 1.1 lists `Marshmallow 3.22.x` for serialization — verify if Marshmallow is actually used in the codebase or if it was replaced by direct serialization.
- [ ] P3: Section 1.1 lists `Huey 2.5.x` as alternative task queue — verify if this was ever implemented or remains aspirational.
- [ ] P3: Section 1.2 lists `Tom Select 2.3.x` for searchable selects — verify if this library is actually used or if the project uses plain Bootstrap selects.

## PROGRESS.md

- [ ] P1: "Post-Phase 6: Third Review Fix-ups — CODEX Re-Review" header (line 259) still says "(In Progress)" but based on MEMORY.md and actual completion status, all P0/P1 items listed are checked complete. Should be "(Complete)".

## Missing Screenshots

None. The `customer_detail.png` and `item_detail_service_history.png` assets now
exist under `docs/screenshots/` and are maintained by the screenshot capture
lane.

## Summary

Total findings: 27 (P0: 0, P1: 6, P2: 9, P3: 12)

No P0 (critical/blocking) issues found. The documentation is broadly accurate but has accumulated drift in several areas:
- **Model/service inventory**: architecture.md undercounts models (missing Attachment, SavedSearch) and services (missing 6 modules added in later waves).
- **Health check descriptions**: Three docs files describe outdated health check commands that no longer match docker-compose.yml.
- **Stale status markers**: The email system is documented as a placeholder despite being functional, and PROGRESS.md has an incorrect "In Progress" label.
- **Missing screenshots**: Resolved in Wave 5A by capturing `customer_detail.png`
  and `item_detail_service_history.png` into `docs/screenshots/`.
- **Migration count**: installation.md says 7 migrations but there are 11.
