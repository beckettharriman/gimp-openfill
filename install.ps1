# OpenFill - generative fill for GIMP 3
# Copyright (C) 2022 Torben Giesselmann, (C) 2026 Beckett Harriman
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Installs the plug-in into the per-user GIMP 3 profile on Windows and writes a
# default config if none exists. Run from the repository root:
#
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-GimpVersion 3.2] [-ProfileDir <dir>]
#              [-ComfyDir C:\AI\ComfyUI\ComfyUI_windows_portable] [-Link]
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall [-RemoveConfig] [-ProfileDir <dir>]
#   powershell -ExecutionPolicy Bypass -File install.ps1 -ListModels | -Model <id> [-ComfyDir <dir>]
#
# -Link         creates a directory junction to the repo instead of copying (handy for development).
# -ProfileDir   the GIMP profile folder itself (default: $env:GIMP3_DIRECTORY, else the newest
#               %APPDATA%\GIMP\3.x). Use it to install into an isolated test profile.
# -Uninstall    removes the plug-in folder or junction. The settings folder (<profile>\openfill,
#               which holds config.json and the Hugging Face token) is kept unless -RemoveConfig.
# -Model        downloads a catalog model with curl and verifies its sha256. A gated model needs a
#               Hugging Face token: set $env:HF_TOKEN (preferred) or pass -HfToken.

[CmdletBinding()]
param(
    [string]$GimpVersion = "",
    [string]$ProfileDir = "",
    [string]$ComfyDir = "",
    [switch]$Link,
    [switch]$Uninstall,
    [switch]$RemoveConfig,
    [switch]$ListModels,
    [string]$Model = "",
    [string]$HfToken = ""
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $repo "gimp-openfill"
$name = "gimp-openfill"
$catalogPath = Join-Path $repo "models\catalog.json"
$defaultComfy = "C:\AI\ComfyUI\ComfyUI_windows_portable"

function Fail([string]$Message) {
    [Console]::Error.WriteLine("error: $Message")
    exit 1
}

function Get-Catalog {
    (Get-Content -Raw -Encoding UTF8 $catalogPath | ConvertFrom-Json).models
}

function Get-ModelsRoot([string]$Dir) {
    if (-not $Dir) { $Dir = $defaultComfy }
    if (Test-Path -LiteralPath (Join-Path $Dir "ComfyUI\models")) { return (Join-Path $Dir "ComfyUI\models") }
    return (Join-Path $Dir "models")
}

function Assert-SafeDest([string]$Dest) {
    # Catalog destinations are "<subfolder>/<file>" made of plain names only.
    foreach ($segment in ($Dest -split '[\\/]')) {
        if ($segment -notmatch '^[A-Za-z0-9_][A-Za-z0-9_.+-]*$' -or $segment -eq '..') {
            Fail "unsafe destination in the catalog: '$Dest'"
        }
    }
}

function Test-ModelInstalled($Entry, [string]$Root) {
    foreach ($f in $Entry.files) {
        $p = Join-Path $Root $f.dest
        if (-not (Test-Path -LiteralPath $p)) { return $false }
        if ($f.size -and (Get-Item -LiteralPath $p).Length -ne $f.size) { return $false }
    }
    return $true
}

function Remove-PluginTarget([string]$Path) {
    # A junction is removed as a link only; Remove-Item -Recurse on a junction can
    # delete the files of the repository it points to on Windows PowerShell 5.1.
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        $item.Delete()
        return "junction"
    }
    Remove-Item -LiteralPath $Path -Recurse -Force
    return "folder"
}

