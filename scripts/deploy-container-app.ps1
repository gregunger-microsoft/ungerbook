# deploy-container-app.ps1
# Deploys Ungerbook to Azure Container Apps from ACR image
# Usage: .\scripts\deploy-container-app.ps1

$ErrorActionPreference = "Stop"

# --- Configuration ---
$RESOURCE_GROUP    = "GREGU"
$LOCATION          = "eastus"
$ACR_NAME          = "gregsacr1"
$IMAGE             = "gregsacr1.azurecr.io/ungerbook:latest"
$APP_NAME          = "ungerbook"
$ENV_NAME          = "ungerbook-env"

# --- Read .env file for app settings ---
$envFile = Join-Path $PSScriptRoot ".." ".env"
if (-not (Test-Path $envFile)) {
    Write-Error ".env file not found at $envFile"
    exit 1
}

$envVars = @{}
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line -split "=", 2
        $envVars[$parts[0].Trim()] = $parts[1].Trim()
    }
}

Write-Host "=== Ungerbook Azure Container Apps Deployment ===" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: Ensure containerapp extension ---
Write-Host "[1/5] Ensuring Azure CLI containerapp extension..." -ForegroundColor Yellow
az extension add --name containerapp --upgrade --yes 2>$null

# --- Step 2: Register required providers ---
Write-Host "[2/5] Registering resource providers..." -ForegroundColor Yellow
az provider register --namespace Microsoft.App --wait 2>$null
az provider register --namespace Microsoft.OperationalInsights --wait 2>$null

# --- Step 3: Create Container Apps Environment ---
Write-Host "[3/5] Creating Container Apps environment: $ENV_NAME..." -ForegroundColor Yellow
$envExists = az containerapp env show --name $ENV_NAME --resource-group $RESOURCE_GROUP 2>$null
if (-not $envExists) {
    az containerapp env create `
        --name $ENV_NAME `
        --resource-group $RESOURCE_GROUP `
        --location $LOCATION
    Write-Host "  Environment created." -ForegroundColor Green
} else {
    Write-Host "  Environment already exists." -ForegroundColor Green
}

# --- Step 4: Create or update Container App ---
Write-Host "[4/5] Deploying container app: $APP_NAME..." -ForegroundColor Yellow

$appExists = az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP 2>$null

$envArgs = @(
    "AZURE_OPENAI_ENDPOINT=$($envVars['AZURE_OPENAI_ENDPOINT'])"
    "AZURE_OPENAI_DEPLOYMENT=$($envVars['AZURE_OPENAI_DEPLOYMENT'])"
    "AZURE_OPENAI_API_VERSION=$($envVars['AZURE_OPENAI_API_VERSION'])"
    "AZURE_OPENAI_API_KEY=$($envVars['AZURE_OPENAI_API_KEY'])"
    "CONVERSATION_MODE=$($envVars['CONVERSATION_MODE'])"
    "AI_RESPONSE_DELAY_SECONDS=$($envVars['AI_RESPONSE_DELAY_SECONDS'])"
    "MAX_AI_RESPONSES_PER_ROUND=$($envVars['MAX_AI_RESPONSES_PER_ROUND'])"
    "MAX_CONTEXT_MESSAGES=$($envVars['MAX_CONTEXT_MESSAGES'])"
    "ENABLE_STREAMING=$($envVars['ENABLE_STREAMING'])"
    "MEMORY_SUMMARIZATION_INTERVAL=$($envVars['MEMORY_SUMMARIZATION_INTERVAL'])"
    "DATABASE_PATH=$($envVars['DATABASE_PATH'])"
    "PERSONALITIES_FILE=$($envVars['PERSONALITIES_FILE'])"
    "SESSION_EXPORT_DIR=$($envVars['SESSION_EXPORT_DIR'])"
)

if (-not $appExists) {
    az containerapp create `
        --name $APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --environment $ENV_NAME `
        --image $IMAGE `
        --registry-server "$ACR_NAME.azurecr.io" `
        --target-port 8000 `
        --ingress external `
        --transport http `
        --min-replicas 1 `
        --max-replicas 1 `
        --cpu 0.5 `
        --memory 1.0Gi `
        --env-vars @envArgs
    Write-Host "  Container app created." -ForegroundColor Green
} else {
    az containerapp update `
        --name $APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --image $IMAGE `
        --set-env-vars @envArgs
    Write-Host "  Container app updated." -ForegroundColor Green
}

# --- Step 5: Get the URL ---
Write-Host "[5/5] Retrieving app URL..." -ForegroundColor Yellow
$fqdn = az containerapp show `
    --name $APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "properties.configuration.ingress.fqdn" `
    --output tsv

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "URL: https://$fqdn" -ForegroundColor Cyan
Write-Host ""
