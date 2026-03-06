#!/bin/bash
# Foundry TUI - Azure Setup Script
# Interactive guided setup for deploying Azure AI resources
#
# Usage:
#   ./scripts/setup.sh              # Full interactive setup
#   ./scripts/setup.sh --only-search  # Add Tavily web search to existing setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source common functions
source "$SCRIPT_DIR/lib/common.sh"

# Default values
DEFAULT_RESOURCE_GROUP="foundry-tui-rg"
DEFAULT_LOCATION="eastus"

# Parse arguments
ONLY_SEARCH=false
for arg in "$@"; do
    case $arg in
        --only-search) ONLY_SEARCH=true ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Welcome
# ─────────────────────────────────────────────────────────────────────────────

clear
echo ""
if [[ "$ONLY_SEARCH" == true ]]; then
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║       ${CYAN}Foundry TUI - Add Web Search${NC}${BOLD}                           ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "This will configure Tavily web search for tool calling"
    echo "in your existing Foundry TUI setup."
else
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║           ${CYAN}Foundry TUI - Azure Setup${NC}${BOLD}                         ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "This script will guide you through deploying the Azure resources"
    echo "needed to run Foundry TUI."
fi
echo ""
print_dim "You will need:"
print_dim "  • Azure CLI installed and authenticated"
print_dim "  • An active Azure subscription"
print_dim "  • Permissions to create resources"
echo ""

if ! confirm "Ready to begin?"; then
    echo "Setup cancelled."
    exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
# Prerequisites Check
# ─────────────────────────────────────────────────────────────────────────────

print_header "Checking Prerequisites"

# Check Azure CLI
if ! require_command "az" "https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"; then
    exit 1
fi
print_success "Azure CLI installed"

# Check authentication
if ! check_az_auth; then
    echo ""
    print_info "Please log in to Azure CLI:"
    az login
fi
print_success "Azure CLI authenticated"

# Get current subscription
SUBSCRIPTION_INFO=$(az account show --query "{name:name, id:id}" -o tsv)
SUBSCRIPTION_NAME=$(echo "$SUBSCRIPTION_INFO" | cut -f1)
SUBSCRIPTION_ID=$(echo "$SUBSCRIPTION_INFO" | cut -f2)

echo ""
print_info "Current subscription: ${BOLD}$SUBSCRIPTION_NAME${NC}"
print_dim "  ID: $SUBSCRIPTION_ID"
echo ""

if ! confirm "Use this subscription?"; then
    echo ""
    print_info "Available subscriptions:"
    az account list --query "[].{Name:name, ID:id}" -o table
    echo ""
    echo -ne "${YELLOW}?${NC} Enter subscription ID: "
    read -r NEW_SUB_ID
    az account set --subscription "$NEW_SUB_ID"
    SUBSCRIPTION_ID="$NEW_SUB_ID"
    print_success "Switched subscription"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Resource Group Setup
# ─────────────────────────────────────────────────────────────────────────────

print_header "Resource Group Configuration"

if [[ "$ONLY_SEARCH" == true ]]; then
    # In search-only mode, skip resource group — we just need the .env file
    cd "$PROJECT_ROOT"
    if [[ -f ".env" ]]; then
        eval "$(grep -E '^AZURE_RESOURCE_GROUP=' .env)"
        RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
    fi

    if [[ -z "$RESOURCE_GROUP" ]]; then
        prompt_with_default "Resource group name" "$DEFAULT_RESOURCE_GROUP" RESOURCE_GROUP
    else
        print_info "Using resource group from .env: ${BOLD}$RESOURCE_GROUP${NC}"
    fi

    if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
        print_error "Resource group '$RESOURCE_GROUP' not found. Run full setup first."
        exit 1
    fi
else
    prompt_with_default "Resource group name" "$DEFAULT_RESOURCE_GROUP" RESOURCE_GROUP
    prompt_with_default "Location" "$DEFAULT_LOCATION" LOCATION

    # Check if resource group exists
    if az group show --name "$RESOURCE_GROUP" &> /dev/null; then
        print_info "Resource group '$RESOURCE_GROUP' already exists"
    else
        print_info "Creating resource group '$RESOURCE_GROUP' in '$LOCATION'..."
        az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
        print_success "Resource group created"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Model Selection & Deployment (skip in --only-search mode)
