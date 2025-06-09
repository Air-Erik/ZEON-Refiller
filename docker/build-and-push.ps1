# File: docker\build-and-push.ps1
<#
.SYNOPSIS
    Build & push a multi-stage Docker image for the Zeon-Refiller project.

.DESCRIPTION
    • Читает версию из pyproject.toml (если не указан ­-Tag).
    • Собирает образ через BuildKit / buildx, используя docker/Dockerfile и
        корень репозитория как контекст.
    • Тегирует как <ImageName>:<Tag> и <ImageName>:latest, мгновенно пушит
        в Docker Hub и чистит локальный build-cache.

.PARAMETER ImageName
    Полное имя репозитория Docker Hub (например `airerik/zeon-refiller`).
    По умолчанию: `airerik/zeon-refiller`.

.PARAMETER Tag
    Тег образа (версия). Если опущен, извлекается из поля `version`
    в pyproject.toml.

.EXAMPLE
    PS> .\docker\build-and-push.ps1
    Соберёт и запушит airerik/zeon-refiller:<версия_из_pyproject> и :latest.

.EXAMPLE
    PS> .\docker\build-and-push.ps1 -ImageName myorg/refiller -Tag v2.0.1
    Соберёт и запушит myorg/refiller:v2.0.1 и :latest.
#>

[CmdletBinding()]
param (
    [Parameter(Position = 0)]
    [string]$ImageName = "airerik/zeon-refiller",

    [Parameter(Position = 1)]
    [string]$Tag
)

# Enable BuildKit
$ErrorActionPreference = "Stop"
$Env:DOCKER_BUILDKIT = "1"

Write-Host "🛠  Запуск сборочного скрипта Zeon-Refiller..." -ForegroundColor Cyan

# ---------- 1. Раскладка путей относительно скрипта -----------------
$ScriptDir   = $PSScriptRoot                       # …\docker
$RepoRoot    = (Resolve-Path "$ScriptDir\..").Path # корень проекта
$pyproject   = Join-Path $RepoRoot  "pyproject.toml"
$Dockerfile  = Join-Path $ScriptDir "Dockerfile"

if (-not (Test-Path $pyproject))  { throw "pyproject.toml не найден: $pyproject" }
if (-not (Test-Path $Dockerfile)) { throw "Dockerfile не найден:  $Dockerfile" }

# ---------- 2. Определяем тег (version) ------------------------------
if (-not $Tag) {
    Write-Host "🔍  Извлекаем версию из pyproject.toml..." -ForegroundColor Cyan
    $content = Get-Content -Raw -Path $pyproject
    $m = [regex]::Match($content, 'version\s*=\s*"(?<ver>[^"]+)"')
    if (-not $m.Success) { throw "Поле version не найдено в pyproject.toml" }
    $Tag = $m.Groups['ver'].Value
}

Write-Host "📦  Используем теги: $ImageName:$Tag  и  $ImageName:latest" `
    -ForegroundColor Green

# ---------- 3. Собираем и пушим образ --------------------------------
Write-Host "🐳  Запускаем docker buildx build..." -ForegroundColor Cyan

$buildCmd = @(
    "docker", "buildx", "build",
    "--builder",  "default",             # предполагаем существование builder 'default'
    "--platform", "linux/amd64",
    "--file",     "`"$Dockerfile`"",     # экранируем кавычками на случай пробелов
    "--tag",      "$ImageName:$Tag",
    "--tag",      "$ImageName:latest",
    "--push",
    "--progress", "plain",
    "`"$RepoRoot`""                      # контекст = весь репозиторий
) -join " "

Write-Host $buildCmd -ForegroundColor Yellow
iex $buildCmd                             # выполняем

# ---------- 4. Чистим buildx cache -----------------------------------
Write-Host "🧹  Очищаем buildx cache..." -ForegroundColor Cyan
docker buildx prune -f | Out-Null

Write-Host "✅  Готово! Образ $ImageName:$Tag опубликован в Docker Hub." `
    -ForegroundColor Green
