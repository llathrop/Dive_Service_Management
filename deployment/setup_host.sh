#!/usr/bin/env bash
# =========================================================================
# setup_host.sh - DSM Target Host Provisioning & Deployment Script
# =========================================================================
# Configures the remote server: formats the EBS volume, installs Docker,
# clones the repository, provisions Nginx with TLS, and starts the stack.
#
# Requirements: setup_aws_infra.sh completed (env variables populated).
# =========================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0;m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

INFRA_ENV="deployment/.env.infra"
if [ ! -f "$INFRA_ENV" ]; then
    error "Infrastructure configuration file not found at $INFRA_ENV. Run setup_aws_infra.sh first."
fi

# Load variables
source "$INFRA_ENV"

# Validate loaded variables
[ -z "${PUBLIC_IP:-}" ] && error "PUBLIC_IP variable not set in $INFRA_ENV."
[ -z "${KEY_FILE:-}" ] && error "KEY_FILE variable not set in $INFRA_ENV."

DOMAIN_NAME=${1:-}
if [ -z "$DOMAIN_NAME" ]; then
    read -p "Enter the domain name for the application (e.g. dsm.example.com): " DOMAIN_NAME
fi
[ -z "$DOMAIN_NAME" ] && error "Domain name is required for reverse proxy and TLS."

log "--------------------------------------------------------"
log "Target Host:       $PUBLIC_IP"
log "Key File:          $KEY_FILE"
log "App Domain:        $DOMAIN_NAME"
log "--------------------------------------------------------"

# Wait for SSH port to open on the VM
log "Waiting for SSH to become available on $PUBLIC_IP..."
until nc -z -w 3 "$PUBLIC_IP" 22 >/dev/null 2>&1; do
    sleep 3
done
log "SSH port is open."

# Create remote configuration payload
REMOTE_SCRIPT="deployment/remote_setup_payload.sh"

cat <<'EOF' > "$REMOTE_SCRIPT"
#!/usr/bin/env bash
set -euo pipefail

# Remote execution logging
log() { echo -e "\033[0;32m[REMOTE-INFO]\033[0;m $1"; }
error() { echo -e "\033[0;31m[REMOTE-ERROR]\033[0;m $1" >&2; exit 1; }

log "System provisioning started..."

# 1. Mount EBS Volume (supporting standard dev-names and Nitro NVMe structures)
log "Detecting EBS block devices..."
# Search for a gp3 block device that is 50G in size and has no filesystem type
EBS_DEV=$(lsblk -o NAME,FSTYPE,SIZE -pn | grep -E "50G[[:space:]]*$" | awk '{print $1}' | head -n 1)

if [ -z "$EBS_DEV" ]; then
    error "Could not detect attached 50GB EBS volume."
fi
log "Detected EBS Volume block device: $EBS_DEV"

# Verify if it already has a filesystem (idempotency check)
FSTYPE=$(lsblk -no FSTYPE "$EBS_DEV" | tr -d ' ')
if [ -z "$FSTYPE" ]; then
    log "Formatting $EBS_DEV with ext4..."
    sudo mkfs.ext4 -F "$EBS_DEV"
else
    log "$EBS_DEV already formatted as $FSTYPE. Skipping formatting."
fi

# Ensure Mount directories exist and mount
sudo mkdir -p /mnt/dsm-data
if ! mountpoint -q /mnt/dsm-data; then
    log "Mounting $EBS_DEV to /mnt/dsm-data..."
    sudo mount "$EBS_DEV" /mnt/dsm-data
fi

# Add persistent mount to fstab via UUID
UUID=$(sudo blkid -s UUID -o value "$EBS_DEV")
if ! grep -q "$UUID" /etc/fstab; then
    log "Adding EBS volume entry to /etc/fstab..."
    echo "UUID=$UUID /mnt/dsm-data ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab
fi

# Create required directory layouts
log "Creating application directories on persistent volume..."
sudo mkdir -p /mnt/dsm-data/{db,uploads/logos,uploads/imports,uploads/exports,uploads/attachments,logs,backups}
sudo chown -R 1000:1000 /mnt/dsm-data

# 2. Package installation
log "Updating package cache and installing host services..."
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx fail2ban git python3-pip

# Enable and configure fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# 3. Docker installation
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker ubuntu
fi

