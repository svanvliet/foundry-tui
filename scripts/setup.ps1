# Foundry TUI - Azure Setup Script (PowerShell)
# Interactive guided setup for deploying Azure AI resources
#
# Usage:
#   .\scripts\setup.ps1              # Full interactive setup
#   .\scripts\setup.ps1 -OnlySearch   # Add Tavily web search to existing setup

param(
    [switch]$OnlySearch
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Source common functions
. "$ScriptDir\lib\common.ps1"

# Default values
$DefaultResourceGroup = "foundry-tui-rg"
$DefaultLocation = "eastus"

# ─────────────────────────────────────────────────────────────────────────────
# Welcome
# ─────────────────────────────────────────────────────────────────────────────

Clear-Host
Write-Host ""
if ($OnlySearch) {
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Blue
    Write-Host "║       Foundry TUI - Add Web Search                           ║" -ForegroundColor Blue
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Blue
    Write-Host ""
    Write-Host "This will configure Tavily web search for tool calling"
    Write-Host "in your existing Foundry TUI setup."
} else {
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Blue
    Write-Host "║           Foundry TUI - Azure Setup                          ║" -ForegroundColor Blue
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Blue
    Write-Host ""
    Write-Host "This script will guide you through deploying the Azure resources"
    Write-Host "needed to run Foundry TUI."
}
Write-Host ""
Write-Dim "You will need:"
Write-Dim "  • Azure CLI installed and authenticated"
Write-Dim "  • An active Azure subscription"
Write-Dim "  • Permissions to create resources"
Write-Host ""

if (-not (Confirm-Action "Ready to begin?")) {
    Write-Host "Setup cancelled."
    exit 0
}

# ─────────────────────────────────────────────────────────────────────────────
# Prerequisites Check
# ─────────────────────────────────────────────────────────────────────────────

Write-Header "Checking Prerequisites"

# Check Azure CLI
if (-not (Test-Command "az")) {
    Write-Error "'az' is required but not installed."
    Write-Dim "  Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}
Write-Success "Azure CLI installed"

# Check authentication
if (-not (Test-AzureAuth)) {
    Write-Host ""
    Write-Info "Please log in to Azure CLI:"
    az login
}
Write-Success "Azure CLI authenticated"

# Get current subscription
$subscription = Get-AzureSubscription
Write-Host ""
Write-Info "Current subscription: $($subscription.name)"
Write-Dim "  ID: $($subscription.id)"
Write-Host ""

if (-not (Confirm-Action "Use this subscription?")) {
    Write-Host ""
    Write-Info "Available subscriptions:"
    az account list --query "[].{Name:name, ID:id}" -o table
    Write-Host ""
    $newSubId = Read-Host "? Enter subscription ID"
    az account set --subscription $newSubId
    $subscription = Get-AzureSubscription
    Write-Success "Switched subscription"
}

# ─────────────────────────────────────────────────────────────────────────────
# Resource Group Setup
# ─────────────────────────────────────────────────────────────────────────────

Write-Header "Resource Group Configuration"

if ($OnlySearch) {
    # In search-only mode, skip resource group — we just need the .env file
    Set-Location $ProjectRoot
    $ResourceGroup = $null
    if (Test-Path ".env") {
        $envContent = Get-Content ".env" | Where-Object { $_ -match "^AZURE_RESOURCE_GROUP=" }
        if ($envContent) {
            $ResourceGroup = ($envContent -split "=", 2)[1]
        }
    }

    if (-not $ResourceGroup) {
        $ResourceGroup = Read-HostWithDefault "Resource group name" $DefaultResourceGroup
    } else {
        Write-Info "Using resource group from .env: $ResourceGroup"
    }

    $rgExists = az group show --name $ResourceGroup 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Resource group '$ResourceGroup' not found. Run full setup first."
        exit 1
    }
} else {
    $ResourceGroup = Read-HostWithDefault "Resource group name" $DefaultResourceGroup
    $Location = Read-HostWithDefault "Location" $DefaultLocation

    # Check if resource group exists
    $rgExists = az group show --name $ResourceGroup 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Info "Resource group '$ResourceGroup' already exists"
    }
    else {
        Write-Info "Creating resource group '$ResourceGroup' in '$Location'..."
        az group create --name $ResourceGroup --location $Location --output none
        Write-Success "Resource group created"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Model Selection & Deployment (skip in -OnlySearch mode)
# ─────────────────────────────────────────────────────────────────────────────

if (-not $OnlySearch) {

# ─────────────────────────────────────────────────────────────────────────────
# Model Selection
# ─────────────────────────────────────────────────────────────────────────────

Write-Header "Model Selection"

Write-Host "Select which models to deploy (enter numbers separated by spaces):"
Write-Host ""
Write-Host "Azure OpenAI Models:" -ForegroundColor White
Write-Host "  1) GPT-4o           - Latest multimodal model"
Write-Host "  2) GPT-4o-mini      - Smaller, faster, cheaper"
Write-Host "  3) o4-mini          - Reasoning model"
Write-Host ""
Write-Host "Azure AI Models (pay-per-token):" -ForegroundColor White
Write-Host "  4) DeepSeek R1      - Reasoning"
Write-Host "  5) DeepSeek V3      - Chat"
Write-Host "  6) Grok 3           - xAI chat model"
Write-Host ""
Write-Dim "Note: Serverless models (Mistral) require manual deployment via Azure AI Foundry portal"
Write-Host ""

$selection = Read-Host "? Enter model numbers [1 2]"
if ([string]::IsNullOrWhiteSpace($selection)) { $selection = "1 2" }

# Parse selection
$DeployOpenAI = $false
$DeployAI = $false
$OpenAIModels = @()
$AIModels = @()

foreach ($num in $selection.Split(" ")) {
    switch ($num) {
        "1" { $DeployOpenAI = $true; $OpenAIModels += "gpt-4o" }
        "2" { $DeployOpenAI = $true; $OpenAIModels += "gpt-4o-mini" }
        "3" { $DeployOpenAI = $true; $OpenAIModels += "o4-mini" }
        "4" { $DeployAI = $true; $AIModels += "deepseek-r1" }
        "5" { $DeployAI = $true; $AIModels += "deepseek-v3" }
        "6" { $DeployAI = $true; $AIModels += "grok-3" }
    }
}

Write-Host ""
Write-Info "Selected models:"
foreach ($model in $OpenAIModels) { Write-Dim "  • $model (Azure OpenAI)" }
foreach ($model in $AIModels) { Write-Dim "  • $model (Azure AI)" }
Write-Host ""

if (-not (Confirm-Action "Deploy these models?")) {
    Write-Host "Setup cancelled."
    exit 0
}

# ─────────────────────────────────────────────────────────────────────────────
# Backup and update .env
# ─────────────────────────────────────────────────────────────────────────────

Set-Location $ProjectRoot
Backup-EnvFile ".env"

Update-EnvFile "AZURE_SUBSCRIPTION_ID" $subscription.id
Update-EnvFile "AZURE_RESOURCE_GROUP" $ResourceGroup
Update-EnvFile "AZURE_LOCATION" $Location

# ─────────────────────────────────────────────────────────────────────────────
# Deploy Azure OpenAI
# ─────────────────────────────────────────────────────────────────────────────

if ($DeployOpenAI) {
    Write-Header "Deploying Azure OpenAI"

    $OpenAIAccountName = "foundry-tui-openai-$(Get-Random)"

    # Check for existing resource
    $existingOpenAI = az cognitiveservices account list `
        --resource-group $ResourceGroup `
        --query "[?kind=='OpenAI'].name" -o tsv 2>$null | Select-Object -First 1

    if ($existingOpenAI) {
        Write-Info "Using existing Azure OpenAI resource: $existingOpenAI"
        $OpenAIAccountName = $existingOpenAI
    }
    else {
        Write-Info "Creating Azure OpenAI resource..."
        az cognitiveservices account create `
            --name $OpenAIAccountName `
            --resource-group $ResourceGroup `
            --location $Location `
            --kind "OpenAI" `
            --sku "S0" `
            --output none
        Write-Success "Azure OpenAI resource created"
    }

    # Get endpoint and key
    $OpenAIEndpoint = az cognitiveservices account show `
        --name $OpenAIAccountName `
        --resource-group $ResourceGroup `
        --query "properties.endpoint" -o tsv

    $OpenAIKey = az cognitiveservices account keys list `
        --name $OpenAIAccountName `
        --resource-group $ResourceGroup `
        --query "key1" -o tsv

    Update-EnvFile "AZURE_OPENAI_ENDPOINT" $OpenAIEndpoint
    Update-EnvFile "AZURE_OPENAI_API_KEY" $OpenAIKey
    Update-EnvFile "AZURE_OPENAI_API_VERSION" "2024-12-01-preview"
    Update-EnvFile "AZURE_OPENAI_EMBEDDING_DEPLOYMENT" "text-embedding-3-small"

    Write-Success "Azure OpenAI configured"

    # Deploy models
    foreach ($model in $OpenAIModels) {
        Write-Info "Deploying model: $model..."

        try {
            az cognitiveservices account deployment create `
                --name $OpenAIAccountName `
                --resource-group $ResourceGroup `
                --deployment-name $model `
                --model-name $model `
                --model-version "latest" `
                --model-format "OpenAI" `
                --sku-capacity 10 `
                --sku-name "Standard" `
                --output none 2>$null
        }
        catch {
            Write-Warning "Could not deploy $model - may need manual setup or quota"
        }
    }

    Write-Success "Azure OpenAI models deployed"

    # Auto-deploy embedding model for semantic memory search
    Write-Info "Deploying embedding model: text-embedding-3-small..."
    try {
        az cognitiveservices account deployment create `
            --name $OpenAIAccountName `
            --resource-group $ResourceGroup `
            --deployment-name "text-embedding-3-small" `
            --model-name "text-embedding-3-small" `
            --model-version "1" `
            --model-format "OpenAI" `
            --sku-capacity 1 `
            --sku-name "GlobalStandard" `
            --output none 2>$null
    }
    catch {
        Write-Warning "Could not deploy embedding model - semantic memory search will use keyword fallback"
    }

    # Auto-deploy image generation model
    Write-Info "Deploying image model: gpt-image-1..."
    try {
        az cognitiveservices account deployment create `
            --name $OpenAIAccountName `
            --resource-group $ResourceGroup `
            --deployment-name "gpt-image-1" `
            --model-name "gpt-image-1" `
            --model-version "1" `
            --model-format "OpenAI" `
            --sku-capacity 1 `
            --sku-name "Standard" `
            --output none 2>$null
    }
    catch {
        Write-Warning "Could not deploy gpt-image-1 - image generation will not be available"
        Write-Host "  Model may not be available in your region yet. You can deploy manually later." -ForegroundColor DarkGray
    }
    # Write env var if deployment exists
    $imgDeploy = az cognitiveservices account deployment show `
        --name $OpenAIAccountName `
        --resource-group $ResourceGroup `
        --deployment-name "gpt-image-1" 2>$null
    if ($imgDeploy) {
        Update-EnvFile "AZURE_OPENAI_IMAGE_DEPLOYMENT" "gpt-image-1"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Deploy Azure AI Services
# ─────────────────────────────────────────────────────────────────────────────

if ($DeployAI) {
    Write-Header "Deploying Azure AI Services"

    $AIAccountName = "foundry-tui-ai-$(Get-Random)"

    # Check for existing resource
    $existingAI = az cognitiveservices account list `
        --resource-group $ResourceGroup `
        --query "[?kind=='AIServices'].name" -o tsv 2>$null | Select-Object -First 1

    if ($existingAI) {
        Write-Info "Using existing Azure AI Services resource: $existingAI"
        $AIAccountName = $existingAI
    }
    else {
        Write-Info "Creating Azure AI Services resource..."
        try {
            az cognitiveservices account create `
                --name $AIAccountName `
                --resource-group $ResourceGroup `
                --location $Location `
                --kind "AIServices" `
                --sku "S0" `
                --output none
        }
        catch {
            Write-Warning "Could not create AIServices - trying CognitiveServices"
            az cognitiveservices account create `
                --name $AIAccountName `
                --resource-group $ResourceGroup `
                --location $Location `
                --kind "CognitiveServices" `
                --sku "S0" `
                --output none
        }
        Write-Success "Azure AI Services resource created"
    }

    # Get endpoint and key
    $AIEndpoint = az cognitiveservices account show `
        --name $AIAccountName `
        --resource-group $ResourceGroup `
        --query "properties.endpoint" -o tsv

    $AIKey = az cognitiveservices account keys list `
        --name $AIAccountName `
        --resource-group $ResourceGroup `
        --query "key1" -o tsv

    Update-EnvFile "AZURE_AI_ENDPOINT" $AIEndpoint
    Update-EnvFile "AZURE_AI_API_KEY" $AIKey

    Write-Success "Azure AI Services configured"

    Write-Warning "Note: DeepSeek, Grok, and other marketplace models require"
    Write-Warning "deployment through Azure AI Foundry portal."
    Write-Dim "  Visit: https://ai.azure.com"
}

}  # end of -OnlySearch skip

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Web Search (Optional - for tool calling)
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Header "Web Search for Tool Calling"
Write-Host ""
Write-Host "Foundry TUI supports tool calling with web search via Tavily."
Write-Host "Models that support tool calling can search the web during conversations."
Write-Host ""
Write-Dim "Get a free API key at: https://tavily.com (1,000 searches/month free)"
Write-Host ""

$DeploySearch = $false
# In -OnlySearch mode, skip the confirmation — that's the whole point
if ($OnlySearch -or (Confirm-Action "Would you like to enable web search for tool calling?")) {
    $DeploySearch = $true

    Set-Location $ProjectRoot
    Backup-EnvFile

    Write-Host ""
    Write-Host "Enter your Tavily API key (starts with " -NoNewline
    Write-Host "tvly-" -ForegroundColor Cyan -NoNewline
    Write-Host "):"
    Write-Dim "Get one free at: https://tavily.com"
    $TavilyKey = Read-Host ">"

    if ([string]::IsNullOrWhiteSpace($TavilyKey)) {
        Write-Warning "No API key entered — skipping web search"
        $DeploySearch = $false
    } else {
        Update-EnvFile "TAVILY_API_KEY" $TavilyKey
        Write-Success "Tavily web search configured for tool calling"
    }
} else {
    Write-Dim "Skipping web search — tool calling will work without it"
}

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

Write-Header "Setup Complete!"

Write-Host ""
Write-Host "Your .env file has been configured with:" -ForegroundColor Green
Write-Host ""
if ($DeployOpenAI) {
    Write-Host "  • Azure OpenAI endpoint and key"
    Write-Host "  • Models: $($OpenAIModels -join ', ')"
}
if ($DeployAI) {
    Write-Host "  • Azure AI Services endpoint and key"
    Write-Host "  • Models: $($AIModels -join ', ') (deploy via portal)"
}
if ($DeploySearch) {
    Write-Host "  • Tavily API key (web search tool calling enabled)"
}
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Run the app:"
Write-Host "     uv run foundry-tui" -ForegroundColor Cyan
Write-Host ""
if ($DeployAI) {
    Write-Host "  2. Deploy marketplace models via Azure AI Foundry:"
    Write-Host "     https://ai.azure.com" -ForegroundColor Cyan
    Write-Host ""
}
Write-Host "  3. To clean up resources later, run:"
Write-Host "     .\scripts\teardown.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Dim "Resources created in: $ResourceGroup"
Write-Dim "Estimated cost: Pay-per-token only (no base cost)"
Write-Host ""
