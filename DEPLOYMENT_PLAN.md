# DSM Deployment Plan
## VM → Full Cloud Migration

**Created:** 2026-05-23  
**Based on:** Multi-agent security, architecture, and QA review of commit 78c72a8  
**Strategy:** Stage 1 — hardened VM (EC2 + Docker Compose). Stage 2 — managed AWS services (ECS + RDS + ElastiCache).

---

## Stage 1 — VM Deployment

### Architecture

```
Internet
   │ 443 (HTTPS) / 80 (→ redirect)
   ▼
[EC2 Instance — t3.medium or t3.large]
   │
   ├── Nginx  (TLS termination via Certbot/Let's Encrypt)
   │     │  proxy_pass → 127.0.0.1:8080
   │     └── Rate limiting on /auth/login, security headers
   │
   ├── Docker Compose  (existing 5-service stack, unchanged)
   │     ├── web     Flask/Gunicorn on :8080  (bind: 127.0.0.1 only)
   │     ├── db      MariaDB 11 LTS
   │     ├── redis   Redis 7
   │     ├── worker  Celery worker
   │     └── beat    Celery Beat scheduler
   │
   └── EBS Volume  (/mnt/dsm-data)
         ├── db/           → /var/lib/mysql  (MariaDB data)
         ├── uploads/      → /app/uploads    (attachments, logos)
         ├── logs/         → /app/logs       (application logs)
         └── backups/      → /app/backups    (pre-migration dumps)
```

**Security groups:** inbound 443 + 80 from `0.0.0.0/0`. SSH (22) from admin IPs only. All other ports closed. Docker does **not** expose port 8080 to the internet — `DSM_BIND_ADDRESS=127.0.0.1` locks it to localhost.

---

### Code Changes Required (8 items, all small)

These implement the security fixes needed before internet exposure. They are small, localized changes. Run the full test suite after each batch.

#### Must-Have Before Go-Live

**S1-1 — ProxyFix middleware** (`app/__init__.py`)  
Nginx forwards `X-Forwarded-For`. Without ProxyFix, Flask-Limiter keys all rate limits off `127.0.0.1` (the Nginx proxy), making it useless. `DSM_PROXY_COUNT=1` is the new env var that activates it.

```python
# In create_app(), after app = Flask(__name__):
from werkzeug.middleware.proxy_fix import ProxyFix
proxy_count = int(os.environ.get("DSM_PROXY_COUNT", 0))
if proxy_count > 0:
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=proxy_count, x_proto=proxy_count,
        x_host=proxy_count, x_prefix=proxy_count
    )
```

Also add to `.env.example`:
```
# Number of reverse proxy hops in front of the app (1 = Nginx or ALB)
DSM_PROXY_COUNT=0
```

---

**S1-2 — Remember-me cookie security flags** (`app/config.py`)  
`ProductionConfig` already sets `SESSION_COOKIE_SECURE=True` but Flask-Security-Too's "remember me" token cookie (`remember_token`) is missing the same flags. `REMEMBER_COOKIE_HTTPONLY` defaults to `False` in Flask.

```python
# Add to ProductionConfig:
from datetime import timedelta
REMEMBER_COOKIE_SECURE = True
REMEMBER_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_SAMESITE = "Lax"
REMEMBER_COOKIE_DURATION = timedelta(days=30)
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)  # fallback default
```

---

**S1-3 — Session lifetime enforcement from DB config** (`app/__init__.py`)  
`security.session_lifetime_hours` is stored in `system_config` with an admin UI to change it, but the value is never applied to Flask. Sessions currently have no server-enforced expiry.

```python
# Add to create_app(), in the before_request registration block:
@app.before_request
def enforce_session_lifetime():
    from app.services.config_service import get_config
    try:
        hours = int(get_config("security.session_lifetime_hours", 24))
        app.permanent_session_lifetime = timedelta(hours=hours)
    except Exception:
        pass  # Never break the request over config read
```

---

**S1-4 — DB password exposure in process list** (`app/services/data_management_service.py`)  
The admin backup function passes `--password=<plaintext>` as a CLI argument to `mariadb-dump`. This is visible in `ps aux` for the subprocess lifetime. The `docker-entrypoint.sh` already uses the correct pattern (`MYSQL_PWD` env var) — apply the same fix here.

