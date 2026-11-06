#Requires -Version 5.1
<#
.SYNOPSIS
Install MCP for Blender and optionally register it with Codex on Windows.
.EXAMPLE
.\Install-BlenderMCP.ps1 -BlenderPath 'D:\Apps\Blender\blender.exe'
.EXAMPLE
.\Install-BlenderMCP.ps1 -CheckOnly
#>
[CmdletBinding()]
param(
    [string]$BlenderPath,
    [switch]$SkipCodex,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Exe $($Arguments -join ' ')"
    }
}

function Backup-File {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $backup = "$Path.before-blender-mcp-$([guid]::NewGuid().ToString('N')).bak"
        Copy-Item -LiteralPath $Path -Destination $backup
        Write-Host "Backup: $backup"
    }
}

if (-not $BlenderPath) {
    $found = Get-Command blender.exe -ErrorAction SilentlyContinue
    if ($found) { $BlenderPath = $found.Source }
}
if (-not $BlenderPath) {
    throw "Specify -BlenderPath with the full path to blender.exe."
}
$BlenderPath = (Resolve-Path -LiteralPath $BlenderPath).Path
if (-not (Test-Path -LiteralPath $BlenderPath -PathType Leaf) -or
    [IO.Path]::GetFileName($BlenderPath) -ine 'blender.exe') {
    throw 'BlenderPath must point to blender.exe.'
}
if (-not $CheckOnly -and (Get-Process blender -ErrorAction SilentlyContinue)) {
    throw 'Save your work and close all Blender instances before running this script.'
}

$codex = Get-Command codex -ErrorAction SilentlyContinue
if (-not $SkipCodex -and -not $codex) {
    throw 'Codex CLI was not found. Install it first, or pass -SkipCodex.'
}

Invoke-Checked -Exe $BlenderPath -Arguments @('--version')
Write-Host "Blender: $BlenderPath"
Write-Host "Configure Codex: $(-not $SkipCodex)"
if ($CheckOnly) {
    Write-Host 'Preflight complete. No installation or configuration changes were made.'
    return
}

$uvxCommand = Get-Command uvx.exe -ErrorAction SilentlyContinue
$uvxPath = Join-Path $env:USERPROFILE '.local\bin\uvx.exe'
if ($uvxCommand) { $uvxPath = $uvxCommand.Source }
if (-not (Test-Path -LiteralPath $uvxPath -PathType Leaf)) {
    # Run the official uv installer with a process-only policy override.
    # This does not change the user's persistent PowerShell execution policy.
    $installer = Join-Path ([IO.Path]::GetTempPath()) ("install-uv-" + [guid]::NewGuid().ToString('N') + '.ps1')
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri 'https://astral.sh/uv/install.ps1' -UseBasicParsing -OutFile $installer
        Invoke-Checked -Exe 'powershell.exe' -Arguments @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $installer)
    }
    finally {
        if (Test-Path -LiteralPath $installer) { Remove-Item -LiteralPath $installer }
    }
}
if (-not (Test-Path -LiteralPath $uvxPath -PathType Leaf)) {
    throw 'uvx was not found after installation. Restart PowerShell and retry.'
}

# Ask this Blender instance for its actual user paths, including portable installs.
$probe = @'
import bpy, json
print('MCP_PATHS=' + json.dumps({'addons': bpy.utils.user_resource('SCRIPTS', path='addons'), 'config': bpy.utils.user_resource('CONFIG')}, ensure_ascii=True))
'@
$probeOutput = & $BlenderPath --background --python-exit-code 1 --python-expr $probe
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect Blender user directories.' }
$marker = @($probeOutput | Where-Object { $_ -like 'MCP_PATHS=*' })
if ($marker.Count -ne 1) { throw 'Unexpected Blender path probe output.' }
$paths = $marker[0].Substring('MCP_PATHS='.Length) | ConvertFrom-Json
if (-not $paths.addons -or -not $paths.config) { throw 'Blender returned empty user paths.' }

Backup-File -Path (Join-Path $paths.addons 'blender_mcp.py')
Backup-File -Path (Join-Path $paths.config 'userpref.blend')
Invoke-Checked -Exe $uvxPath -Arguments @('mcp-for-blender', 'install-addon', '--addons-dir', $paths.addons)

$enable = @'
import bpy, addon_utils
addon_utils.enable('blender_mcp', default_set=True, persistent=True)
assert 'blender_mcp' in bpy.context.preferences.addons, 'MCP addon did not enable'
bpy.ops.wm.save_userpref()
print('MCP_ADDON_ENABLED', bpy.app.version_string)
'@
Invoke-Checked -Exe $BlenderPath -Arguments @('--background', '--python-exit-code', '1', '--python-expr', $enable)

if (-not $SkipCodex) {
    # Respect custom CODEX_HOME, otherwise use the current user's .codex folder.
    $codexRoot = $env:CODEX_HOME
    if (-not $codexRoot) { $codexRoot = Join-Path $env:USERPROFILE '.codex' }
    $existing = & $codex.Source mcp get blender 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Warning "Codex already has a 'blender' entry. It was kept. Check it with: codex mcp get blender"
    }
    else {
        Backup-File -Path (Join-Path $codexRoot 'config.toml')
        Invoke-Checked -Exe $codex.Source -Arguments @('mcp', 'add', 'blender', '--env', 'DISABLE_TELEMETRY=true', '--', $uvxPath, 'mcp-for-blender')
    }
    Invoke-Checked -Exe $codex.Source -Arguments @('mcp', 'get', 'blender')
}

Write-Host 'Installation complete. Open Blender and restart your MCP client.'
Write-Host 'In the 3D viewport, press N and inspect the MCP for Blender tab.'
Write-Host 'The addon normally starts its local server automatically on port 9876.'