# 4. Clone repository
log "Cloning Dive Service Management..."
sudo rm -rf /srv/dsm
sudo mkdir -p /srv/dsm
sudo chown -R ubuntu:ubuntu /srv/dsm
git clone https://github.com/llathrop/Dive_Service_Management.git /srv/dsm

cd /srv/dsm

# Generate secure secrets
log "Generating secure production configuration environment..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
SALT_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
ROOT_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
REDIS_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

# Write production .env
cat <<EOF > .env
DSM_SECRET_KEY=$SECRET_KEY
DSM_SECURITY_PASSWORD_SALT=$SALT_KEY
DSM_ENV=production
DSM_DEBUG=false
DSM_BIND_ADDRESS=127.0.0.1
DSM_PORT=8080
DSM_PROXY_COUNT=1
DSM_ALLOWED_HOSTS=$DOMAIN_NAME
MARIADB_ROOT_PASSWORD=$ROOT_PASS
MARIADB_PASSWORD=$DB_PASS
MARIADB_DATABASE=dsm
MARIADB_USER=dsm
DSM_DATABASE_URL=mysql+mysqldb://dsm:$DB_PASS@db:3306/dsm
REDIS_PASSWORD=$REDIS_PASS
DSM_REDIS_URL=redis://:$REDIS_PASS@redis:6379/0
DSM_CELERY_BROKER_URL=redis://:$REDIS_PASS@redis:6379/1
DSM_CELERY_RESULT_BACKEND=redis://:$REDIS_PASS@redis:6379/2
DSM_AUTO_BACKUP_ON_UPGRADE=true
DSM_LOG_LEVEL=INFO
EOF

# Update docker-compose.yml volume paths dynamically to use the EBS mount
log "Updating Docker Compose volume bindings to persistent EBS path..."
sed -i 's|\./uploads:/app/uploads|/mnt/dsm-data/uploads:/app/uploads|g' docker-compose.yml
sed -i 's|\./logs:/app/logs|/mnt/dsm-data/logs:/app/logs|g' docker-compose.yml
sed -i 's|\./backups:/app/backups|/mnt/dsm-data/backups:/app/backups|g' docker-compose.yml
sed -i 's|\./db_data:/var/lib/mysql|/mnt/dsm-data/db:/var/lib/mysql|g' docker-compose.yml

# 5. Start Docker Container Stack
log "Building and launching containers..."
sudo sg docker -c "docker compose build"
sudo sg docker -c "docker compose up -d"

log "Waiting for application startup health probes..."
sleep 15

# Trigger database migrations and seeding
log "Running database migrations..."
sudo sg docker -c "docker compose exec -T web flask db upgrade"
log "Seeding database..."
sudo sg docker -c "docker compose exec -T web flask seed-db"

# Create Nginx Reverse Proxy Config
log "Creating Nginx configuration..."
cat <<NGINXEOF | sudo tee /etc/nginx/sites-available/dsm
limit_req_zone \$binary_remote_addr zone=dsm_login:10m rate=10r/m;

server {
    listen 80;
    server_name $DOMAIN_NAME;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $DOMAIN_NAME;

    # Certbot placeholder - Nginx will reload after cert generation
    ssl_certificate     /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;

    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    client_max_body_size 20M;

    location /auth/login {
        limit_req zone=dsm_login burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Host \$host;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Host \$host;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
NGINXEOF

sudo ln -sf /etc/nginx/sites-available/dsm /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

# 6. Acquire Certbot TLS Certificate
log "Requesting Let's Encrypt TLS Certificate via Certbot..."
# We run certbot with --nginx to automate retrieval and certificate reload
sudo certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email -d "$DOMAIN_NAME"

log "Reloading Nginx with new TLS certificates..."
sudo systemctl restart nginx

log "Host setup and application deployment successfully completed!"
EOF

# Copy remote payload script to the target VM
log "Uploading remote setup payload to VM..."
scp -i "$KEY_FILE" -o StrictHostKeyChecking=no "$REMOTE_SCRIPT" ubuntu@"$PUBLIC_IP":/tmp/remote_setup.sh

# Run remote script
log "Executing remote server configuration script..."
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@"$PUBLIC_IP" "chmod +x /tmp/remote_setup.sh && /tmp/remote_setup.sh"

log "--------------------------------------------------------"
log "Host Setup successfully completed!"
log "Visit: https://$DOMAIN_NAME"
log "--------------------------------------------------------"

# Cleanup local temporary payload
rm -f "$REMOTE_SCRIPT"
