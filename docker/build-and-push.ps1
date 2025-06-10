# File: docker\build-and-push.ps1
<#
.SYNOPSIS
    Build & push a multi-stage Docker image for the Zeon-Refiller project.

.DESCRIPTION
    * Reads the version from pyproject.toml (unless -Tag/-Version is provided).
    * Builds the image via BuildKit/buildx using docker/Dockerfile.
    * Tags it as <ImageName>:<Tag> and <ImageName>:latest, pushes to Docker Hub,
        then removes the local buildx cache.

.PARAMETER ImageName
    The full repository name on Docker Hub (default: airerik/zeon-refiller).

.PARAMETER Tag
    Image tag (version). If omitted, read from pyproject.toml.
    Alias: -Version

.PARAMETER Registry
    Registry URL (default: registry.project.client.loc).

.PARAMETER LocalOnly
    If specified, only build locally without pushing.

.EXAMPLE
    PS> .\docker\build-and-push.ps1
    Builds and pushes registry.project.client.loc/zeon/refiller:<version_from_pyproject> and :latest.

.EXAMPLE
    PS> .\docker\build-and-push.ps1 -ImageName registry.project.client.loc/myproject/refiller -Tag v2.0.1
    Builds and pushes custom image with specific tag.

.EXAMPLE
    PS> .\docker\build-and-push.ps1 -Registry my.registry.com -LocalOnly
    Builds locally without pushing.
#>

[CmdletBinding()]
param (
    [string]$ImageName = "registry.project.client.loc/zeon/refiller",
    [Alias("Version")]
    [string]$Tag,
    [string]$Registry = "registry.project.client.loc",
    [switch]$LocalOnly,
    # необязательный builder
    [string]$Builder
)

# Enable BuildKit
$ErrorActionPreference = "Stop"
$Env:DOCKER_BUILDKIT = "1"

Write-Host "Checking Docker connectivity..." -ForegroundColor Yellow
try {
    & docker version --format "{{.Server.Version}}" | Out-Null
    Write-Host "✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Error "Docker is not running or not accessible. Please start Docker Desktop."
    exit 1
}

# ---------- 1. Раскладка путей относительно скрипта -----------------
$ScriptDir   = $PSScriptRoot                       # …\docker
$RepoRoot    = (Resolve-Path "$ScriptDir\..").Path # корень проекта
$pyproject   = Join-Path $RepoRoot  "pyproject.toml"
$Dockerfile  = Join-Path $ScriptDir "Dockerfile"

if (-not (Test-Path $PyProject))  { throw "pyproject.toml not found: $PyProject" }
if (-not (Test-Path $Dockerfile)) { throw "Dockerfile not found:  $Dockerfile" }

# ---------- 2. Определяем тег (version) ------------------------------
if (-not $Tag) {
    Write-Host "Reading version from pyproject.toml ..." -ForegroundColor Yellow
    $content = Get-Content -Raw -Path $PyProject
    $m = [regex]::Match($content, 'version\s*=\s*"(?<ver>[^"]+)"')
    if (-not $m.Success) { throw "Field 'version' not found in pyproject.toml" }
    $Tag = $m.Groups['ver'].Value
    Write-Host "✓ Found version: $Tag" -ForegroundColor Green
}

# ---------- 3. Проверка доступности registry -------------------------
if (-not $LocalOnly) {
    Write-Host "Checking registry connectivity..." -ForegroundColor Yellow
    try {
        # Пытаемся получить каталог репозиториев
        $catalogUrl = "https://$Registry/v2/_catalog"
        Write-Host "Testing registry at: $catalogUrl" -ForegroundColor Cyan

        # Простая проверка доступности (может потребоваться аутентификация)
        $response = Invoke-WebRequest -Uri $catalogUrl -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ Registry is accessible" -ForegroundColor Green
        } else {
            Write-Warning "Registry responded with status: $($response.StatusCode)"
        }
    } catch {
        Write-Warning "Registry check failed: $($_.Exception.Message)"
        Write-Host "Will try to push anyway..." -ForegroundColor Yellow
    }
}

# ---------- 4. Информативная часть -----------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host "Build & Push Docker Image using BuildKit"
Write-Host "Project root:   $RepoRoot"
Write-Host "Dockerfile:     $Dockerfile"
Write-Host "Image to push:  ${ImageName}:$Tag"
Write-Host "Additional tag: ${ImageName}:latest"
if ($LocalOnly) {
    Write-Host "Mode:           LOCAL BUILD ONLY (no push)" -ForegroundColor Yellow
} else {
    Write-Host "Mode:           BUILD AND PUSH" -ForegroundColor Green
}
if ($Builder) { Write-Host "Builder:        $Builder" }
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""


# ---------- 5. Собираем и пушим образ --------------------------------
$dockerArgs = @(
    "buildx", "build",
    "--platform", "linux/amd64",
    "--tag", "${ImageName}:$Tag",
    "--tag", "${ImageName}:latest",
    "--file", "$Dockerfile"
)

if (-not $LocalOnly) {
    $dockerArgs += "--push"
} else {
    $dockerArgs += "--load"  # загружаем в локальный Docker daemon
}

if ($Builder) {
    $dockerArgs += @("--builder", "$Builder")
}

$dockerArgs += "$RepoRoot"

Write-Host "Running command:" -ForegroundColor Yellow
Write-Host "  docker $($dockerArgs -join ' ')" -ForegroundColor Cyan
Write-Host ""

# ---------- 6. Запуск сборки -----------------------------------------
& docker @dockerArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error "`nBuild or push failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# ---------- 7. Результат ---------------------------------------------
Write-Host ""
if ($LocalOnly) {
    Write-Host "✓ Image has been built successfully: ${ImageName}:$Tag" -ForegroundColor Green
    Write-Host "Available locally in Docker daemon" -ForegroundColor Green
} else {
    Write-Host "✓ Image has been built and pushed successfully!" -ForegroundColor Green
    Write-Host "  ${ImageName}:$Tag" -ForegroundColor Cyan
    Write-Host "  ${ImageName}:latest" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Registry catalog: https://$Registry/v2/_catalog" -ForegroundColor Blue
}

exit 0
