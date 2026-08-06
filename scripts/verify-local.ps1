$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$backendPython = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $backendPython)) {
    $backendPython = "python"
}

function Assert-LastExitCode {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Write-Host "[1/4] Backend quality and full test suite"
Push-Location $backendRoot
try {
    & $backendPython -m ruff check .
    Assert-LastExitCode "Ruff lint"
    & $backendPython -m ruff format --check .
    Assert-LastExitCode "Ruff format"
    & $backendPython -m mypy src
    Assert-LastExitCode "mypy"
    & $backendPython -m pytest
    Assert-LastExitCode "Pytest"
}
finally {
    Pop-Location
}

Write-Host "[2/4] Frontend typecheck and tests"
Push-Location $frontendRoot
try {
    & npm run typecheck
    Assert-LastExitCode "Frontend typecheck"
    & npm run test -- --run
    Assert-LastExitCode "Frontend tests"
}
finally {
    Pop-Location
}

Write-Host "[3/4] Frontend production build"
Push-Location $frontendRoot
try {
    & npm run build
    Assert-LastExitCode "Frontend build"
}
finally {
    Pop-Location
}

Write-Host "[4/4] Docker Compose validation"
& docker compose -f (Join-Path $projectRoot "docker\docker-compose.yml") config --quiet
Assert-LastExitCode "Docker Compose validation"

Write-Host "Local verification passed."
