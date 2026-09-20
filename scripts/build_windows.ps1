param(
    [switch]$ExportEnv,
    [switch]$Launch
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Crie o ambiente virtual primeiro: .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
& $python -m pip install -r requirements.txt pyinstaller Pillow
if ($LASTEXITCODE -ne 0) { throw "Não foi possível instalar as dependências do empacotamento." }

$iconPath = Join-Path $projectRoot "steam_analytics\static\assets\favicon.ico"
& $python (Join-Path $projectRoot "scripts\png_to_ico.py") (Join-Path $projectRoot "steam_analytics\static\assets\logo.png") $iconPath
if ($LASTEXITCODE -ne 0) { throw "Não foi possível preparar o ícone do executável." }

& $python -m PyInstaller --clean --noconfirm steam_analytics.spec
if ($LASTEXITCODE -ne 0) { throw "O empacotamento falhou." }

$buildDir = Join-Path $projectRoot "dist\SteamAchievementAnalytics"
$intermediateExe = Join-Path $projectRoot "dist\SAA.exe"
if (Test-Path -LiteralPath $intermediateExe) {
    Remove-Item -LiteralPath $intermediateExe -Force
    Write-Host "Executável intermediário removido de dist."
}

if ($ExportEnv) {
    $envFile = Join-Path $projectRoot ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        throw "A flag -ExportEnv foi usada, mas o arquivo .env não existe na raiz do projeto."
    }
    Copy-Item -LiteralPath $envFile -Destination (Join-Path $buildDir ".env") -Force
    Write-Host "Arquivo .env copiado para a pasta da build."
} else {
    $exampleEnv = Join-Path $projectRoot ".env.example"
    if (-not (Test-Path -LiteralPath $exampleEnv)) {
        throw "O arquivo .env.example não existe na raiz do projeto."
    }
    Copy-Item -LiteralPath $exampleEnv -Destination (Join-Path $buildDir ".env") -Force
    Write-Host "Arquivo .env.example copiado como .env na pasta da build."
}

$packageReadme = Join-Path $projectRoot "packaging\Leia-me.md"
if (-not (Test-Path -LiteralPath $packageReadme)) {
    throw "O arquivo packaging\Leia-me.md não existe."
}
Copy-Item -LiteralPath $packageReadme -Destination (Join-Path $buildDir "Leia-me.md") -Force

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archivePath = Join-Path $projectRoot "dist\SteamAchievementAnalytics.zip"
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $buildDir,
    $archivePath,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

Write-Host "Executável gerado em dist\SteamAchievementAnalytics\SAA.exe"
Write-Host "Pacote ZIP gerado em dist\SteamAchievementAnalytics.zip"

if ($Launch) {
    Start-Process -FilePath (Join-Path $buildDir "SAA.exe") -WorkingDirectory $buildDir
    Write-Host "Aplicação iniciada para teste."
}
