#!/usr/bin/env bash
# =============================================================================
# Dive Service Management -- First-Time Setup & Management Script
# =============================================================================
# Supports: Raspberry Pi OS (Debian/ARM64), Ubuntu/Debian (x86-64), Windows WSL2
#
# Usage:
#   ./scripts/setup.sh                    # Full first-time setup (interactive)
#   ./scripts/setup.sh --non-interactive  # Automated setup with defaults
#   ./scripts/setup.sh upgrade            # Pull latest, rebuild, migrate
#   ./scripts/setup.sh backup             # Backup database
#   ./scripts/setup.sh restore <file>     # Restore database from backup
#   ./scripts/setup.sh status             # Show system status
#   ./scripts/setup.sh stop               # Stop all containers
#   ./scripts/setup.sh start              # Start all containers
#   ./scripts/setup.sh reset              # Full reset (drops database!)
#   ./scripts/setup.sh logs               # Tail live logs
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/.env"
ENV_EXAMPLE="${PROJECT_DIR}/.env.example"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"
COMPOSE_LIGHTWEIGHT="${PROJECT_DIR}/docker-compose.lightweight.yml"
BACKUP_DIR="${PROJECT_DIR}/backups"

# Defaults for non-interactive mode
DEFAULT_PORT=8080
DEFAULT_BIND="0.0.0.0"
DEFAULT_COMPANY="Dive Service Management"
DEFAULT_ADMIN_USER="admin"
DEFAULT_ADMIN_EMAIL="admin@localhost"
DEFAULT_ADMIN_PASS="changeme"

# Minimum resource thresholds
MIN_RAM_MB=1024
MIN_DISK_GB=4

# Flags
NON_INTERACTIVE=false
LIGHTWEIGHT=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_step() {
    echo -e "\n${BLUE}==>${NC} $1"
}

prompt() {
    local prompt_text="$1"
    local default_value="$2"
    local var_name="$3"

    if [[ "${NON_INTERACTIVE}" == "true" ]]; then
        eval "${var_name}='${default_value}'"
        return
    fi

    read -r -p "${prompt_text} [${default_value}]: " input
    eval "${var_name}='${input:-${default_value}}'"
}

generate_secret() {
    # Try Python first, then openssl, then urandom
    if command -v python3 &>/dev/null; then
        python3 -c "import secrets; print(secrets.token_hex(32))"
    elif command -v openssl &>/dev/null; then
        openssl rand -hex 32
    else
        head -c 32 /dev/urandom | xxd -p | tr -d '\n'
    fi
}

get_compose_cmd() {
    # Build the docker compose command with appropriate files
    local cmd="docker compose -f ${COMPOSE_FILE}"
    if [[ "${LIGHTWEIGHT}" == "true" ]]; then
        cmd="${cmd} -f ${COMPOSE_LIGHTWEIGHT}"
    fi
    echo "${cmd}"
}

detect_architecture() {
    local arch
    arch="$(uname -m)"
    case "${arch}" in
        aarch64|arm64) echo "arm64" ;;
        x86_64|amd64)  echo "amd64" ;;
        *)             echo "${arch}" ;;
    esac
}

