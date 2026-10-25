# Repair-CodexDaemon.ps1 -- clear stale Codex CLI daemon records.
#
# Why: ~/.codex/app-server-daemon/daemon.pid survives reboots. When the recorded
# PID is later reused by a protected process (SYSTEM service, elevated app),
# `codex` tries to open that process, gets "Access is denied (os error 5)" and
# refuses to start instead of treating the record as stale. This script moves
# any record that does not point at a live codex.exe owned by the current user
# into a timestamped backup folder so Codex starts a fresh daemon.
#
# Safe to run any time: a healthy daemon is left untouched.
#
# Usage:
#   Repair-CodexDaemon.ps1            # repair ~/.codex
#   Repair-CodexDaemon.ps1 -Quiet     # no output unless something was repaired
#   Repair-CodexDaemon.ps1 -CodexHome <dir>   # test against another folder

[CmdletBinding()]
param(
    [string]$CodexHome = (Join-Path $env:USERPROFILE '.codex'),
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$daemonDir  = Join-Path $CodexHome 'app-server-daemon'
$controlDir = Join-Path $CodexHome 'app-server-control'
$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name

function Test-LiveCodexProcess {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $false }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $proc) { return $false }
    if ($proc.Name -ne 'codex.exe') { return $false }
    try {
        $owner = Invoke-CimMethod -InputObject $proc -MethodName GetOwner -ErrorAction Stop
        if ($owner.ReturnValue -ne 0) { return $false }
        $ownerName = "$($owner.Domain)\$($owner.User)"
    } catch { return $false }   # cannot read owner => protected process => not ours
    return ($ownerName -ieq $me)
}

function Read-PidRecord {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
        if ($raw -match '"pid"\s*:\s*(\d+)') { return [int]$Matches[1] }
    } catch { }
    return -1   # unreadable or malformed => treat as stale
}

$records = @(
    @{ Name = 'daemon';  Pid = (Join-Path $daemonDir 'daemon.pid');         Extra = @((Join-Path $controlDir 'app-server-control.sock')) },
    @{ Name = 'updater'; Pid = (Join-Path $daemonDir 'daemon-updater.pid'); Extra = @((Join-Path $daemonDir 'daemon-updater.sock')) }
)

$stale = @()
foreach ($r in $records) {
    $recordedPid = Read-PidRecord $r.Pid
    if ($null -eq $recordedPid) { continue }        # no record, nothing to do
    if (Test-LiveCodexProcess $recordedPid) { continue }
    $stale += [pscustomobject]@{ Name = $r.Name; Pid = $recordedPid; Files = @($r.Pid) + $r.Extra }
}

if (-not $stale) {
    if (-not $Quiet) { Write-Host 'Codex daemon records are healthy.' }
    exit 0
}

$backup = Join-Path $daemonDir ("stale-backup-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $backup | Out-Null
foreach ($s in $stale) {
    foreach ($f in $s.Files) {
        if (Test-Path -LiteralPath $f) {
            Move-Item -LiteralPath $f -Destination (Join-Path $backup (Split-Path $f -Leaf)) -Force
        }
    }
    Write-Host ("Cleared stale Codex {0} record (pid {1} is not a live codex.exe owned by {2})." -f $s.Name, $s.Pid, $me)
}
Write-Host "Backup: $backup"
exit 0