# ─────────────────────────────────────────────────────────────────────────────

if [[ "$ONLY_SEARCH" != true ]]; then

# ─────────────────────────────────────────────────────────────────────────────
# Model Selection
# ─────────────────────────────────────────────────────────────────────────────

print_header "Model Selection"

echo "Select which models to deploy (enter numbers separated by spaces):"
echo ""
echo -e "${BOLD}Azure OpenAI Models:${NC}"
echo "  1) GPT-4o           - Latest multimodal model (~\$2.50/1M in, \$10/1M out)"
echo "  2) GPT-4o-mini      - Smaller, faster, cheaper (~\$0.15/1M in, \$0.60/1M out)"
echo "  3) o4-mini          - Reasoning model (~\$1.10/1M in, \$4.40/1M out)"
echo ""
echo -e "${BOLD}Azure AI Models (pay-per-token):${NC}"
echo "  4) DeepSeek R1      - Reasoning (~\$0.55/1M in, \$2.19/1M out)"
echo "  5) DeepSeek V3      - Chat (~\$0.27/1M in, \$1.10/1M out)"
echo "  6) Grok 3           - xAI chat model (pricing varies)"
echo ""
echo -e "${DIM}Note: Serverless models (Mistral) require manual deployment via Azure AI Foundry portal${NC}"
echo ""

echo -ne "${YELLOW}?${NC} Enter model numbers [1 2]: "
read -r MODEL_SELECTION
MODEL_SELECTION="${MODEL_SELECTION:-1 2}"

# Parse selection
DEPLOY_OPENAI=false
DEPLOY_AI=false
OPENAI_MODELS=()
AI_MODELS=()

for num in $MODEL_SELECTION; do
    case $num in
        1) DEPLOY_OPENAI=true; OPENAI_MODELS+=("gpt-4o") ;;
        2) DEPLOY_OPENAI=true; OPENAI_MODELS+=("gpt-4o-mini") ;;
        3) DEPLOY_OPENAI=true; OPENAI_MODELS+=("o4-mini") ;;
        4) DEPLOY_AI=true; AI_MODELS+=("deepseek-r1") ;;
        5) DEPLOY_AI=true; AI_MODELS+=("deepseek-v3") ;;
        6) DEPLOY_AI=true; AI_MODELS+=("grok-3") ;;
        *) print_warning "Unknown selection: $num" ;;
    esac
done

echo ""
print_info "Selected models:"
for model in "${OPENAI_MODELS[@]}"; do
    print_dim "  • $model (Azure OpenAI)"
done
for model in "${AI_MODELS[@]}"; do
    print_dim "  • $model (Azure AI)"
done
echo ""

if ! confirm "Deploy these models?"; then
    echo "Setup cancelled."
    exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
# Backup existing .env
# ─────────────────────────────────────────────────────────────────────────────

cd "$PROJECT_ROOT"
backup_env ".env"

# Update base .env settings
update_env "AZURE_SUBSCRIPTION_ID" "$SUBSCRIPTION_ID"
update_env "AZURE_RESOURCE_GROUP" "$RESOURCE_GROUP"
update_env "AZURE_LOCATION" "$LOCATION"

# ─────────────────────────────────────────────────────────────────────────────
# Deploy Azure OpenAI
# ─────────────────────────────────────────────────────────────────────────────