function Find-GimpExe {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\GIMP 3\bin"),
        (Join-Path $env:ProgramFiles "GIMP 3\bin")
    )
    foreach ($dir in $candidates) {
        if (Test-Path -LiteralPath $dir) {
            $exe = Get-ChildItem -LiteralPath $dir -Filter "gimp-3*.exe" -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -notmatch 'console' } | Select-Object -First 1
            if ($exe) { return $exe.FullName }
        }
    }
    return $null
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
    if (-not $HfToken) { $HfToken = $env:HF_TOKEN }
    $root = Get-ModelsRoot $ComfyDir
    $catalog = Get-Catalog
    $entry = $catalog | Where-Object { $_.id -eq $Model }
    if (-not $entry) { Fail "Unknown model id '$Model'. Use -ListModels." }
    $queue = @()
    foreach ($dep in $entry.requires_models) { $queue += ($catalog | Where-Object { $_.id -eq $dep }) }
    $queue += $entry
    foreach ($m in $queue) {
        Write-Host "== $($m.id): $($m.name)"
        Write-Host "   License: $($m.license.name) - $($m.license.url)"
        foreach ($f in $m.files) {
            Assert-SafeDest $f.dest
            if ($f.url -notmatch '^https://') { Fail "catalog URL is not https: $($f.url)" }
            $dest = Join-Path $root $f.dest
            New-Item -ItemType Directory -Force (Split-Path -Parent $dest) | Out-Null
            if ((Test-Path -LiteralPath $dest) -and (-not $f.size -or (Get-Item -LiteralPath $dest).Length -eq $f.size)) {
                Write-Host "   present  $($f.dest)"; continue
            }
            if ($f.optional -and (Test-Path -LiteralPath $dest)) { continue }
            $useToken = $false
            if ($f.gated -or $m.gated) {
                if (-not $HfToken) { Fail "$($f.dest) is gated. Accept the license at $($m.page) and set `$env:HF_TOKEN (huggingface.co/settings/tokens)." }
                $useToken = ([Uri]$f.url).Host -match '(^|\.)(huggingface\.co|hf\.co)$'
            }
            $part = "$dest.part"
            Write-Host "   download $($f.url)"
            if ($useToken) {
                # The header goes to curl on stdin, so the token never appears in the process list.
                # curl does not resend a custom Authorization header to another host after a redirect.
                "Authorization: Bearer $HfToken" | & curl.exe -sS -L -C - --retry 5 --retry-delay 5 --fail -H "@-" -o $part $f.url
            } else {
                & curl.exe -sS -L -C - --retry 5 --retry-delay 5 --fail -o $part $f.url
            }
            if ($LASTEXITCODE -ne 0) { Fail "download failed for $($f.url) (curl exit $LASTEXITCODE); the .part file is kept for resume" }
            if ($f.size -and (Get-Item -LiteralPath $part).Length -ne $f.size) {
                Remove-Item -LiteralPath $part -Force
                Fail "size mismatch for $($f.dest); the partial file was deleted, re-run to download again"
            }
            if ($f.sha256) {
                $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $part).Hash.ToLower()
                if ($hash -ne $f.sha256) { Remove-Item -LiteralPath $part -Force; Fail "sha256 mismatch for $($f.dest): $hash" }
                Write-Host "   sha256 ok"
            }
            Move-Item -Force -LiteralPath $part -Destination $dest
        }
        foreach ($n in $m.requires_nodes) {
            if ($n.repo -notmatch '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' -or
                $n.commit -notmatch '^[0-9a-f]{40}$' -or $n.folder -notmatch '^[A-Za-z0-9_][A-Za-z0-9_.+-]*$') {
                Fail "catalog node entry is not a pinned GitHub repository: $($n.repo) $($n.folder) $($n.commit)"
            }
            $nodes = Join-Path (Split-Path -Parent $root) "custom_nodes"
            $target = Join-Path $nodes $n.folder
            if (-not (Test-Path -LiteralPath $target)) {
                Write-Host "   git clone $($n.repo) @ $($n.commit)"
                & git clone --quiet -- $n.repo $target
                if ($LASTEXITCODE -ne 0) { Fail "git clone failed for $($n.repo)" }
                & git -C $target checkout --quiet $n.commit
                if ($LASTEXITCODE -ne 0) { Fail "git checkout $($n.commit) failed in $target" }
                $py = Join-Path (Split-Path -Parent (Split-Path -Parent $root)) "python_embeded\python.exe"
                if ((Test-Path -LiteralPath (Join-Path $target "requirements.txt")) -and (Test-Path -LiteralPath $py)) {
                    & $py -s -m pip install --no-warn-script-location -r (Join-Path $target "requirements.txt")
                    if ($LASTEXITCODE -ne 0) { Fail "pip install failed for $($n.folder)" }
                }
            }
        }
    }
    Write-Host "Done. Select the model in Filters > OpenFill > Generative Fill Settings > Models (Set active)."
    exit 0
}