```python
# Replace: f"--password={parsed.password or ''}" in the cmd list
# With: pass password via subprocess env instead

import copy, os
env = copy.copy(os.environ)
env["MYSQL_PWD"] = parsed.password or ""
# Remove --password from cmd list entirely
result = subprocess.run(cmd, capture_output=True, text=True, env=env, ...)

# Also sanitize error messages — don't surface raw stderr to admin UI:
# Replace: raise RuntimeError(f"Backup failed: {e.stderr}")
# With:
raise RuntimeError("Backup failed. Check server logs for details.")
```

---

**S1-5 — SMTP password in audit export redaction set** (`app/blueprints/admin/audit.py`)  
`SENSITIVE_FIELDS` redacts password hashes from audit CSV exports but `email.smtp_password` is not in the set, so it can appear in plaintext in downloaded audit logs.

```python
# Find the SENSITIVE_FIELDS set and add the smtp_password key:
SENSITIVE_FIELDS = {
    "password", "password_hash", "fs_uniquifier", "tf_totp_secret",
    "email.smtp_password",   # ← add this
}
```

---

**S1-6 — Host header validation** (`app/__init__.py`)  
`DSM_ALLOWED_HOSTS` is documented in `.env.example` and `docs/cloud_deployment.md` but never read by the application. Without this, password reset emails can be poisoned with an attacker's domain via a crafted `Host` header.

```python
# In create_app(), in the before_request registration block:
allowed_hosts_str = os.environ.get("DSM_ALLOWED_HOSTS", "")
allowed_hosts = [h.strip() for h in allowed_hosts_str.split(",") if h.strip() and h.strip() != "*"]

@app.before_request
def check_host_header():
    if allowed_hosts and request.host.split(":")[0] not in allowed_hosts:
        abort(400)
```

Set `DSM_ALLOWED_HOSTS=yourdomain.com` in the VM `.env`.

---

**S1-7 — Portal user password hashing upgrade** (`app/models/portal_user.py`)  
Staff users are hashed with argon2 (via Flask-Security-Too). Portal users use Werkzeug's `pbkdf2:sha256`. `argon2-cffi` is already in `requirements.txt` — apply the same algorithm to portal users.

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_ph = PasswordHasher()

def set_password(self, raw_password: str) -> None:
    self.password_hash = _ph.hash(raw_password)

