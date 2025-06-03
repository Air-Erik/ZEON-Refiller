# File: docker\build-and-push.ps1
<#
.SYNOPSIS
    Builds a Docker image using BuildKit and immediately pushes it to Docker Hub.

.DESCRIPTION
    Run this script from any folder; it locates the "docker" directory relative to itself.
    It enables BuildKit, builds the image using the Dockerfile in the "docker" folder,
    and pushes it to the specified Docker Hub repository without storing it locally.

.PARAMETER ImageName
    Full Docker Hub image name, e.g., "username/zeon-refiller".

.PARAMETER Tag
    Tag for the image. Default is "latest".

.EXAMPLE
    PS> .\docker\build-and-push.ps1 -ImageName "myuser/zeon-refiller" -Tag "v1.0.0"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ImageName,

    [Parameter(Mandatory = $false)]
    [string]$Tag = "latest"
)

# Enable BuildKit
$Env:DOCKER_BUILDKIT = "1"

# Determine script directory (where this .ps1 lives)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Project root is the parent of the docker folder
$dockerDir   = Resolve-Path $scriptDir
$projectRoot = Resolve-Path "$dockerDir\.."

# Path to Dockerfile (in the docker folder)
$dockerfilePath = Join-Path $dockerDir "Dockerfile"

Write-Host "============================================================"
Write-Host "Build & Push Docker Image using BuildKit"
Write-Host "Project root:   $projectRoot"
Write-Host "Dockerfile:     $dockerfilePath"
Write-Host "Image to push:  $ImageName`:$Tag"
Write-Host "============================================================`n"

# Check that Dockerfile exists
if (-not (Test-Path $dockerfilePath)) {
    Write-Error "Dockerfile not found at: $dockerfilePath"
    exit 1
}

# Build command as an array
$dockerArgs = @(
    "buildx", "build",
    "--tag", "$ImageName`:$Tag",
    "--file", "$dockerfilePath",
    "--push",
    "$projectRoot"
)

Write-Host "Running command:"
Write-Host "  docker $($dockerArgs -join ' ')"`n

# Invoke Docker directly so output streams to console
& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "`nBuild or push failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

Write-Host "`nImage has been built and pushed successfully: $ImageName`:$Tag" -ForegroundColor Green
exit 0
