#!/usr/bin/env bash
# =========================================================================
# setup_aws_infra.sh - DSM AWS VM Provisioning Script
# =========================================================================
# Automates the creation of security groups, key pairs, EC2 instance,
# GP3 EBS volume, and Elastic IP on AWS.
#
# Requirements: AWS CLI installed and configured on the local system, jq.
# =========================================================================

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0;m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

# Check dependencies
command -v aws >/dev/null 2>&1 || error "AWS CLI is required but not installed."
command -v jq >/dev/null 2>&1 || error "jq is required but not installed."

# Verify AWS configuration
log "Verifying AWS credentials..."
aws sts get-caller-identity >/dev/null 2>&1 || error "Invalid AWS credentials. Run 'aws configure' first."

REGION=$(aws configure get region)
if [ -z "$REGION" ]; then
    REGION="us-east-1"
    warn "AWS default region not set. Defaulting to us-east-1."
fi
log "Using AWS region: $REGION"

INFRA_ENV="deployment/.env.infra"
rm -f "$INFRA_ENV"

# 1. Detect dynamic IP for SSH whitelisting
log "Detecting your public IP address..."
MY_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me)
if [ -z "$MY_IP" ]; then
    warn "Could not detect public IP. SSH will be opened to 0.0.0.0/0. Use caution!"
    SSH_CIDR="0.0.0.0/0"
else
    log "Detected IP: $MY_IP"
    SSH_CIDR="${MY_IP}/32"
fi

# 2. Get Default VPC and Subnet details
log "Retrieving default VPC..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text)
if [ "$VPC_ID" == "None" ] || [ -z "$VPC_ID" ]; then
    error "Default VPC not found. Please ensure a default VPC exists in region $REGION."
fi
log "Using Default VPC: $VPC_ID"

SUBNET_ID=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[0].SubnetId" --output text)
AZ=$(aws ec2 describe-subnets --filters "Name=subnet-id,Values=$SUBNET_ID" --query "Subnets[0].AvailabilityZone" --output text)
log "Using Subnet: $SUBNET_ID in Availability Zone: $AZ"

# 3. Create Key Pair
KEY_NAME="dsm-admin-key"
KEY_FILE="deployment/${KEY_NAME}.pem"
if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" >/dev/null 2>&1; then
    log "Creating EC2 Key Pair: $KEY_NAME..."
    aws ec2 create-key-pair --key-name "$KEY_NAME" --query "KeyMaterial" --output text > "$KEY_FILE"
    chmod 400 "$KEY_FILE"
    log "Saved private key to $KEY_FILE"
else
    warn "Key pair $KEY_NAME already exists in AWS. Ensure you have the corresponding .pem key."
fi

# 4. Create Security Group
SG_NAME="dsm-production-sg"
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SG_NAME" --query "SecurityGroups[0].GroupId" --output text)
if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
    log "Creating Security Group: $SG_NAME..."
    SG_ID=$(aws ec2 create-security-group --group-name "$SG_NAME" --description "DSM Production SG" --vpc-id "$VPC_ID" --query "GroupId" --output text)
    
    log "Authorizing inbound traffic..."
    # HTTP (80)
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0
    # HTTPS (443)
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 443 --cidr 0.0.0.0/0
    # SSH (22)
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$SSH_CIDR"
    log "Security Group created: $SG_ID"
else
    log "Security Group $SG_NAME already exists: $SG_ID"
fi

# 5. Query Latest Ubuntu 24.04 LTS AMI dynamically
log "Querying latest Ubuntu 24.04 LTS AMI..."
AMI_ID=$(aws ec2 describe-images \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
              "Name=state,Values=available" \
    --query "sort_by(Images, &CreationDate)[-1].ImageId" \
    --output text)
if [ -z "$AMI_ID" ] || [ "$AMI_ID" == "None" ]; then
    error "Could not find Ubuntu 24.04 AMI. Check AWS region and connection."
fi
log "Latest Ubuntu 24.04 AMI: $AMI_ID"

# 6. Launch EC2 Instance
log "Launching EC2 instance (t3.medium)..."
INSTANCE_JSON=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type t3.medium \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --subnet-id "$SUBNET_ID" \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=dsm-production-server}]' \
    --output json)

INSTANCE_ID=$(echo "$INSTANCE_JSON" | jq -r '.Instances[0].InstanceId')
log "Instance launched: $INSTANCE_ID"

# 7. Wait for Instance to be running
log "Waiting for instance to enter running state..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
log "Instance is running."

# 8. Create and Attach 50GB gp3 EBS Volume
log "Creating 50GB gp3 EBS volume in $AZ..."
VOLUME_ID=$(aws ec2 create-volume \
    --availability-zone "$AZ" \
    --size 50 \
    --volume-type gp3 \
    --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=dsm-production-data}]' \
    --query "VolumeId" \
    --output text)

log "Waiting for EBS volume to become available..."
aws ec2 wait volume-available --volume-ids "$VOLUME_ID"

log "Attaching EBS volume $VOLUME_ID to instance $INSTANCE_ID..."
aws ec2 attach-volume \
    --volume-id "$VOLUME_ID" \
    --instance-id "$INSTANCE_ID" \
    --device /dev/sdf

log "Waiting for EBS volume attachment to complete..."
aws ec2 wait volume-in-use --volume-ids "$VOLUME_ID"
log "EBS volume attached."

# 9. Allocate and Associate Elastic IP
log "Allocating Elastic IP..."
EIP_JSON=$(aws ec2 allocate-address --domain vpc --output json)
ALLOCATION_ID=$(echo "$EIP_JSON" | jq -r '.AllocationId')
PUBLIC_IP=$(echo "$EIP_JSON" | jq -r '.PublicIp')
log "Elastic IP allocated: $PUBLIC_IP"

log "Associating Elastic IP with instance..."
aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOCATION_ID"
log "Elastic IP associated."

# Save values for the setup_host.sh script
cat <<EOF > "$INFRA_ENV"
PUBLIC_IP=$PUBLIC_IP
INSTANCE_ID=$INSTANCE_ID
VOLUME_ID=$VOLUME_ID
KEY_FILE=$KEY_FILE
REGION=$REGION
EOF

log "AWS Infrastructure setup complete."
log "--------------------------------------------------------"
log "IP Address:   $PUBLIC_IP"
log "Instance ID:  $INSTANCE_ID"
log "Volume ID:    $VOLUME_ID"
log "Key File:     $KEY_FILE"
log "Region:       $REGION"
log "--------------------------------------------------------"
log "Details saved to $INFRA_ENV"