def check_password(self, raw_password: str) -> bool:
    try:
        return _ph.verify(self.password_hash, raw_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
```

Existing pbkdf2 hashes are not retroactively upgraded — portal users will need to reset passwords or log in once (at which point the hash can be re-stored as argon2 on successful verify).

---

**S1-8 — DSM_PROXY_COUNT added to .env.example**  
Add the new variable to `.env.example` (under the Network section) so it is documented alongside `DSM_BIND_ADDRESS` and `DSM_ALLOWED_HOSTS`:

```bash
# Number of trusted reverse proxy hops in front of the app.
# Set to 1 when running behind Nginx or an AWS ALB.
# Enables ProxyFix so Flask sees the real client IP for rate limiting.
DSM_PROXY_COUNT=0
```

---

### VM Setup Steps

#### Phase A — Provision the VM (Day 1)

```bash
# =========================================================================
# Option 1: Provisioning on AWS (EC2 + EBS)
# =========================================================================
# 1. Launch EC2 instance:
#    Type:   t3.medium (2 vCPU, 4 GB) — or t3.large if PDF generation is heavy
#    OS:     Ubuntu 24.04 LTS (64-bit)
#    Key:    SSH key pair only — disable password auth in sshd_config
#    Region: choose closest to customers

# 2. Security group rules (create before launch):
#    Inbound:  TCP 443   from 0.0.0.0/0, ::/0
#    Inbound:  TCP 80    from 0.0.0.0/0, ::/0   (Nginx redirects → 443)
#    Inbound:  TCP 22    from YOUR_ADMIN_IP/32 only
#    Outbound: All traffic (for apt, Certbot renewal, SMTP, etc.)

# 3. Attach Elastic IP → update your domain's DNS A record to point to it.
#    Wait for DNS propagation before requesting a TLS certificate.

# 4. Create and attach EBS volume (separate from root):
#    Size:  50 GB gp3 (can be expanded online later)
#    Mount: /mnt/dsm-data

# On the VM, format and mount the EBS volume:
# sudo mkfs.ext4 /dev/xvdf          # adjust device name as shown in EC2 console / lsblk
# sudo mkdir -p /mnt/dsm-data
# sudo mount /dev/xvdf /mnt/dsm-data
# # Persist across reboots:
# echo '/dev/xvdf /mnt/dsm-data ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab

# =========================================================================
# Option 2: Provisioning on GCP (Compute Engine + Persistent Disk)
# =========================================================================
# 1. Launch Compute Engine Instance:
#    Machine Type: e2-medium (2 vCPU, 4 GB)
#    OS:           Ubuntu 24.04 LTS (64-bit)
#    Region:       choose closest to customers

# 2. VPC Network Firewall Rules:
#    Create ingress rule: TCP 80, 443   from 0.0.0.0/0, ::/0
#    Create ingress rule: TCP 22        from YOUR_ADMIN_IP/32 only (or use GCP IAP / Identity-Aware Proxy)

# 3. Reserve Static External IP -> Assign to VM -> update DNS A record to it.
#    Wait for DNS propagation before requesting a TLS certificate.

# 4. Create and attach Google Persistent Disk (separate from boot disk):
#    Size:  50 GB pd-ssd or pd-standard
#    Mount: /mnt/dsm-data

# On the VM, format and mount the Persistent Disk:
# sudo mkfs.ext4 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb
# sudo mkdir -p /mnt/dsm-data
# sudo mount -o discard,defaults /dev/sdb /mnt/dsm-data
# # Persist across reboots using disk UUID:
# UUID=$(sudo blkid -s UUID -o value /dev/sdb)
# echo "UUID=$UUID /mnt/dsm-data ext4 discard,defaults,nofail 0 2" | sudo tee -a /etc/fstab

# =========================================================================
# Common Directory Setup (runs on both AWS and GCP)
# =========================================================================
# Create subdirectories DSM expects:
sudo mkdir -p /mnt/dsm-data/{db,uploads/logos,uploads/imports,uploads/exports,uploads/attachments,logs,backups}
sudo chown -R 1000:1000 /mnt/dsm-data   # UID 1000 = default ubuntu user; dsm container runs as UID 999
```

#### Phase B — Install Software (Day 1)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker   # apply group without logout

# Verify
docker --version
docker compose version

# Install Nginx and Certbot
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx fail2ban

# Enable fail2ban for SSH protection (blocks repeated failed SSH attempts)
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

#### Phase C — Apply Code Changes and Deploy (Day 1–2)

```bash
# Clone the repository onto the VM:
git clone https://github.com/llathrop/Dive_Service_Management.git /srv/dsm
cd /srv/dsm

# Apply the 8 code changes (S1-1 through S1-8) described above.
# Run full test suite locally first to confirm no regressions:
./scripts/test-compose.sh -f docker-compose.test.yml run --rm test

# Create production .env — DO NOT copy from dev, generate fresh secrets:
cp .env.example .env

# Edit .env with production values:
#   DSM_SECRET_KEY       = $(python3 scripts/generate_secret_key.py)
#   DSM_SECURITY_PASSWORD_SALT = $(python3 scripts/generate_secret_key.py)
#   DSM_ENV              = production
#   DSM_DEBUG            = false
#   DSM_BIND_ADDRESS     = 127.0.0.1   ← CRITICAL: locks Docker to localhost only
#   DSM_PORT             = 8080
#   DSM_PROXY_COUNT      = 1           ← new: tells ProxyFix to trust Nginx's X-Forwarded-For
#   DSM_ALLOWED_HOSTS    = yourdomain.com
#   MARIADB_ROOT_PASSWORD = <random>
#   MARIADB_PASSWORD      = <random>
#   MARIADB_DATABASE      = dsm
#   MARIADB_USER          = dsm
#   DSM_DATABASE_URL      = mysql+mysqldb://dsm:<MARIADB_PASSWORD>@db:3306/dsm
#   REDIS_PASSWORD        = <random>
#   DSM_REDIS_URL         = redis://:REDIS_PASSWORD@redis:6379/0
#   DSM_CELERY_BROKER_URL    = redis://:REDIS_PASSWORD@redis:6379/1
#   DSM_CELERY_RESULT_BACKEND = redis://:REDIS_PASSWORD@redis:6379/2
#   DSM_AUTO_BACKUP_ON_UPGRADE = true
#   DSM_LOG_LEVEL         = INFO

# Update docker-compose.yml volume paths to use EBS mount:
# Change all ./uploads, ./logs, ./backups, ./instance bind mounts to:
#   /mnt/dsm-data/uploads:/app/uploads
#   /mnt/dsm-data/logs:/app/logs
#   /mnt/dsm-data/backups:/app/backups
# For the db service:
#   /mnt/dsm-data/db:/var/lib/mysql
# (Keep named volume dsm-redis-data for Redis — it's small and can stay in Docker's storage)

# Build and start:
docker compose build
docker compose up -d

# Verify health:
curl http://127.0.0.1:8080/health/ready
# Expected: {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}

# Create admin account:
docker compose exec web flask create-admin
```

#### Phase D — Configure Nginx and TLS (Day 2)

```nginx
# /etc/nginx/sites-available/dsm
# (symlink to sites-enabled after creation)

# Rate limiting zone — shared across workers
limit_req_zone $binary_remote_addr zone=dsm_login:10m rate=10r/m;

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    # TLS — managed by Certbot (do not edit these lines manually)
    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers (complement what Flask already sends)
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Match Flask's MAX_CONTENT_LENGTH (default 16 MB) with some headroom
    client_max_body_size 20M;

    # Rate-limit the login endpoint at the edge before Flask-Limiter
    location /auth/login {
        limit_req zone=dsm_login burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
        proxy_read_timeout 120s;   # match Gunicorn --timeout 120 for PDF generation
        proxy_send_timeout 120s;
    }
}
```

```bash
# Enable site and test config:
sudo ln -s /etc/nginx/sites-available/dsm /etc/nginx/sites-enabled/
sudo nginx -t