if [[ "$DEPLOY_OPENAI" == true ]]; then
    print_header "Deploying Azure OpenAI"

    OPENAI_ACCOUNT_NAME="foundry-tui-openai-${RANDOM}"

    # Check if we already have an OpenAI resource
    EXISTING_OPENAI=$(az cognitiveservices account list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[?kind=='OpenAI'].name" -o tsv 2>/dev/null | head -1)

    if [[ -n "$EXISTING_OPENAI" ]]; then
        print_info "Using existing Azure OpenAI resource: $EXISTING_OPENAI"
        OPENAI_ACCOUNT_NAME="$EXISTING_OPENAI"
    else
        print_info "Creating Azure OpenAI resource..."
        az cognitiveservices account create \
            --name "$OPENAI_ACCOUNT_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --kind "OpenAI" \
            --sku "S0" \
            --output none
        print_success "Azure OpenAI resource created"
    fi

    # Get endpoint and key
    OPENAI_ENDPOINT=$(az cognitiveservices account show \
        --name "$OPENAI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.endpoint" -o tsv)

    OPENAI_KEY=$(az cognitiveservices account keys list \
        --name "$OPENAI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "key1" -o tsv)

    # Update .env
    update_env "AZURE_OPENAI_ENDPOINT" "$OPENAI_ENDPOINT"
    update_env "AZURE_OPENAI_API_KEY" "$OPENAI_KEY"
    update_env "AZURE_OPENAI_API_VERSION" "2024-12-01-preview"
    update_env "AZURE_OPENAI_EMBEDDING_DEPLOYMENT" "text-embedding-3-small"

    print_success "Azure OpenAI configured"

    # Deploy models
    for model in "${OPENAI_MODELS[@]}"; do
        print_info "Deploying model: $model..."

        # Check if deployment exists
        if az cognitiveservices account deployment show \
            --name "$OPENAI_ACCOUNT_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --deployment-name "$model" &> /dev/null; then
            print_dim "  Model $model already deployed"
        else
            az cognitiveservices account deployment create \
                --name "$OPENAI_ACCOUNT_NAME" \
                --resource-group "$RESOURCE_GROUP" \
                --deployment-name "$model" \
                --model-name "$model" \
                --model-version "latest" \
                --model-format "OpenAI" \
                --sku-capacity 10 \
                --sku-name "Standard" \
                --output none 2>/dev/null || {
                    print_warning "Could not deploy $model - may need manual setup or quota"
                }
        fi
    done

    print_success "Azure OpenAI models deployed"

    # Auto-deploy embedding model for semantic memory search
    print_info "Deploying embedding model: text-embedding-3-small..."
    if az cognitiveservices account deployment show \
        --name "$OPENAI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --deployment-name "text-embedding-3-small" &> /dev/null; then
        print_dim "  Embedding model already deployed"
    else
        az cognitiveservices account deployment create \
            --name "$OPENAI_ACCOUNT_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --deployment-name "text-embedding-3-small" \
            --model-name "text-embedding-3-small" \
            --model-version "1" \
            --model-format "OpenAI" \
            --sku-capacity 1 \
            --sku-name "GlobalStandard" \
            --output none 2>/dev/null || {
                print_warning "Could not deploy embedding model - semantic memory search will use keyword fallback"
            }
    fi

    # Auto-deploy image generation model
    print_info "Deploying image model: gpt-image-1..."
    if az cognitiveservices account deployment show \
        --name "$OPENAI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --deployment-name "gpt-image-1" &> /dev/null; then
        print_dim "  Image model already deployed"
    else
        az cognitiveservices account deployment create \
            --name "$OPENAI_ACCOUNT_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --deployment-name "gpt-image-1" \
            --model-name "gpt-image-1" \
            --model-version "1" \
            --model-format "OpenAI" \
            --sku-capacity 1 \
            --sku-name "Standard" \
            --output none 2>/dev/null || {
                print_warning "Could not deploy gpt-image-1 - image generation will not be available"
                print_dim "  Model may not be available in your region yet. You can deploy manually later."
            }
    fi
    # Write env var if deployment exists (may have been pre-existing)
    if az cognitiveservices account deployment show \
        --name "$OPENAI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --deployment-name "gpt-image-1" &> /dev/null; then
        update_env "AZURE_OPENAI_IMAGE_DEPLOYMENT" "gpt-image-1"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Deploy Azure AI Services
# ─────────────────────────────────────────────────────────────────────────────

