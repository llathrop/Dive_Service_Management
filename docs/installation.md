# Installation Guide

Step-by-step instructions for deploying Dive Service Management (DSM) in various environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (Local Docker)](#quick-start-local-docker)
- [Raspberry Pi Setup](#raspberry-pi-setup)
- [Remote Database Setup](#remote-database-setup)
- [Cloud Deployment Overview](#cloud-deployment-overview)
- [First-Time Setup](#first-time-setup)
- [Upgrading](#upgrading)
- [Backup and Restore](#backup-and-restore)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Docker Engine** 24.0 or later
- **Docker Compose** v2 (included with Docker Desktop, or install the `docker-compose-plugin` package on Linux)

Verify your installation:

```bash
docker --version       # Docker version 24.0+
docker compose version # Docker Compose version v2.x
```

### Minimum Hardware

| Environment | RAM | CPU | Storage |
|-------------|-----|-----|---------|
| Raspberry Pi | 4 GB (Pi 4/5) | ARM64 | 16 GB+ SD card or SSD |
| Local development | 4 GB | Any x86-64 | 2 GB free |
| Production server | 4 GB+ | 2+ cores | 10 GB+ |

### Network

The application listens on port **8080** by default. Ensure this port is available or configure an alternative via the `DSM_PORT` environment variable.

---

## Quick Start (Local Docker)

1. **Clone the repository:**

   ```bash
   git clone https://github.com/llathrop/Dive_Service_Management.git
   cd Dive_Service_Management
   ```

2. **Create your environment file:**

   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` with your settings.** At minimum, change these values:

   ```bash
   # Generate random values for these (e.g., with: python -c "import secrets; print(secrets.token_hex(32))")
   DSM_SECRET_KEY=<random-64-char-hex-string>
   DSM_SECURITY_PASSWORD_SALT=<different-random-64-char-hex-string>

   # Set database passwords
   MARIADB_ROOT_PASSWORD=<strong-root-password>
   MARIADB_PASSWORD=<strong-app-password>

   # Make sure the app password matches the connection string
   DSM_DATABASE_URL=mysql+mysqldb://dsm:<strong-app-password>@db:3306/dsm
   ```

4. **Start all services:**

   ```bash
   docker compose up -d
   ```

   This builds the application image and starts all five containers (web, db, redis, worker, beat).

5. **Wait for startup to complete** (about 30-60 seconds on first run):

   ```bash
   docker compose logs -f web
   ```

   Look for `Running database migrations...`, `Seeding database defaults...`, and the Gunicorn startup message.

6. **Access the application:**

   Open `http://localhost:8080` in your browser.

7. **Create your admin account** (production mode):

   ```bash
   docker compose exec web flask create-admin
   ```

   Follow the prompts to set username, email, and password.

   In development mode (`DSM_ENV=development`), demo users are created automatically during seeding. See the [User Guide](user_guide.md) for credentials.

### Stopping and Restarting

```bash
docker compose down      # Stop all containers (data is preserved in volumes)
docker compose up -d     # Start again
docker compose restart   # Restart without rebuilding
```

---

## Raspberry Pi Setup

### OS Setup

1. Install **Raspberry Pi OS (64-bit)** using the Raspberry Pi Imager. The 64-bit Lite version is recommended for a headless server.
2. Enable SSH during OS setup.
3. Boot the Pi and connect via SSH.

### Install Docker on ARM64

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker using the convenience script
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to the docker group (avoids needing sudo)
sudo usermod -aG docker $USER

# Log out and back in, then verify
docker --version
docker compose version
```

### Deploy DSM on Pi

Follow the [Quick Start](#quick-start-local-docker) steps above. The Docker image supports ARM64 natively.

### Pi-Specific Notes

**MariaDB tuning**: The default configuration in `docker/db/conf/custom.cnf` is already optimized for memory-constrained environments:

- `innodb_buffer_pool_size = 128M` (suitable for 4 GB system RAM)
- `max_connections = 30` (limits memory overhead)
- `performance_schema = OFF` (saves ~100 MB RAM)
- `thread_cache_size = 4` (minimizes thread creation overhead)

For a Pi with 8 GB RAM, you can increase `innodb_buffer_pool_size` to `256M` and `max_connections` to `50`.

**Gunicorn workers**: The default configuration uses 2 workers with 4 threads each, which is appropriate for a Pi. Do not increase beyond 3 workers on a 4 GB Pi.

**Storage**: Use an SSD connected via USB 3.0 instead of the SD card for the Docker volumes. SD cards wear out quickly under database write loads. Mount the SSD and configure Docker's data root or use bind mounts pointing to the SSD.

**Expected performance**: Page loads typically complete in 1-3 seconds on a Pi 4 with SSD storage. Report generation for large datasets may take 5-10 seconds.

---

## Remote Database Setup

To use an external MariaDB instance instead of the Docker-managed database:

### 1. Configure the Connection String

Edit `.env` to point to your external database:

```bash
DSM_DATABASE_URL=mysql+mysqldb://dsm_user:password@db-host.example.com:3306/dive_service_mgmt?charset=utf8mb4
```

### 2. Remove the Database Container

Create a `docker-compose.override.yml` to exclude the `db` service and remove the dependency:

```yaml
services:
  db:
    profiles: ["disabled"]
  web:
    depends_on:
      redis:
        condition: service_healthy
  worker:
    depends_on:
      redis:
        condition: service_healthy
```

### 3. Apply MariaDB Configuration

On the external database server, apply the settings from `docker/db/conf/custom.cnf`:

- Set `character-set-server = utf8mb4` and `collation-server = utf8mb4_unicode_ci`
- Set `innodb_ft_min_token_size = 2` for FULLTEXT search support
- Create the database and user:

```sql
CREATE DATABASE dive_service_mgmt CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'dsm_user'@'%' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON dive_service_mgmt.* TO 'dsm_user'@'%';
FLUSH PRIVILEGES;
```

### 4. Start Without the Database Container

```bash
docker compose up -d
```

The web container will run migrations against the external database on startup.

---

## Cloud Deployment Overview

The general approach for cloud deployment:

1. Build and push the Docker image to a container registry
2. Provision a managed database (MariaDB 10.11+ or MySQL 8.0+) and Redis instance
3. Deploy the web container with environment variables pointing to managed services
4. Optionally deploy worker and beat containers for background task processing

### AWS (ECS/Fargate + RDS + ElastiCache)

1. **Container Registry**: Push the `dsm-web` image to Amazon ECR.
2. **Database**: Create an RDS MariaDB instance. Use the `db.t3.micro` or `db.t3.small` tier.
3. **Cache/Broker**: Create an ElastiCache Redis cluster (single-node `cache.t3.micro` is sufficient).
4. **Compute**: Create an ECS cluster with a Fargate service running the web container. Set environment variables for `DSM_DATABASE_URL`, `DSM_REDIS_URL`, `DSM_CELERY_BROKER_URL`, `DSM_SECRET_KEY`, etc.
5. **Load Balancer**: Place an ALB in front of the ECS service with HTTPS termination.
6. **Worker/Beat**: Create separate ECS task definitions for the worker and beat containers, overriding the default command.

### GCP (Cloud Run + Cloud SQL + Memorystore)

1. **Container Registry**: Push to Google Artifact Registry.
2. **Database**: Create a Cloud SQL for MySQL 8.0 instance (GCP Cloud SQL does not offer MariaDB; MySQL 8.0 is compatible).
3. **Cache/Broker**: Create a Memorystore for Redis instance.
4. **Compute**: Deploy to Cloud Run with the container image. Set environment variables.
5. **Worker/Beat**: Deploy as separate Cloud Run services or use Compute Engine instances.

### Azure (Container Apps + Azure DB + Azure Cache)

1. **Container Registry**: Push to Azure Container Registry.
2. **Database**: Create an Azure Database for MySQL Flexible Server instance (Azure Database for MariaDB has been retired).
3. **Cache/Broker**: Create an Azure Cache for Redis instance.
4. **Compute**: Deploy to Azure Container Apps with environment variables.
5. **Worker/Beat**: Deploy as separate container app replicas with command overrides.

### Important Cloud Considerations

- Always set `DSM_ENV=production` to enable production mode security checks.
- Use managed secrets (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault) for `DSM_SECRET_KEY` and database passwords.
- The web container runs migrations automatically on startup -- ensure only one instance runs migrations at a time during deployments (use deployment ordering or a migration init container).
- For high availability, run 2+ web container replicas behind a load balancer.

---

## First-Time Setup

When the application starts for the first time, the following happens automatically:

1. **Database migration**: `flask db upgrade` creates all tables from the migration chain (10 migrations total).
2. **Seed data**: `flask seed-db` creates:
   - 3 roles: admin, technician, viewer
   - 6 price list categories: Drysuit Repairs, Seal Replacement, Zipper Service, Valve Service, Testing & Inspection, General Service
   - 38 system config entries across 8 categories (company, invoice, tax, service, notification, email, display, security)
   - 3 demo users (development/testing mode only)
3. **Admin account**: In production mode, no demo users are created. Run `flask create-admin` to create your first admin user:

   ```bash
   docker compose exec web flask create-admin
   ```

All seed operations are idempotent -- re-running them will not create duplicates.

---

## Upgrading

To upgrade to a new version of DSM:

1. **Pull the latest code:**

   ```bash
   git pull origin master
   ```

2. **Rebuild and restart containers:**

   ```bash
   docker compose up -d --build
   ```

   The web container automatically runs `flask db upgrade` on startup, applying any new migrations. Before running migrations, DSM creates a compressed SQL backup if pending migrations are detected (see [Automatic Pre-Migration Backup](#automatic-pre-migration-backup) below). The seed command runs next, adding any new default data.

3. **Verify the upgrade:**

   ```bash
   docker compose logs web | tail -20
   ```

   Confirm that migrations and seeding completed successfully.

### Rollback

If an upgrade causes issues:

1. Stop the containers: `docker compose down`
2. Check out the previous version: `git checkout <previous-tag-or-commit>`
3. Rebuild and restart: `docker compose up -d --build`

Database rollback requires restoring from a backup if new migrations have already been applied.

### Automatic Pre-Migration Backup

When the web container starts and detects pending Alembic migrations, it automatically creates a compressed SQL dump of the database before applying them. This provides a recovery point in case a migration fails or causes data issues.

**How it works:**

- The entrypoint script compares `flask db current` with `flask db heads` to detect pending migrations.
- If migrations are pending, `mariadb-dump` creates a gzipped backup at `/app/backups/dsm_pre_migrate_<timestamp>.sql.gz`.
- The backup uses `--single-transaction` for a consistent snapshot without locking tables.
- Backup files are stored in the `./backups/` directory on the host (mounted into the container).

**Disabling auto-backup:**

Set the environment variable in your `.env` file:

```bash
DSM_AUTO_BACKUP_ON_UPGRADE=false
```

**Backup behavior:**

- Backup is best-effort: if it fails, a warning is logged but the migration proceeds normally.
- No backup is created when there are no pending migrations (to avoid unnecessary disk usage).
- Backups are compressed with gzip to minimize storage requirements.

**Restoring from a pre-migration backup:**

```bash
# Stop the application
docker compose down

# Start only the database
docker compose up -d db

# Wait for it to be healthy
docker compose exec db healthcheck.sh --connect --innodb_initialized

# Restore the backup (decompress and pipe to mysql)
gunzip -c backups/dsm_pre_migrate_20260318_120000.sql.gz | docker compose exec -T db mysql -u root -p"$MARIADB_ROOT_PASSWORD" dsm

# Start all services
docker compose up -d
```

---

## Backup and Restore

### Using the Admin Interface

1. Log in as an admin user.
2. Navigate to **Admin** > **Data Management**.
3. Click **Download SQL Backup** to download a full database dump.

### Command-Line Backup

Run `mysqldump` inside the database container:

```bash
docker compose exec db mysqldump -u root -p"$MARIADB_ROOT_PASSWORD" dsm > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Automated Backups

Set up a cron job to run the backup command on a schedule:

```bash
# Daily backup at 2:00 AM
0 2 * * * cd /path/to/Dive_Service_Management && docker compose exec -T db mysqldump -u root -p"$(grep MARIADB_ROOT_PASSWORD .env | cut -d= -f2)" dsm > backups/backup_$(date +\%Y\%m\%d).sql
```

### Restoring from Backup

```bash
# Stop the application
docker compose down

# Start only the database
docker compose up -d db

# Wait for it to be healthy
docker compose exec db healthcheck.sh --connect --innodb_initialized

# Restore the backup
docker compose exec -T db mysql -u root -p"$MARIADB_ROOT_PASSWORD" dsm < backup_file.sql

# Start all services
docker compose up -d
```

### Volume Backup

To back up the entire database volume (preserves binary data exactly):

```bash
docker compose down
docker run --rm -v dive_service_management_dsm-db-data:/data -v $(pwd)/backups:/backup ubuntu tar czf /backup/db-volume-$(date +%Y%m%d).tar.gz /data
docker compose up -d
```

---

## Running Tests (Docker)

DSM provides two Docker-based approaches for running tests. Both use SQLite in-memory, so no MariaDB or Redis is required.

### Persistent Test Container (Recommended for Development)

The persistent test runner stays running and mounts your source code as volumes. Code changes are reflected instantly with no rebuild needed.

Resource caps for the Docker test container live in `docker/test-resources.env`.
By default, `./scripts/configure_test_resources.sh` writes half the detected host CPUs and one quarter of host RAM, capped at `6144m`.
Refresh them from the current machine before long test sessions:

```bash
./scripts/configure_test_resources.sh

# Build and start the persistent test container
docker compose --env-file docker/test-resources.env -f docker-compose.test-dev.yml build
docker compose --env-file docker/test-resources.env -f docker-compose.test-dev.yml up -d

# Run the full test suite
docker compose --env-file docker/test-resources.env -f docker-compose.test-dev.yml exec test pytest

# Run specific tests
docker compose --env-file docker/test-resources.env -f docker-compose.test-dev.yml exec test pytest tests/unit/ -v
docker compose --env-file docker/test-resources.env -f docker-compose.test-dev.yml exec test pytest -k "test_customer"
docker compose --env-file docker/test-resources.env -f docker-compose.test-dev.yml exec test pytest --cov=app

# Stop the container when done
docker compose --env-file docker/test-resources.env -f docker-compose.test-dev.yml down
```

Rebuild the container only when Python dependencies change:

```bash
docker compose --env-file docker/test-resources.env -f docker-compose.test-dev.yml build test
docker compose --env-file docker/test-resources.env -f docker-compose.test-dev.yml up -d
```

### Run-Once Test Container

The run-once approach builds a fresh container each time. This is useful for CI or one-off test runs.

```bash
docker compose --env-file docker/test-resources.env -f docker-compose.test.yml build
docker compose --env-file docker/test-resources.env -f docker-compose.test.yml run --rm test
docker compose --env-file docker/test-resources.env -f docker-compose.test.yml run --rm test pytest tests/ -v --cov=app
```

### Local Testing (Without Docker)

If you have a local Python virtual environment set up:

```bash
.venv/bin/python3 -m pytest
```

This requires all dependencies from `requirements.txt` and `requirements-test.txt` (or `requirements-dev.txt`) to be installed in the virtual environment.

---

## Troubleshooting

### Port 8080 Already in Use

**Symptom**: `Bind for 0.0.0.0:8080 failed: port is already allocated`

**Solution**: Change the port in `.env`:

```bash
DSM_PORT=8090
```

Then restart: `docker compose up -d`

### Database Connection Refused

**Symptom**: Web container logs show `Can't connect to MySQL server on 'db'`

**Possible causes and solutions**:

- **Database container not started**: Check `docker compose ps` -- if `dsm-db` is not running, check its logs with `docker compose logs db`.
- **Database still initializing**: On first run, MariaDB can take 30-60 seconds to initialize. Wait and check the health status: `docker compose ps`.
- **Wrong credentials**: Verify that `MARIADB_PASSWORD` in `.env` matches the password in `DSM_DATABASE_URL`.
- **Volume corruption**: If the database repeatedly fails to start, try removing the volume and starting fresh: `docker compose down -v && docker compose up -d` (this deletes all data).

### Migration Failures

**Symptom**: Web container logs show `FATAL: Database migration failed in production`

**Possible causes and solutions**:

- **Schema conflict**: If the database was manually modified, the migration may fail. Check the specific error in `docker compose logs web`.
- **Missing migration**: Ensure all migration files are present in `migrations/versions/`.
- **Reset approach**: For development, you can reset by removing the database volume: `docker compose down -v && docker compose up -d`.

### Permission Errors on Volumes

**Symptom**: `Permission denied` errors when writing to `/app/uploads`, `/app/logs`, or `/app/instance`

**Solution**: The application runs as the `dsm` user (non-root) inside the container. Ensure the host directories have appropriate permissions:

```bash
# Create directories if they don't exist
mkdir -p uploads logs instance

# Set ownership (use the UID/GID of the dsm user in the container)
sudo chown -R 999:999 uploads logs instance
```

Alternatively, set broader permissions:

```bash
chmod -R 777 uploads logs instance
```

### Container Keeps Restarting

**Symptom**: `docker compose ps` shows a container in a restart loop.

**Solution**: Check the container logs for the specific error:

```bash
docker compose logs --tail=50 web
docker compose logs --tail=50 worker
```

Common causes:

- **Production secret key check**: If `DSM_ENV=production` and you have not changed `DSM_SECRET_KEY` or `DSM_SECURITY_PASSWORD_SALT` from their defaults, the app will refuse to start with `SECURITY ERROR`.
- **Redis not available**: Worker and beat containers need Redis. Ensure the Redis container is healthy.

### Slow Performance

- **On Raspberry Pi**: Ensure you are using an SSD, not an SD card for Docker volumes. Check memory usage with `free -h` -- if swap is heavily used, reduce `innodb_buffer_pool_size` in `docker/db/conf/custom.cnf`.
- **Large datasets**: For tables with many thousands of rows, ensure database indexes are in place (they are created by migrations).
- **Container resource limits**: If running alongside other services, consider setting memory limits in `docker-compose.yml`.

### Health Check Failing

**Symptom**: `docker compose ps` shows a container as `unhealthy`.

Check the specific health check:

```bash
# Web health
curl http://localhost:8080/health

# Database health
docker compose exec db healthcheck.sh --connect --innodb_initialized

# Redis health
docker compose exec redis redis-cli ping

# Worker health
docker compose exec worker celery -A app.celery_app inspect ping
```

The `/health` endpoint returns JSON with the overall status and individual check results:

```json
{"status": "ok", "checks": {"database": "ok"}}
```

A `degraded` status with `"database": "unreachable"` indicates the web container cannot reach the database.