# Obtain TLS certificate (DNS must resolve first):
sudo certbot --nginx -d yourdomain.com

# Confirm auto-renewal is scheduled:
sudo certbot renew --dry-run
sudo systemctl status certbot.timer

# Reload Nginx:
sudo systemctl reload nginx
```

#### Phase E — Validation (Day 2)

```bash
# 1. End-to-end HTTPS health check:
curl -f https://yourdomain.com/health/ready

# 2. Confirm HTTP redirects to HTTPS:
curl -I http://yourdomain.com
# Expected: HTTP/1.1 301 Moved Permanently → https://yourdomain.com

# 3. Confirm port 8080 is NOT accessible from the internet:
# (run from a machine other than the VM)
curl --connect-timeout 5 http://<EC2_PUBLIC_IP>:8080
# Expected: connection refused or timeout

# 4. Verify login works and session persists correctly.

# 5. Test file upload (attach a photo to a service item) — confirm
#    file appears in /mnt/dsm-data/uploads/attachments/ on the VM.

# 6. Test backup via Admin > Data Management > Download SQL Backup.
#    Confirm no database password appears in logs:
docker compose logs web | grep -i password   # should return nothing

# 7. Set up automated nightly DB backup cron:
(crontab -l 2>/dev/null; echo "0 2 * * * cd /srv/dsm && ./scripts/backup.sh nightly_\$(date +\%Y\%m\%d) >> /mnt/dsm-data/logs/backup.log 2>&1") | crontab -
```

---

### Upgrading the VM Deployment

The existing `scripts/setup.sh upgrade` command handles the standard upgrade path:

```bash
cd /srv/dsm
./scripts/setup.sh upgrade
```

This: pulls latest code (`git pull`) → rebuilds images → restarts containers → runs `flask db upgrade`. The `DSM_AUTO_BACKUP_ON_UPGRADE=true` setting triggers an automatic pre-migration SQL dump before any schema changes are applied (see `docs/installation.md` — Automatic Pre-Migration Backup).

For code-only changes (no dependency or migration changes):
```bash
docker compose build web worker beat
docker compose up -d --no-deps web worker beat
```

---

## Stage 2 — Full Cloud Migration (AWS ECS)

### When to Start Stage 2

Start Stage 2 planning when any of these conditions are met:
- More than one shop location needs simultaneous access
- VM is consistently at >70% CPU or >80% memory under normal load  
- SLA requirement for automated failover without manual intervention
- File storage exceeds 40 GB on EBS (S3 becomes cost-effective)

### What Changes Stage 1 → Stage 2

```
Stage 1 (VM)                 →    Stage 2 (AWS Managed)
────────────────────────────────────────────────────────────
EC2 + Nginx                  →    ALB + ACM certificate
Docker Compose on VM         →    ECS Fargate task definitions
MariaDB in Docker container  →    RDS for MariaDB 11 (db.t4g.medium)
Redis in Docker container    →    ElastiCache Redis 7 (cache.t4g.micro + replica)
EBS bind mounts (uploads)    →    EFS (Phase 2a) → S3 presigned URLs (Phase 2b)
.env file on disk            →    AWS Secrets Manager + SSM Parameter Store
Nginx rate limiting          →    AWS WAF v2 on ALB (Core Managed Rules)
Manual git pull upgrade      →    ECR image push → ECS rolling deploy
VM-level cron backups        →    RDS automated snapshots
```

### Additional Code Changes for Stage 2

Only 4 additions on top of Stage 1 (all small):

**S2-1 — Gate `flask db upgrade` behind env var** (`docker-entrypoint.sh`)  
In ECS, multiple tasks start simultaneously during rolling deploys — both would attempt migrations at the same time. Gate the migration step so only a dedicated one-off task runs it (triggered by the deploy pipeline, not every container start).

```bash
# In docker-entrypoint.sh, replace the unconditional flask db upgrade block with:
if [[ "${DSM_RUN_MIGRATIONS:-false}" == "true" && "$1" == "gunicorn" ]]; then
    echo "Running database migrations..."
    flask db upgrade || { echo "FATAL: Migration failed"; exit 1; }
    echo "Seeding database defaults..."
    flask seed-db || echo "WARNING: Seeding failed"
