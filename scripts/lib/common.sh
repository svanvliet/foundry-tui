#!/bin/bash
# Common functions for Foundry TUI setup scripts

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}$1${NC}"
    echo -e "${DIM}$(printf '%.0s─' {1..50})${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_info() {
    echo -e "${CYAN}→${NC} $1"
}

print_dim() {
    echo -e "${DIM}$1${NC}"
}

# Prompt for yes/no
confirm() {
    local prompt="${1:-Continue?}"
    echo -ne "${YELLOW}?${NC} ${prompt} [y/N] "
    read -r response
    [[ "$response" =~ ^[Yy]$ ]]
}

# Prompt for input with default
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"

    echo -ne "${YELLOW}?${NC} ${prompt} [${default}]: "
    read -r response
    if [[ -z "$response" ]]; then
        eval "$var_name='$default'"
    else
        eval "$var_name='$response'"
    fi
}

# Check if command exists
require_command() {
    local cmd="$1"
    local install_hint="$2"

    if ! command -v "$cmd" &> /dev/null; then
        print_error "'$cmd' is required but not installed."
        if [[ -n "$install_hint" ]]; then
            print_dim "  Install: $install_hint"
        fi
        return 1
    fi
    return 0
}

# Check Azure CLI authentication
check_az_auth() {
    if ! az account show &> /dev/null; then
        print_error "Not logged in to Azure CLI."
        print_dim "  Run: az login"
        return 1
    fi
    return 0
}

# Get current Azure subscription
get_subscription() {
    az account show --query "{name:name, id:id}" -o tsv 2>/dev/null
}

# Update .env file with a key-value pair
update_env() {
    local key="$1"
    local value="$2"
    local env_file="${3:-.env}"

    # Create .env if it doesn't exist
    if [[ ! -f "$env_file" ]]; then
        touch "$env_file"
    fi

    # Check if key exists
    if grep -q "^${key}=" "$env_file" 2>/dev/null; then
        # Update existing key (macOS compatible sed)
        if [[ "$(uname)" == "Darwin" ]]; then
            sed -i '' "s|^${key}=.*|${key}=${value}|" "$env_file"
        else
            sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
        fi
    else
        # Add new key
        echo "${key}=${value}" >> "$env_file"
    fi
}

# Backup .env file
backup_env() {
    local env_file="${1:-.env}"
    if [[ -f "$env_file" ]]; then
        cp "$env_file" "${env_file}.backup.$(date +%Y%m%d_%H%M%S)"
        print_dim "Backed up existing .env file"
    fi
}

# Spinner for long operations
spinner() {
    local pid=$1
    local message="${2:-Working...}"
    local spin='⣾⣽⣻⢿⡿⣟⣯⣷'
    local i=0

    while kill -0 $pid 2>/dev/null; do
        printf "\r${YELLOW}${spin:i++%${#spin}:1}${NC} ${message}"
        sleep 0.1
    done
    printf "\r"
}

# Format cost estimate
format_cost() {
    local input_cost="$1"
    local output_cost="$2"
    echo "\$${input_cost}/1M in, \$${output_cost}/1M out"
}
