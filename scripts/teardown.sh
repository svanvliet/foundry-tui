#!/bin/bash
# Foundry TUI - Azure Teardown Script
# Safely remove Azure resources created by setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source common functions
source "$SCRIPT_DIR/lib/common.sh"

# ─────────────────────────────────────────────────────────────────────────────
# Welcome
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${RED}║           Foundry TUI - Resource Cleanup${NC}${BOLD}${RED}                    ║${NC}"
echo -e "${BOLD}${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
print_warning "This script will DELETE Azure resources."
print_warning "This action cannot be undone!"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Prerequisites Check
# ─────────────────────────────────────────────────────────────────────────────

if ! require_command "az" "https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"; then
    exit 1
fi

if ! check_az_auth; then
    echo ""
    print_info "Please log in to Azure CLI:"
    az login
fi

# ─────────────────────────────────────────────────────────────────────────────
# Load configuration from .env
# ─────────────────────────────────────────────────────────────────────────────

cd "$PROJECT_ROOT"

if [[ -f ".env" ]]; then
    # shellcheck disable=SC1091
    eval "$(grep -E '^AZURE_(SUBSCRIPTION_ID|RESOURCE_GROUP)=' .env)"
fi

if [[ -z "$AZURE_RESOURCE_GROUP" ]]; then
    echo -ne "${YELLOW}?${NC} Enter resource group name to delete: "
    read -r AZURE_RESOURCE_GROUP
fi

if [[ -z "$AZURE_RESOURCE_GROUP" ]]; then
    print_error "No resource group specified."
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Show resources to be deleted
# ─────────────────────────────────────────────────────────────────────────────

print_header "Resources to Delete"

# Check if resource group exists
if ! az group show --name "$AZURE_RESOURCE_GROUP" &> /dev/null; then
    print_error "Resource group '$AZURE_RESOURCE_GROUP' not found."
    exit 1
fi

echo ""
echo -e "Resource Group: ${BOLD}$AZURE_RESOURCE_GROUP${NC}"
echo ""

# List resources in the group
print_info "Resources in this group:"
az resource list \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --query "[].{Name:name, Type:type}" \
    -o table 2>/dev/null || print_dim "  (no resources found)"

echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Confirmation
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${RED}${BOLD}WARNING: This will delete the entire resource group and ALL resources inside it.${NC}"
echo ""

echo -ne "${YELLOW}?${NC} Type the resource group name to confirm deletion: "
read -r CONFIRM_NAME

if [[ "$CONFIRM_NAME" != "$AZURE_RESOURCE_GROUP" ]]; then
    print_error "Names don't match. Deletion cancelled."
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Delete resources
# ─────────────────────────────────────────────────────────────────────────────

print_header "Deleting Resources"

print_info "Deleting resource group '$AZURE_RESOURCE_GROUP'..."
print_dim "This may take a few minutes..."

az group delete \
    --name "$AZURE_RESOURCE_GROUP" \
    --yes \
    --no-wait

print_success "Resource group deletion initiated"
print_dim "Deletion is running in the background."

# ─────────────────────────────────────────────────────────────────────────────
# Clean up .env (optional)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
if confirm "Clear Azure credentials from .env file?"; then
    # Comment out Azure settings instead of deleting
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' 's/^AZURE_OPENAI_/#AZURE_OPENAI_/' .env 2>/dev/null || true
        sed -i '' 's/^AZURE_AI_/#AZURE_AI_/' .env 2>/dev/null || true
        sed -i '' 's/^SERVERLESS_/#SERVERLESS_/' .env 2>/dev/null || true
        sed -i '' 's/^TAVILY_/#TAVILY_/' .env 2>/dev/null || true
    else
        sed -i 's/^AZURE_OPENAI_/#AZURE_OPENAI_/' .env 2>/dev/null || true
        sed -i 's/^AZURE_AI_/#AZURE_AI_/' .env 2>/dev/null || true
        sed -i 's/^SERVERLESS_/#SERVERLESS_/' .env 2>/dev/null || true
        sed -i 's/^TAVILY_/#TAVILY_/' .env 2>/dev/null || true
    fi
    print_success "Credentials commented out in .env"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

print_header "Cleanup Complete"

echo ""
echo "The resource group is being deleted in the background."
echo ""
echo "To verify deletion:"
echo -e "  ${CYAN}az group show --name $AZURE_RESOURCE_GROUP${NC}"
echo ""
echo "To re-deploy resources:"
echo -e "  ${CYAN}./scripts/setup.sh${NC}"
echo ""
