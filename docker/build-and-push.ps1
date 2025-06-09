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

.EXAMPLE
    PS> .\docker\build-and-push.ps1
    Builds and pushes airerik/zeon-refiller:<version_from_pyproject> and :latest.

.EXAMPLE
    PS> .\docker\build-and-push.ps1 -ImageName myorg/refiller -Tag v2.0.1
    Builds and pushes myorg/refiller:v2.0.1 and :latest.
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $true)]
    [string]$ImageName,

    [Alias("Version")]
    [string]$Tag,

    # необязательный builder
    [string]$Builder
)

# Enable BuildKit
$ErrorActionPreference = "Stop"
$Env:DOCKER_BUILDKIT = "1"

# ---------- 1. Раскладка путей относительно скрипта -----------------
$ScriptDir   = $PSScriptRoot                       # …\docker
$RepoRoot    = (Resolve-Path "$ScriptDir\..").Path # корень проекта
$pyproject   = Join-Path $RepoRoot  "pyproject.toml"
$Dockerfile  = Join-Path $ScriptDir "Dockerfile"

if (-not (Test-Path $PyProject))  { throw "pyproject.toml not found: $PyProject" }
if (-not (Test-Path $Dockerfile)) { throw "Dockerfile not found:  $Dockerfile" }

# ---------- 2. Определяем тег (version) ------------------------------
if (-not $Tag) {
    Write-Host "Reading version from pyproject.toml ..."
    $content = Get-Content -Raw -Path $PyProject
    $m = [regex]::Match($content, 'version\s*=\s*"(?<ver>[^"]+)"')
    if (-not $m.Success) { throw "Field 'version' not found in pyproject.toml" }
    $Tag = $m.Groups['ver'].Value
}

# ---------- 3. Информативная часть -----------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host "Build & Push Docker Image using BuildKit"
Write-Host "Project root:   $RepoRoot"
Write-Host "Dockerfile:     $Dockerfile"
Write-Host "Image to push:  ${ImageName}:$Tag"
Write-Host "Additional tag: ${ImageName}:latest"
if ($Builder) { Write-Host "Builder:        $Builder" }
Write-Host "============================================================"
Write-Host ""

# ---------- 4. Собираем и пушим образ --------------------------------
$dockerArgs = @(
    "buildx", "build",
    "--platform", "linux/amd64",
    "--tag", "${ImageName}:$Tag",
    "--tag", "${ImageName}:latest",
    "--file", "$Dockerfile",
    "--push"
)
if ($Builder) { $dockerArgs += @("--builder", "$Builder") }
$dockerArgs += "$RepoRoot"

Write-Host "Running command:"
Write-Host "  docker $($dockerArgs -join ' ')"
Write-Host ""

# ---------- 5. Запуск сборки -----------------------------------------
& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "`nBuild or push failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# ---------- 4. Чистим buildx cache -----------------------------------
Write-Host ""
Write-Host "Image has been built and pushed successfully: ${ImageName}:$Tag" -ForegroundColor Green
exit 0
