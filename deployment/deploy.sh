#!/usr/bin/env bash
# =========================================================================
# deploy.sh - DSM Master AWS Deployment Orchestrator Wizard
# =========================================================================
# Standard orchestrator to cleanly provision infrastructure on AWS and
# completely deploy the DSM application with reverse proxies and HTTPS.
# =========================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0;m'

log() { echo -e "${GREEN}[DSM-DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[DSM-DEPLOY-WARN]${NC} $1"; }
error() { echo -e "${RED}[DSM-DEPLOY-ERROR]${NC} $1" >&2; exit 1; }

# Create deployment directory if not exists
mkdir -p deployment

log "========================================================"
log "      DSM Automated AWS VM Deployment Wizard            "
log "========================================================"
log "This wizard will:"
log "  1. Provision an EC2 instance, EBS storage, and Elastic IP."
log "  2. Connect to the host to format volumes & install Docker."
log "  3. Configure security controls, Nginx, and Let's Encrypt TLS."
log "========================================================"

# Step 1: Handle AWS Credentials
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    warn "AWS CLI credentials are not configured or expired."
    log "Please provide your AWS credentials to proceed:"
    
    read -p "AWS Access Key ID: " AWS_ACCESS_KEY_ID
    read -sp "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
    echo ""
    read -p "Default Region [us-east-1]: " AWS_DEFAULT_REGION
    AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
        error "AWS credentials are required to continue."
    fi

    # Export credentials for the subprocess shell execution
    export AWS_ACCESS_KEY_ID
    export AWS_SECRET_ACCESS_KEY
    export AWS_DEFAULT_REGION
    export AWS_REGION="$AWS_DEFAULT_REGION"
    
    log "AWS credentials set successfully in active shell session."
else
    log "Verified existing AWS credentials and active session."
fi

# Step 2: Prompt for target Domain Name
read -p "Enter the domain name pointing to your Elastic IP (e.g. dsm.yourdomain.com): " DOMAIN_NAME
if [ -z "$DOMAIN_NAME" ]; then
    error "Domain name is required to configure Nginx reverse proxy and SSL."
fi

# Step 3: Launch Infrastructure script
log "Phase 1: Launching AWS Infrastructure Provisioning..."
chmod +x deployment/setup_aws_infra.sh
./deployment/setup_aws_infra.sh

# Step 4: Launch Host script
log "Phase 2: Launching remote system configuration and deploy..."
chmod +x deployment/setup_host.sh
./deployment/setup_host.sh "$DOMAIN_NAME"

log "========================================================"
log "🎉 SUCCESS: Dive Service Management is now fully live!"
log "Visit: https://$DOMAIN_NAME"
log "========================================================"