fi
```

Set `DSM_RUN_MIGRATIONS=false` in ECS service task definitions. A separate `dsm-migrate` ECS task definition runs with `DSM_RUN_MIGRATIONS=true` and is invoked by the deploy pipeline before updating the service.

---

**S2-2 — Celery beat Redis-backed scheduler** (`requirements.txt`, `app/celery_app.py`, ECS task command)  
In ECS Fargate, `/tmp/celerybeat-schedule` is ephemeral — lost on every task restart. A restart causes beat to re-fire all periodic tasks immediately (duplicate alerts, emails). `celery-redbeat` stores schedule state in Redis instead of a file.

```
# requirements.txt:
celery-redbeat==2.2.0

# app/celery_app.py — add to make_celery():
celery.conf.redbeat_redis_url = app.config.get("REDIS_URL")

# ECS beat task definition command (replaces current --schedule=/tmp/... flag):
celery -A app.celery_app beat --scheduler redbeat.RedBeatScheduler --loglevel=info
```

---

**S2-3 — Gunicorn worker tuning for Fargate** (ECS task definition CMD)  
Current: `--workers 2 --threads 4` (tuned for Raspberry Pi). Fargate recommended for 1 vCPU: `--workers 3 --threads 2` (formula: `(2 × vCPU) + 1`).

```
gunicorn --bind 0.0.0.0:8080 --workers 3 --threads 2 \
         --access-logfile - --error-logfile - --timeout 120 \
         --keep-alive 5 "app:create_app()"
```

---

**S2-4 — S3 file storage layer** (`app/utils/storage.py` + service updates)  
Replace EFS bind mount with S3 presigned URLs. This is the largest Stage 2 code change (estimated 1–2 sprint weeks). Defer until the ECS deployment is stable.

Files requiring changes:
- `app/utils/storage.py` — new module (S3 upload/download/delete/presign)
- `app/services/attachment_service.py` — swap local I/O for storage module
- `app/__init__.py` — `uploaded_file` route returns presigned URL redirect
- `app/utils/pdf.py` — download logo from S3 to memory buffer for fpdf2
- `app/blueprints/tools.py` — import wizard uses S3 temp storage

S3 bucket security requirements (must be configured before enabling):
- Block Public Access: all 4 settings ON
- Bucket policy: restrict to ECS task role ARN only (`s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`)
- Encryption: SSE-KMS
- VPC Gateway Endpoint for S3 (free — keeps traffic off the public internet)
- Versioning enabled
- Access logging to a separate audit bucket
- Presigned URL expiry: 15 minutes (`DSM_S3_PRESIGN_EXPIRY_SECONDS=900`)

---

### Stage 2 AWS Infrastructure

#### VPC Layout

```
VPC 10.0.0.0/16
  Public subnets:  10.0.0.0/24 (AZ-a), 10.0.1.0/24 (AZ-b)   → ALB, NAT Gateway
  Private subnets: 10.0.2.0/24 (AZ-a), 10.0.3.0/24 (AZ-b)   → ECS, RDS, ElastiCache