# ---- locate the GIMP 3 profile ----
if (-not $ProfileDir -and $env:GIMP3_DIRECTORY) { $ProfileDir = $env:GIMP3_DIRECTORY }
if ($ProfileDir) {
    $profileDir = $ProfileDir
} else {
    $base = Join-Path $env:APPDATA "GIMP"
    if (-not $GimpVersion) {
        $candidates = @(Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^3\.\d+$' } | Sort-Object { [version]$_.Name } -Descending)
        if ($candidates.Count -eq 0) {
            if ($Uninstall) { Write-Host "No GIMP 3.x profile under $base; nothing to uninstall."; exit 0 }
            if (Find-GimpExe) {
                Fail "GIMP 3 is installed but has no profile under $base yet. Start GIMP once, close it, then re-run."
            }
            Fail "GIMP 3 does not seem to be installed (no profile under $base). Install GIMP 3 from https://www.gimp.org/downloads/, start it once, then re-run."
        }
        $GimpVersion = $candidates[0].Name
    }
    $profileDir = Join-Path $base $GimpVersion
}
$pluginsDir = Join-Path $profileDir "plug-ins"
$target = Join-Path $pluginsDir $name
$configDir = Join-Path $profileDir "openfill"
$configFile = Join-Path $configDir "config.json"
Write-Host "GIMP profile: $profileDir"

if (Get-Process -Name "gimp-3*" -ErrorAction SilentlyContinue) {
    Write-Warning "A GIMP process is running. Changes take effect the next time GIMP starts."
}

if ($Uninstall) {
    if (Test-Path -LiteralPath $target) {
        $kind = Remove-PluginTarget $target
        Write-Host "Removed plug-in $kind $target"
    } else {
        Write-Host "No plug-in installed at $target"
    }
    if ($RemoveConfig) {
        if (Test-Path -LiteralPath $configDir) {
            Remove-Item -LiteralPath $configDir -Recurse -Force
            Write-Host "Removed settings folder $configDir (config.json, logs, task queue)"
        }
    } elseif (Test-Path -LiteralPath $configDir) {
        Write-Host "Kept settings folder $configDir (holds config.json and the Hugging Face token; use -RemoveConfig to delete it)"
    }
    Write-Host "Done. Restart GIMP; the Filters > OpenFill entries are gone. Models in the ComfyUI folder are not touched."
    exit 0
}

if (-not (Test-Path -LiteralPath (Join-Path $source "$name.py"))) { Fail "plug-in source not found at $source" }
New-Item -ItemType Directory -Force $pluginsDir | Out-Null
if (Test-Path -LiteralPath $target) {
    $kind = Remove-PluginTarget $target
    Write-Host "Replacing the existing plug-in $kind at $target"
}
if ($Link) {
    New-Item -ItemType Junction -Path $target -Target $source | Out-Null
    Write-Host "Linked $target -> $source"
} else {
    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
    Get-ChildItem -LiteralPath $target -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
    New-Item -ItemType Directory -Force (Join-Path $target "models") | Out-Null
    Copy-Item -LiteralPath $catalogPath -Destination (Join-Path $target "models\catalog.json") -Force
    Write-Host "Copied plug-in (with models\catalog.json) to $target"
}

# Default config (only if missing).
New-Item -ItemType Directory -Force $configDir | Out-Null
if (-not (Test-Path -LiteralPath $configFile)) {
    if (-not $ComfyDir) { $ComfyDir = $defaultComfy }
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
    if (-not $ComfyDir) {
        try { $ComfyDir = (Get-Content -Raw -LiteralPath $configFile | ConvertFrom-Json).comfy_dir } catch { $ComfyDir = "" }
    }
}

if (-not (Find-GimpExe)) {
    Write-Warning "GIMP 3 was not found in the usual install folders. Install it from https://www.gimp.org/downloads/."
}
if ($ComfyDir -and -not (Test-Path -LiteralPath (Join-Path $ComfyDir "ComfyUI\main.py")) -and
        -not (Test-Path -LiteralPath (Join-Path $ComfyDir "main.py"))) {
    Write-Warning "ComfyUI not found at $ComfyDir. See docs/models.md for the backend setup."
}
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Restart GIMP (plug-ins are registered at start-up)."
Write-Host "  2. Open Filters > OpenFill > Generative Fill Settings... and check the ComfyUI folder."
Write-Host "  3. In the Models tab, download a model (SD 1.5 inpainting is the small default) and press Set active."
Write-Host "  4. Select an area of an image and run Filters > OpenFill > Generative Fill..."
Write-Host "To remove the plug-in later: install.ps1 -Uninstall (add -RemoveConfig to delete the settings too)."
