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
    [switch]$Uninstall,
    [switch]$ListModels,
    [string]$Model = "",
    [string]$HfToken = ""
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $repo "gimp-stable-boy"
$name = "gimp-stable-boy"
$catalogPath = Join-Path $repo "models\catalog.json"

function Get-Catalog {
    (Get-Content -Raw -Encoding UTF8 $catalogPath | ConvertFrom-Json).models
}

function Get-ModelsRoot {
    param([string]$Dir)
    if (-not $Dir) { $Dir = "C:\AI\ComfyUI\ComfyUI_windows_portable" }
    if (Test-Path (Join-Path $Dir "ComfyUI\models")) { return (Join-Path $Dir "ComfyUI\models") }
    return (Join-Path $Dir "models")
}

function Test-ModelInstalled {
    param($Entry, [string]$Root)
    foreach ($f in $Entry.files) {
        $p = Join-Path $Root $f.dest
        if (-not (Test-Path $p)) { return $false }
        if ($f.size -and (Get-Item $p).Length -ne $f.size) { return $false }
    }
    return $true
}

# ---- headless model management (same catalog as the Models tab) ----
if ($ListModels) {
    $root = Get-ModelsRoot $ComfyDir
    foreach ($e in Get-Catalog) {
        $state = if (Test-ModelInstalled $e $root) { "Installed" } elseif ($e.gated) { "Needs token" } else { "Available" }
        $gb = [math]::Round((($e.files | Measure-Object -Property size -Sum).Sum / 1GB), 2)
        "{0,-30} {1,-9} {2,-12} {3,7} GB  {4}  [{5}]" -f $e.id, $e.tier, $state, $gb, $e.license.name, $e.source_type
    }
    exit 0
}

if ($Model) {
    $root = Get-ModelsRoot $ComfyDir
    $catalog = Get-Catalog
    $entry = $catalog | Where-Object { $_.id -eq $Model }
    if (-not $entry) { Write-Error "Unknown model id '$Model'. Use -ListModels." }
    $queue = @()
    foreach ($dep in $entry.requires_models) { $queue += ($catalog | Where-Object { $_.id -eq $dep }) }
    $queue += $entry
    foreach ($m in $queue) {
        Write-Host "== $($m.id): $($m.name)"
        Write-Host "   License: $($m.license.name) - $($m.license.url)"
        foreach ($f in $m.files) {
            $dest = Join-Path $root $f.dest
            New-Item -ItemType Directory -Force (Split-Path -Parent $dest) | Out-Null
            if ((Test-Path $dest) -and (-not $f.size -or (Get-Item $dest).Length -eq $f.size)) {
                Write-Host "   present  $($f.dest)"; continue
            }
            if ($f.optional -and (Test-Path $dest)) { continue }
            $headers = @()
            if ($f.gated -or $m.gated) {
                if (-not $HfToken) { Write-Error "$($f.dest) is gated. Accept the license at $($m.page) and pass -HfToken hf_xxx (huggingface.co/settings/tokens)." }
                $headers = @("-H", "Authorization: Bearer $HfToken")
            }
            $part = "$dest.part"
            Write-Host "   download $($f.url)"
            & curl.exe -L -C - --retry 5 --retry-delay 5 --fail -o $part $f.url @headers
            if ($LASTEXITCODE -ne 0) { Write-Error "download failed for $($f.url) (curl exit $LASTEXITCODE); the .part file is kept for resume" }
            if ($f.size -and (Get-Item $part).Length -ne $f.size) { Write-Error "size mismatch for $($f.dest); re-run to resume" }
            if ($f.sha256) {
                $hash = (Get-FileHash -Algorithm SHA256 $part).Hash.ToLower()
                if ($hash -ne $f.sha256) { Remove-Item $part; Write-Error "sha256 mismatch for $($f.dest): $hash" }
                Write-Host "   sha256 ok"
            }
            Move-Item -Force $part $dest
        }
        foreach ($n in $m.requires_nodes) {
            $nodes = Join-Path (Split-Path -Parent $root) "custom_nodes"
            $target = Join-Path $nodes $n.folder
            if (-not (Test-Path $target)) {
                Write-Host "   git clone $($n.repo) @ $($n.commit)"
                git clone --quiet $n.repo $target
                git -C $target checkout --quiet $n.commit
                $py = Join-Path (Split-Path -Parent (Split-Path -Parent $root)) "python_embeded\python.exe"
                if ((Test-Path (Join-Path $target "requirements.txt")) -and (Test-Path $py)) {
                    & $py -s -m pip install --no-warn-script-location -r (Join-Path $target "requirements.txt")
                }
            }
        }
    }
    Write-Host "Done. Select the model in Filters > AI > Generative Fill Settings > Models (Set active)."
    exit 0
}

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
    New-Item -ItemType Directory -Force (Join-Path $target "models") | Out-Null
    Copy-Item $catalogPath (Join-Path $target "models\catalog.json") -Force
    Write-Host "Copied plug-in (with models\catalog.json) to $target"
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