Security groups:
  sg-alb:    inbound 443/80 from 0.0.0.0/0  → outbound 8080 to sg-web
  sg-web:    inbound 8080 from sg-alb        → outbound 3306 to sg-db, 6379 to sg-redis, 443 to internet
  sg-db:     inbound 3306 from sg-web only
  sg-redis:  inbound 6379 from sg-web only
```

#### Service Sizing (starting point — scale up as needed)

| Service | AWS Service | Size | Est. Cost/month |
| --- | --- | --- | --- |
| Web (2 tasks) | ECS Fargate | 1 vCPU / 2 GB | ~$50 |
| Celery worker | ECS Fargate Spot | 0.5 vCPU / 1 GB | ~$6 |
| Celery beat | ECS Fargate Spot | 0.25 vCPU / 0.5 GB | ~$3 |
| Database | RDS MariaDB 11, `db.t4g.medium` | 2 vCPU / 4 GB | ~$55 (single-AZ) |
| Cache/Queue | ElastiCache Redis 7, `cache.t4g.micro` + 1 replica | 0.5 GB | ~$24 |
| Load balancer | ALB | — | ~$20 + usage |
| File storage | EFS (Phase 2a) → S3 (Phase 2b) | — | ~$5–15 |
| **Total** | | | **~$163–173/month** |

Multi-AZ RDS (for automatic failover) adds ~$55/month. Enable when uptime SLA requires it.

#### Secrets in AWS Secrets Manager

| Secret | Variable Injected into ECS |
| --- | --- |
| `dsm/prod/secret-key` | `DSM_SECRET_KEY` |
| `dsm/prod/password-salt` | `DSM_SECURITY_PASSWORD_SALT` |
| `dsm/prod/db-url` | `DSM_DATABASE_URL` |
| `dsm/prod/db-password` | `MARIADB_PASSWORD` |
| `dsm/prod/redis-url` | `DSM_REDIS_URL`, `DSM_CELERY_BROKER_URL`, `DSM_CELERY_RESULT_BACKEND` |
| `dsm/prod/smtp-password` | `DSM_MAIL_PASSWORD` |

All are injected via ECS Task Definition `secrets:` blocks — values are never stored in plaintext in the task definition. See `docs/cloud_deployment.md` for the full task definition JSON template.

#### ECS Task Definition Key Settings

```json
{
  "environment": [
    {"name": "DSM_ENV",                 "value": "production"},
    {"name": "DSM_PROXY_COUNT",         "value": "1"},
    {"name": "DSM_ALLOWED_HOSTS",       "value": "yourdomain.com"},
    {"name": "DSM_RUN_MIGRATIONS",      "value": "false"},
    {"name": "DSM_AUTO_BACKUP_ON_UPGRADE", "value": "false"},
    {"name": "DSM_BIND_ADDRESS",        "value": "0.0.0.0"},
    {"name": "DSM_LOG_LEVEL",           "value": "INFO"},
    {"name": "DSM_WORKERS",             "value": "3"},
    {"name": "DSM_THREADS",             "value": "2"}
  ],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/dsm/prod/web",
      "awslogs-region": "us-east-1",
      "awslogs-stream-prefix": "web"
    }
  }
}
```

Note: `DSM_BIND_ADDRESS` changes to `0.0.0.0` in ECS (no Nginx — the ALB is the public entry point, containers run in private subnets). `DSM_PROXY_COUNT=1` remains so ProxyFix trusts the ALB's `X-Forwarded-For`.

#### Health Check Configuration

ALB target group settings (matches what `docs/cloud_deployment.md` specifies):
- Path: `/health/ready`
- Protocol: HTTP, Port: 8080
- Healthy threshold: 2, Unhealthy threshold: 3
- Timeout: 5s, Interval: 30s
- Success codes: 200

---

### Stage 2 Migration Steps (Condensed)

```
Week 1 — Parallel Infrastructure (no downtime, VM stays live)
  □ Create VPC, subnets, security groups, IGW, NAT Gateway
  □ Create RDS MariaDB 11 (db.t4g.medium, single-AZ to start)
  □ Dump from VM MariaDB → restore to RDS (mysqldump + mysql)
  □ Create ElastiCache Redis (cache.t4g.micro + 1 replica, TLS + auth token)
  □ Create EFS filesystem + access point (for /app/uploads)
  □ Sync /mnt/dsm-data/uploads → EFS (rsync via EC2 in same VPC)
  □ Store secrets in AWS Secrets Manager
  □ Create ECR repository, build and push current image

