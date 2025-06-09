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
    [Parameter(Position = 0)]
    [string]$ImageName = "airerik/zeon-refiller",

    [Parameter(Position = 1)]
    [Alias("Version")]
    [string]$Tag
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

Write-Host "Image tags: ${ImageName}:$Tag  and  ${ImageName}:latest"

# ---------- 3. Собираем и пушим образ --------------------------------
Write-Host "Running: docker buildx build ..."

$buildCmd = @(
    "docker", "buildx", "build",
    "--builder",  "desktop-linux",
    "--platform", "linux/amd64",
    "--file",     "`"$Dockerfile`"",     # экранируем кавычками на случай пробелов
    "--tag",      "${ImageName}:$Tag",
    "--tag",      "${ImageName}:latest",
    "--push",
    "--progress", "plain",
    "`"$RepoRoot`""                      # контекст = весь репозиторий
) -join " "

Write-Host $buildCmd
iex $buildCmd

# ---------- 4. Чистим buildx cache -----------------------------------
Write-Host "Cleaning buildx cache ..."
docker buildx prune -f | Out-Null

Write-Host "=== Done. Image ${ImageName}:$Tag pushed to Docker Hub ==="