if [[ "$DEPLOY_AI" == true ]]; then
    print_header "Deploying Azure AI Services"

    AI_ACCOUNT_NAME="foundry-tui-ai-${RANDOM}"

    # Check if we already have an AI Services resource
    EXISTING_AI=$(az cognitiveservices account list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[?kind=='AIServices'].name" -o tsv 2>/dev/null | head -1)

    if [[ -n "$EXISTING_AI" ]]; then
        print_info "Using existing Azure AI Services resource: $EXISTING_AI"
        AI_ACCOUNT_NAME="$EXISTING_AI"
    else
        print_info "Creating Azure AI Services resource..."
        az cognitiveservices account create \
            --name "$AI_ACCOUNT_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --kind "AIServices" \
            --sku "S0" \
            --output none 2>/dev/null || {
                print_warning "Could not create AIServices - trying CognitiveServices"
                az cognitiveservices account create \
                    --name "$AI_ACCOUNT_NAME" \
                    --resource-group "$RESOURCE_GROUP" \
                    --location "$LOCATION" \
                    --kind "CognitiveServices" \
                    --sku "S0" \
                    --output none
            }
        print_success "Azure AI Services resource created"
    fi

    # Get endpoint and key
    AI_ENDPOINT=$(az cognitiveservices account show \
        --name "$AI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.endpoint" -o tsv)

    AI_KEY=$(az cognitiveservices account keys list \
        --name "$AI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "key1" -o tsv)

    # Update .env
    update_env "AZURE_AI_ENDPOINT" "$AI_ENDPOINT"
    update_env "AZURE_AI_API_KEY" "$AI_KEY"

    print_success "Azure AI Services configured"

    print_warning "Note: DeepSeek, Grok, and other marketplace models require"
    print_warning "deployment through Azure AI Foundry portal."
    print_dim "  Visit: https://ai.azure.com"
fi

fi  # end of --only-search skip

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Web Search (Optional - for tool calling)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
print_header "Web Search for Tool Calling"
echo ""
echo "Foundry TUI supports tool calling with web search via Tavily."
echo "Models that support tool calling can search the web during conversations."
echo ""
print_dim "Get a free API key at: https://tavily.com (1,000 searches/month free)"
echo ""

DEPLOY_SEARCH=false
# In --only-search mode, skip the confirmation — that's the whole point
if [[ "$ONLY_SEARCH" == true ]] || confirm "Would you like to enable web search for tool calling?"; then
    DEPLOY_SEARCH=true

    cd "$PROJECT_ROOT"
    backup_env ".env"

    echo ""
    echo -e "Enter your Tavily API key (starts with ${CYAN}tvly-${NC}):"
    echo -e "${DIM}Get one free at: https://tavily.com${NC}"
    read -rp "> " TAVILY_KEY

    if [[ -z "$TAVILY_KEY" ]]; then
        print_warning "No API key entered — skipping web search"
        DEPLOY_SEARCH=false
    else
        update_env "TAVILY_API_KEY" "$TAVILY_KEY"
        print_success "Tavily web search configured for tool calling"
    fi
else
    print_dim "Skipping web search — tool calling will work without it"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

print_header "Setup Complete!"

echo ""
echo -e "${GREEN}Your .env file has been configured with:${NC}"
echo ""
if [[ "$DEPLOY_OPENAI" == true ]]; then
    echo "  • Azure OpenAI endpoint and key"
    echo "  • Models: ${OPENAI_MODELS[*]}"
fi
if [[ "$DEPLOY_AI" == true ]]; then
    echo "  • Azure AI Services endpoint and key"
    echo "  • Models: ${AI_MODELS[*]} (deploy via portal)"
fi
if [[ "$DEPLOY_SEARCH" == true ]]; then
    echo "  • Tavily API key (web search tool calling enabled)"
fi
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo ""
echo "  1. Run the app:"
echo -e "     ${CYAN}./run.sh${NC}"
echo ""
if [[ "$DEPLOY_AI" == true ]]; then
    echo "  2. Deploy marketplace models (DeepSeek, Grok) via Azure AI Foundry:"
    echo -e "     ${CYAN}https://ai.azure.com${NC}"
    echo ""
fi
echo "  3. To clean up resources later, run:"
echo -e "     ${CYAN}./scripts/teardown.sh${NC}"
echo ""
print_dim "Resources created in: $RESOURCE_GROUP"
print_dim "Estimated cost: Pay-per-token only (no base cost)"
echo ""