detect_pi() {
    # Detect if running on a Raspberry Pi
    if [[ -f /proc/device-tree/model ]]; then
        if grep -qi "raspberry" /proc/device-tree/model 2>/dev/null; then
            return 0
        fi
    fi
    if grep -qi "raspberry" /proc/cpuinfo 2>/dev/null; then
        return 0
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Pre-Flight Checks
# ---------------------------------------------------------------------------

preflight_checks() {
    log_step "Running pre-flight checks..."

    local arch
    arch="$(detect_architecture)"
    log_info "Architecture: ${arch}"

    local os_info
    os_info="$(uname -s) $(uname -r)"
    log_info "OS: ${os_info}"

    # Check for Raspberry Pi
    if detect_pi; then
        log_info "Raspberry Pi detected"
        if [[ "${NON_INTERACTIVE}" == "true" ]]; then
            LIGHTWEIGHT=true
            log_info "Auto-selecting lightweight deployment profile"
        else
            echo ""
            read -r -p "Raspberry Pi detected. Use lightweight profile (Huey instead of Celery)? [Y/n]: " pi_choice
            if [[ "${pi_choice}" != "n" && "${pi_choice}" != "N" ]]; then
                LIGHTWEIGHT=true
                log_info "Using lightweight deployment profile"
            fi
        fi
    fi

    # Check for Docker
    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed."
        echo ""
        echo "Install Docker with the official convenience script:"
        echo "  curl -fsSL https://get.docker.com | sh"
        echo "  sudo usermod -aG docker \$USER"
        echo "  # Log out and back in, then re-run this script"
        echo ""
        if [[ "${NON_INTERACTIVE}" == "false" ]]; then
            read -r -p "Attempt automatic Docker installation? [y/N]: " install_docker
            if [[ "${install_docker}" == "y" || "${install_docker}" == "Y" ]]; then
                log_info "Installing Docker..."
                curl -fsSL https://get.docker.com | sh
                sudo usermod -aG docker "${USER}" || true
                log_warn "You may need to log out and back in for Docker group membership to take effect."
            else
                exit 1
            fi
        else
            exit 1
        fi
    fi
    log_info "Docker: $(docker --version)"

    # Check for Docker Compose (v2 plugin)
    if ! docker compose version &>/dev/null; then
        log_error "Docker Compose V2 is not available."
        echo "It should be included with recent Docker installations."
        echo "Install it with: sudo apt-get install docker-compose-plugin"
        exit 1
    fi
    log_info "Docker Compose: $(docker compose version --short)"

    # Check available RAM
    if command -v free &>/dev/null; then
        local total_ram_mb
        total_ram_mb=$(free -m | awk '/^Mem:/{print $2}')
        if [[ "${total_ram_mb}" -lt "${MIN_RAM_MB}" ]]; then
            log_warn "Low RAM: ${total_ram_mb}MB detected (recommended: ${MIN_RAM_MB}MB+)"
            if [[ "${LIGHTWEIGHT}" == "false" ]]; then
                log_warn "Consider using the lightweight profile for low-memory systems."
            fi
        else
            log_info "RAM: ${total_ram_mb}MB"
        fi
    fi

    # Check available disk space
    local available_disk_gb
    available_disk_gb=$(df -BG "${PROJECT_DIR}" | awk 'NR==2{gsub("G",""); print $4}')
    if [[ "${available_disk_gb}" -lt "${MIN_DISK_GB}" ]]; then
        log_warn "Low disk space: ${available_disk_gb}GB available (recommended: ${MIN_DISK_GB}GB+)"
    else
        log_info "Disk: ${available_disk_gb}GB available"
    fi

    # Check for git
    if command -v git &>/dev/null; then
        log_info "Git: $(git --version)"
    else
        log_warn "Git is not installed (optional, but useful for updates)"
    fi

    log_info "Pre-flight checks passed."
}

# ---------------------------------------------------------------------------
# Configuration Generation
# ---------------------------------------------------------------------------

generate_config() {
    log_step "Generating configuration..."

    if [[ -f "${ENV_FILE}" ]]; then
        log_info "Using existing .env file"
        return
    fi

    if [[ ! -f "${ENV_EXAMPLE}" ]]; then
        log_error ".env.example not found at ${ENV_EXAMPLE}"
        exit 1
    fi

    # Copy template
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"

    # Generate secrets
    local secret_key
    secret_key="$(generate_secret)"
    local password_salt
    password_salt="$(generate_secret)"
    local db_root_pass
    db_root_pass="$(generate_secret)"
    local db_pass
    db_pass="$(generate_secret)"

    # Prompt for configuration (or use defaults in non-interactive mode)
    local app_port app_bind company_name
    prompt "Application port" "${DEFAULT_PORT}" app_port
    prompt "Bind address" "${DEFAULT_BIND}" app_bind
    prompt "Company name" "${DEFAULT_COMPANY}" company_name

    # Determine deployment profile
    local profile="full"
    if [[ "${LIGHTWEIGHT}" == "true" ]]; then
        profile="lightweight"
    fi

    # Write values to .env
    # Use sed for in-place replacement (portable across GNU and BSD sed)
    sed -i "s|^DSM_SECRET_KEY=.*|DSM_SECRET_KEY=${secret_key}|" "${ENV_FILE}"
    sed -i "s|^DSM_SECURITY_PASSWORD_SALT=.*|DSM_SECURITY_PASSWORD_SALT=${password_salt}|" "${ENV_FILE}"
    sed -i "s|^DSM_PORT=.*|DSM_PORT=${app_port}|" "${ENV_FILE}"
    sed -i "s|^DSM_BIND_ADDRESS=.*|DSM_BIND_ADDRESS=${app_bind}|" "${ENV_FILE}"
    sed -i "s|^MARIADB_ROOT_PASSWORD=.*|MARIADB_ROOT_PASSWORD=${db_root_pass}|" "${ENV_FILE}"
    sed -i "s|^MARIADB_PASSWORD=.*|MARIADB_PASSWORD=${db_pass}|" "${ENV_FILE}"
    sed -i "s|^DSM_DEPLOYMENT_PROFILE=.*|DSM_DEPLOYMENT_PROFILE=${profile}|" "${ENV_FILE}"

    # Update database URL with the generated password
    sed -i "s|^DSM_DATABASE_URL=.*|DSM_DATABASE_URL=mysql+mysqldb://dsm:${db_pass}@db:3306/dsm|" "${ENV_FILE}"

    log_info "Configuration written to ${ENV_FILE}"
    log_info "Company name '${company_name}' will be set in database on first boot."

    # Store company name for seeding later
    export DSM_COMPANY_NAME="${company_name}"
}

# ---------------------------------------------------------------------------
# Directory Creation
# ---------------------------------------------------------------------------

create_directories() {
    log_step "Creating required directories..."

    local dirs=(
        "${PROJECT_DIR}/uploads/logos"
        "${PROJECT_DIR}/uploads/imports"
        "${PROJECT_DIR}/uploads/exports"
        "${PROJECT_DIR}/uploads/attachments"
        "${PROJECT_DIR}/logs"
        "${PROJECT_DIR}/instance"
        "${PROJECT_DIR}/backups"
    )

    for dir in "${dirs[@]}"; do
        mkdir -p "${dir}"
    done

    # Set permissions (writable by the dsm user in the container, UID typically 999)
    chmod -R 775 "${PROJECT_DIR}/uploads" "${PROJECT_DIR}/logs" "${PROJECT_DIR}/instance"

    log_info "Directories created."
}

# ---------------------------------------------------------------------------
# Build and Start
# ---------------------------------------------------------------------------

build_and_start() {
    log_step "Building and starting containers..."

    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    log_info "Building Docker images..."
    ${compose_cmd} build

    log_info "Starting services..."
    ${compose_cmd} up -d

    # Wait for health checks
    log_info "Waiting for services to become healthy..."
    local max_wait=120
    local waited=0
    local interval=5

    while [[ ${waited} -lt ${max_wait} ]]; do
        # Check if web container is healthy
        local health
        health=$(docker inspect --format='{{.State.Health.Status}}' dsm-web 2>/dev/null || echo "starting")
        if [[ "${health}" == "healthy" ]]; then
            break
        fi

        # Check if db is healthy
        local db_health
        db_health=$(docker inspect --format='{{.State.Health.Status}}' dsm-db 2>/dev/null || echo "starting")

        echo -ne "\r  Waiting... DB: ${db_health}, Web: ${health} (${waited}s/${max_wait}s)"
        sleep ${interval}
        waited=$((waited + interval))
    done
    echo "" # newline after progress

    if [[ ${waited} -ge ${max_wait} ]]; then
        log_warn "Timeout waiting for containers to become healthy."
        log_warn "Containers may still be starting. Check with: docker compose ps"
    else
        log_info "All services are running."
    fi

    # Print container status
    echo ""
    ${compose_cmd} ps
}

# ---------------------------------------------------------------------------
# Database Setup
# ---------------------------------------------------------------------------

run_migrations() {
    log_step "Running database migrations..."

    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    ${compose_cmd} exec -T web flask db upgrade
    log_info "Migrations complete."
}

seed_database() {
    log_step "Seeding initial data..."

    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    ${compose_cmd} exec -T web flask seed-db || {
        log_warn "Seed command failed (the container may not be ready yet)."
        log_warn "You can run it manually later: docker compose exec web flask seed-db"
    }
}

create_admin_user() {
    log_step "Creating admin user..."

    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    local admin_user admin_email admin_pass
    prompt "Admin username" "${DEFAULT_ADMIN_USER}" admin_user
    prompt "Admin email" "${DEFAULT_ADMIN_EMAIL}" admin_email

    if [[ "${NON_INTERACTIVE}" == "true" ]]; then
        admin_pass="${DEFAULT_ADMIN_PASS}"
    else
        read -r -s -p "Admin password [changeme]: " admin_pass
        admin_pass="${admin_pass:-${DEFAULT_ADMIN_PASS}}"
        echo ""
    fi

    ${compose_cmd} exec -T web flask create-admin \
        --username "${admin_user}" \
        --email "${admin_email}" \
        --password "${admin_pass}" 2>/dev/null || {
        log_warn "create-admin command failed (the container may not be ready yet)."
        log_warn "You can run it manually later: docker compose exec web flask create-admin"
    }
}

# ---------------------------------------------------------------------------
# Print Summary
# ---------------------------------------------------------------------------

print_summary() {
    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    # Detect IP address for access URL
    local ip_addr
    ip_addr=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

    # Load port from .env
    local port
    port=$(grep "^DSM_PORT=" "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || echo "${DEFAULT_PORT}")

    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}  Dive Service Management - Setup Complete!${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo -e "  Access URL:    ${BLUE}http://${ip_addr}:${port}${NC}"
    echo ""
    echo -e "  ${YELLOW}Next steps:${NC}"
    echo "    1. Change the default admin password"
    echo "    2. Upload your company logo (Admin > Settings)"
    echo "    3. Review and customize the price list"
    echo "    4. Configure tax rate if applicable (Admin > Settings)"
    echo ""
    echo "  Useful commands:"
    echo "    make logs          - Tail application logs"
    echo "    make shell         - Open shell in web container"
    echo "    make backup        - Backup the database"
    echo "    make test          - Run the test suite"
    echo ""
    echo "  Configuration: ${ENV_FILE}"
    echo "  Backups:       ${BACKUP_DIR}/"
    echo "  Logs:          ${PROJECT_DIR}/logs/"
    echo ""

    if [[ "${LIGHTWEIGHT}" == "true" ]]; then
        echo -e "  ${YELLOW}Profile: Lightweight (Huey in-process, no Celery)${NC}"
    else
        echo -e "  Profile: Full (Celery worker + beat)"
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

cmd_setup() {
    preflight_checks
    generate_config
    create_directories
    build_and_start
    run_migrations
    seed_database
    create_admin_user
    print_summary
}

cmd_upgrade() {
    log_step "Upgrading Dive Service Management..."

    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    # Pull latest code if in a git repo
    if [[ -d "${PROJECT_DIR}/.git" ]]; then
        log_info "Pulling latest code..."
        cd "${PROJECT_DIR}" && git pull
    fi

    # Backup before upgrade
    log_info "Creating pre-upgrade backup..."
    "${SCRIPT_DIR}/backup.sh" "pre_upgrade_$(date +%Y%m%d_%H%M%S)" || {
        log_warn "Backup failed, continuing with upgrade..."
    }

    log_info "Rebuilding images..."
    ${compose_cmd} build

    log_info "Restarting services..."
    ${compose_cmd} up -d

    log_info "Running migrations..."
    ${compose_cmd} exec -T web flask db upgrade

    log_info "Upgrade complete."
}

cmd_status() {
    log_step "System Status"

    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    echo ""
    echo "Container Status:"
    ${compose_cmd} ps
    echo ""

    # Disk usage
    echo "Disk Usage:"
    echo "  Project:  $(du -sh "${PROJECT_DIR}" 2>/dev/null | cut -f1)"
    echo "  Uploads:  $(du -sh "${PROJECT_DIR}/uploads" 2>/dev/null | cut -f1)"
    echo "  Logs:     $(du -sh "${PROJECT_DIR}/logs" 2>/dev/null | cut -f1)"
    echo "  Backups:  $(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1)"
    echo ""

    # Docker volume sizes
    echo "Docker Volumes:"
    docker system df -v 2>/dev/null | grep dsm || echo "  (unable to retrieve)"
    echo ""

    # Last backup
    echo "Last Backup:"
    local last_backup
    last_backup=$(ls -t "${BACKUP_DIR}"/dsm_*.sql.gz 2>/dev/null | head -1)
    if [[ -n "${last_backup}" ]]; then
        echo "  ${last_backup} ($(du -h "${last_backup}" | cut -f1))"
        echo "  Created: $(stat -c '%y' "${last_backup}" 2>/dev/null || stat -f '%Sm' "${last_backup}" 2>/dev/null)"
    else
        echo "  No backups found."
    fi
}

cmd_backup() {
    "${SCRIPT_DIR}/backup.sh" "$@"
}

cmd_restore() {
    if [[ $# -lt 1 ]]; then
        log_error "Usage: $0 restore <backup-file>"
        exit 1
    fi
    "${SCRIPT_DIR}/restore.sh" "$@"
}

cmd_reset() {
    log_step "Reset - This will destroy ALL data!"

    if [[ "${NON_INTERACTIVE}" == "false" ]]; then
        echo ""
        echo -e "${RED}WARNING: This will stop all containers, delete the database,${NC}"
        echo -e "${RED}and re-run the full setup from scratch.${NC}"
        echo ""
        read -r -p "Type 'RESET' to confirm: " confirm
        if [[ "${confirm}" != "RESET" ]]; then
            echo "Reset cancelled."
            exit 0
        fi
    fi

    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    log_info "Stopping containers..."
    ${compose_cmd} down -v

    log_info "Removing .env file..."
    rm -f "${ENV_FILE}"

    log_info "Running full setup..."
    cmd_setup
}

cmd_logs() {
    local compose_cmd
    compose_cmd="$(get_compose_cmd)"
    ${compose_cmd} logs -f "$@"
}

cmd_stop() {
    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    log_info "Stopping all containers..."
    ${compose_cmd} stop
    log_info "Containers stopped."
}

cmd_start() {
    local compose_cmd
    compose_cmd="$(get_compose_cmd)"

    log_info "Starting all containers..."
    ${compose_cmd} up -d
    log_info "Containers started."
}

# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

main() {
    # Parse global flags
    local args=()
    for arg in "$@"; do
        case "${arg}" in
            --non-interactive)
                NON_INTERACTIVE=true
                ;;
            --lightweight)
                LIGHTWEIGHT=true
                ;;
            *)
                args+=("${arg}")
                ;;
        esac
    done

    # Check if lightweight profile is set in environment
    if [[ "${DSM_DEPLOYMENT_PROFILE:-}" == "lightweight" ]]; then
        LIGHTWEIGHT=true
    fi

    # Dispatch subcommand
    local subcommand="${args[0]:-setup}"
    local remaining_args=("${args[@]:1}")

    case "${subcommand}" in
        setup)
            cmd_setup
            ;;
        upgrade)
            cmd_upgrade
            ;;
        status)
            cmd_status
            ;;
        backup)
            cmd_backup "${remaining_args[@]}"
            ;;
        restore)
            cmd_restore "${remaining_args[@]}"
            ;;
        reset)
            cmd_reset
            ;;
        logs)
            cmd_logs "${remaining_args[@]}"
            ;;
        stop)
            cmd_stop
            ;;
        start)
            cmd_start
            ;;
        -h|--help|help)
            echo "Dive Service Management - Setup & Management Script"
            echo ""
            echo "Usage: $0 [--non-interactive] [--lightweight] [command]"
            echo ""
            echo "Commands:"
            echo "  setup     Full first-time setup (default)"
            echo "  upgrade   Pull latest code, rebuild, migrate, restart"
            echo "  status    Show container status, disk usage, last backup"
            echo "  backup    Backup database to backups/ directory"
            echo "  restore   Restore database from a backup file"
            echo "  reset     Stop containers, drop DB, re-run full setup"
            echo "  logs      Tail live application logs"
            echo "  stop      Stop all containers"
            echo "  start     Start all containers"
            echo "  help      Show this help message"
            echo ""
            echo "Flags:"
            echo "  --non-interactive  Use all defaults, no prompts"
            echo "  --lightweight      Use Pi-optimized profile (Huey, fewer containers)"
            ;;
        *)
            log_error "Unknown command: ${subcommand}"
            echo "Run '$0 help' for usage information."
            exit 1
            ;;
    esac
}

main "$@"
