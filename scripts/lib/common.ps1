# Common functions for Foundry TUI setup scripts (PowerShell)

# Print functions
function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Blue
    Write-Host ("─" * 50) -ForegroundColor DarkGray
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Write-Warning {
    param([string]$Message)
    Write-Host "! " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Info {
    param([string]$Message)
    Write-Host "→ " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

function Write-Dim {
    param([string]$Message)
    Write-Host $Message -ForegroundColor DarkGray
}

# Prompt for confirmation
function Confirm-Action {
    param([string]$Prompt = "Continue?")
    $response = Read-Host "? $Prompt [y/N]"
    return $response -match '^[Yy]$'
}

# Prompt with default value
function Read-HostWithDefault {
    param(
        [string]$Prompt,
        [string]$Default
    )
    $response = Read-Host "? $Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($response)) {
        return $Default
    }
    return $response
}

# Check if command exists
function Test-Command {
    param([string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

# Check Azure CLI authentication
function Test-AzureAuth {
    try {
        $null = az account show 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

# Get current Azure subscription
function Get-AzureSubscription {
    $result = az account show --query "{name:name, id:id}" -o json 2>$null | ConvertFrom-Json
    return $result
}

# Update .env file
function Update-EnvFile {
    param(
        [string]$Key,
        [string]$Value,
        [string]$EnvFile = ".env"
    )

    # Create file if it doesn't exist
    if (-not (Test-Path $EnvFile)) {
        New-Item -ItemType File -Path $EnvFile -Force | Out-Null
    }

    $content = Get-Content $EnvFile -Raw -ErrorAction SilentlyContinue
    $pattern = "^$Key=.*$"

    if ($content -match $pattern) {
        # Update existing key
        $content = $content -replace "(?m)$pattern", "$Key=$Value"
        Set-Content -Path $EnvFile -Value $content.TrimEnd()
    }
    else {
        # Add new key
        Add-Content -Path $EnvFile -Value "$Key=$Value"
    }
}

# Backup .env file
function Backup-EnvFile {
    param([string]$EnvFile = ".env")

    if (Test-Path $EnvFile) {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        Copy-Item $EnvFile "$EnvFile.backup.$timestamp"
        Write-Dim "Backed up existing .env file"
    }
}
