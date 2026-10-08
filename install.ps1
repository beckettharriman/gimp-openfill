# Stable Boy - generative fill for GIMP 3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Installs the plug-in into the per-user GIMP 3 profile on Windows and writes a
# default config if none exists. Run from the repository root:
#
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-GimpVersion 3.2] [-ComfyDir C:\AI\ComfyUI\ComfyUI_windows_portable] [-Link]
#
# -Link creates a directory junction to the repo instead of copying (handy for development).

[CmdletBinding()]
param(
    [string]$GimpVersion = "",
    [string]$ComfyDir = "",
    [switch]$Link,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $repo "gimp-stable-boy"
$name = "gimp-stable-boy"

$base = Join-Path $env:APPDATA "GIMP"
if (-not $GimpVersion) {
    $candidates = Get-ChildItem -Path $base -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^3\.\d+$' } | Sort-Object { [version]$_.Name } -Descending
    if (-not $candidates) {
        Write-Error "No GIMP 3.x profile found under $base. Start GIMP once, then re-run."
    }
    $GimpVersion = $candidates[0].Name
}
$profileDir = Join-Path $base $GimpVersion
$pluginsDir = Join-Path $profileDir "plug-ins"
$target = Join-Path $pluginsDir $name

if (Get-Process -Name "gimp-3.*" -ErrorAction SilentlyContinue) {
    Write-Warning "GIMP is running. The plug-in registers on the next GIMP start."
}

if ($Uninstall) {
    if (Test-Path $target) {
        $item = Get-Item $target -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $item.Delete() } else { Remove-Item $target -Recurse -Force }
        Write-Host "Removed $target"
    } else {
        Write-Host "Nothing installed at $target"
    }
    exit 0
}

New-Item -ItemType Directory -Force $pluginsDir | Out-Null
if (Test-Path $target) {
    $item = Get-Item $target -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $item.Delete() } else { Remove-Item $target -Recurse -Force }
}
if ($Link) {
    New-Item -ItemType Junction -Path $target -Target $source | Out-Null
    Write-Host "Linked $target -> $source"
} else {
    Copy-Item -Path $source -Destination $target -Recurse -Force
    Get-ChildItem $target -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
    Write-Host "Copied plug-in to $target"
}

# Default config (only if missing).
$configDir = Join-Path $profileDir "stable-boy"
$configFile = Join-Path $configDir "config.json"
New-Item -ItemType Directory -Force $configDir | Out-Null
if (-not (Test-Path $configFile)) {
    if (-not $ComfyDir) { $ComfyDir = "C:\AI\ComfyUI\ComfyUI_windows_portable" }
    $config = [ordered]@{
        backend = "comfyui"
        comfy_dir = $ComfyDir
        url = "http://127.0.0.1:8188"
        autostart = $true
        idle_timeout_minutes = 20
        checkpoint = "sd-v1-5-inpainting.ckpt"
        sdxl_checkpoint = "sd_xl_base_1.0.safetensors"
        fooocus_head = "fooocus_inpaint_head.pth"
        fooocus_patch = "inpaint_v26.fooocus.patch"
        quality = "fast"
    }
    # UTF-8 without BOM (Set-Content -Encoding UTF8 adds one on Windows PowerShell).
    [IO.File]::WriteAllText($configFile, (($config | ConvertTo-Json) + "`n"), (New-Object Text.UTF8Encoding $false))
    Write-Host "Wrote default config to $configFile"
} else {
    Write-Host "Keeping existing config at $configFile"
}

if ($ComfyDir -and -not (Test-Path (Join-Path $ComfyDir "ComfyUI\main.py"))) {
    Write-Warning "ComfyUI not found at $ComfyDir. See docs/models.md for the backend setup."
}
Write-Host "Done. Restart GIMP and look for Filters > AI > Generative Fill..."
