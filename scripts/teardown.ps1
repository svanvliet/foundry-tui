# Foundry TUI - Azure Teardown Script (PowerShell)
# Safely remove Azure resources created by setup.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Source common functions
. "$ScriptDir\lib\common.ps1"

# ─────────────────────────────────────────────────────────────────────────────
# Welcome
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Red
Write-Host "║           Foundry TUI - Resource Cleanup                     ║" -ForegroundColor Red
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Red
Write-Host ""
Write-Warning "This script will DELETE Azure resources."
Write-Warning "This action cannot be undone!"
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# Prerequisites Check
# ─────────────────────────────────────────────────────────────────────────────

if (-not (Test-Command "az")) {
    Write-Error "'az' is required but not installed."
    exit 1
}

if (-not (Test-AzureAuth)) {
    Write-Host ""
    Write-Info "Please log in to Azure CLI:"
    az login
}

# ─────────────────────────────────────────────────────────────────────────────
# Load configuration from .env
# ─────────────────────────────────────────────────────────────────────────────

Set-Location $ProjectRoot

$ResourceGroup = $null
if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match 'AZURE_RESOURCE_GROUP=(.+)') {
        $ResourceGroup = $Matches[1].Trim()
    }
}

if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
    $ResourceGroup = Read-Host "? Enter resource group name to delete"
}

if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
    Write-Error "No resource group specified."
    exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# Show resources to be deleted
# ─────────────────────────────────────────────────────────────────────────────

Write-Header "Resources to Delete"

# Check if resource group exists
$rgExists = az group show --name $ResourceGroup 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Resource group '$ResourceGroup' not found."
    exit 1
}

Write-Host ""
Write-Host "Resource Group: " -NoNewline
Write-Host $ResourceGroup -ForegroundColor White
Write-Host ""

Write-Info "Resources in this group:"
az resource list --resource-group $ResourceGroup --query "[].{Name:name, Type:type}" -o table

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# Confirmation
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "WARNING: This will delete the entire resource group and ALL resources inside it." -ForegroundColor Red
Write-Host ""

$confirmName = Read-Host "? Type the resource group name to confirm deletion"

if ($confirmName -ne $ResourceGroup) {
    Write-Error "Names don't match. Deletion cancelled."
    exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# Delete resources
# ─────────────────────────────────────────────────────────────────────────────

Write-Header "Deleting Resources"

Write-Info "Deleting resource group '$ResourceGroup'..."
Write-Dim "This may take a few minutes..."

az group delete --name $ResourceGroup --yes --no-wait

Write-Success "Resource group deletion initiated"
Write-Dim "Deletion is running in the background."

# ─────────────────────────────────────────────────────────────────────────────
# Clean up .env (optional)
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
if (Confirm-Action "Clear Azure credentials from .env file?") {
    if (Test-Path ".env") {
        $content = Get-Content ".env" -Raw
        $content = $content -replace '(?m)^AZURE_OPENAI_', '#AZURE_OPENAI_'
        $content = $content -replace '(?m)^AZURE_AI_', '#AZURE_AI_'
        $content = $content -replace '(?m)^SERVERLESS_', '#SERVERLESS_'
        Set-Content -Path ".env" -Value $content.TrimEnd()
        Write-Success "Credentials commented out in .env"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

Write-Header "Cleanup Complete"

Write-Host ""
Write-Host "The resource group is being deleted in the background."
Write-Host ""
Write-Host "To verify deletion:"
Write-Host "  az group show --name $ResourceGroup" -ForegroundColor Cyan
Write-Host ""
Write-Host "To re-deploy resources:"
Write-Host "  .\scripts\setup.ps1" -ForegroundColor Cyan
Write-Host ""