Week 2 — ECS Cutover (brief maintenance window ~30 min)
  □ Apply Stage 2 code changes S2-1 through S2-3, run test suite
  □ Build + push updated image to ECR
  □ Create ECS cluster + task definitions (web, worker, beat, migrate)
  □ Mount EFS at /app/uploads in web and worker task defs
  □ Create ALB + target group (HTTP:8080) + ACM certificate (HTTPS:443)
  □ Run dsm-migrate one-off ECS task (DSM_RUN_MIGRATIONS=true) → wait exit 0
  □ Start ECS services (web ×2, worker ×1, beat ×1)
  □ Verify ALB: curl -f https://yourdomain.com/health/ready
  □ Update DNS: yourdomain.com A record → ALB DNS name (or CNAME for apex)
  □ Keep VM running for 24h as fallback → stop (not terminate) after stable
  □ Terminate VM after 1 week of stable cloud operation

Week 3 — Hardening
  □ Enable AWS WAF v2 on ALB — Core Managed Rule set + rate-based rule on /auth/login
  □ Configure CloudWatch alarms: 5xx error rate, CPU, memory, DB connections
  □ Set RDS automated backup retention to 7 days
  □ Confirm CloudWatch Logs receiving output from all ECS tasks
  □ Document rollback procedure (repoint DNS to stopped VM)

Week 4+ — S3 Migration (when ready, no deadline)
  □ Implement app/utils/storage.py (S3 adapter)
  □ Update attachment_service, uploaded_file route, pdf.py, import wizard
  □ Configure S3 bucket security (all controls listed in S2-4)
  □ Write S3 adapter tests with moto mocking
  □ Sync EFS → S3, cut over, remove EFS mounts from task defs
  □ Admin log viewer: replace file-read with CloudWatch Logs Insights queries
```

---

## Local ↔ Cloud Sync (Future)

For multi-location use (e.g., a second dive shop location running a local DSM instance that syncs to the cloud):

The recommended approach is the **outbox event pattern**: every service-layer write appends an event to an `OutboxEvent` table. A Celery periodic task reads unsynced events and POSTs them to the cloud's sync endpoint every 15 minutes when internet is available.

**Conflict resolution:**
- Financial records (invoices, payments): cloud wins — never allow local overwrite
- Service records (orders, items): last-write-wins by timestamp
- Attachments, notes, audit logs: append-only, no conflicts possible

**File sync:** `rclone sync /app/uploads s3://dsm-uploads-prod/shop-id/` on a schedule or triggered after upload.

This is a 4–6 sprint week effort and should be scoped as a separate project after Stage 2 is stable.

---

## Security Findings Backlog (Post-Stage-1)

These were identified in the security review but are not required for initial deployment. Address them in order during normal development sprints.

| # | Finding | Effort | When |
| --- | --- | --- | --- |
| B-1 | Account lockout not enforced despite config (Redis-backed failed-login counter via Flask-Security signal) | M | Post-Stage-1 |
| B-2 | CSP allows `unsafe-inline`/`unsafe-eval` — should use nonce-based script tags | L | Post-Stage-1 |
| B-3 | SMTP password stored in plaintext in `system_config` DB — encrypt with Fernet or migrate to SES IAM auth | M | Stage 2 (or migrate to SES) |
| B-4 | Health endpoints expose DB/Redis reachability unauthenticated — acceptable behind ALB SG but restrict detail in response | XS | Post-Stage-2 |
| B-5 | Celery task `send_notification_email_task` has zero tests (retry, max-retries, Kombu error path) | M | Post-Stage-1 |
| B-6 | Rate limiting 429 never exercised in test suite | S | Post-Stage-1 |
| B-7 | `mariadb-client` in runtime Docker image — only needed for backup; remove when using RDS snapshots | XS | Stage 2 |
| B-8 | Dockerfile base image not pinned by digest (floating `python:3.12-slim` tag) | XS | Post-Stage-1 |

---

*Last updated: 2026-05-23*  
*Reference docs: `docs/installation.md`, `docs/cloud_deployment.md`, `docs/architecture.md`, `docs/configuration.md`*
