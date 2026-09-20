param(
    [switch]$ExportEnv
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Crie o ambiente virtual primeiro: .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
& $python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Não foi possível instalar as dependências do empacotamento." }

$iconPath = Join-Path $projectRoot "steam_analytics\static\assets\favicon.ico"
& $python (Join-Path $projectRoot "scripts\png_to_ico.py") (Join-Path $projectRoot "steam_analytics\static\assets\favicon.png") $iconPath
if ($LASTEXITCODE -ne 0) { throw "Não foi possível preparar o ícone do executável." }

& $python -m PyInstaller --clean --noconfirm steam_analytics.spec
if ($LASTEXITCODE -ne 0) { throw "O empacotamento falhou." }

$buildDir = Join-Path $projectRoot "dist\SteamAchievementAnalytics"
if ($ExportEnv) {
    $envFile = Join-Path $projectRoot ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        throw "A flag -ExportEnv foi usada, mas o arquivo .env não existe na raiz do projeto."
    }
    Copy-Item -LiteralPath $envFile -Destination (Join-Path $buildDir ".env") -Force
    Write-Host "Arquivo .env copiado para a pasta da build."
}

Write-Host "Executável gerado em dist\SteamAchievementAnalytics\SteamAchievementAnalytics.exe"
