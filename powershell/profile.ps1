# claude-kit PowerShell profile — canonical copy.
# $PROFILE (in OneDrive\Documents\WindowsPowerShell) is a one-line stub that
# dot-sources this file, so the real logic lives in git, not OneDrive.

# ─── cc: fuzzy project launcher ──────────────────────────────────────
# Usage:
#   cc            → interactive fzf picker over all project folders
#   cc sbir       → fuzzy match; auto-opens if unambiguous
#   ccd <query>   → same but just cd, no claude launch
function Get-ProjectDirs {
    $roots = @(
        "$env:USERPROFILE\OneDrive\Desktop\Projects",
        "C:\dev"
    ) | Where-Object { Test-Path $_ }
    $dirs = New-Object System.Collections.Generic.List[string]
    foreach ($r in $roots) {
        $dirs.Add($r)
        Get-ChildItem $r -Directory -Depth 2 -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\(node_modules|\.git|\.venv|venv|__pycache__|dist|build|Archive|archive)(\\|$)' } |
            ForEach-Object { $dirs.Add($_.FullName) }
    }
    return $dirs
}

function Select-ProjectDir {
    param([string]$Query)
    $dirs = Get-ProjectDirs
    if (Get-Command fzf -ErrorAction SilentlyContinue) {
        if ($Query) { return ($dirs | fzf --select-1 --exit-0 --query "$Query") }
        return ($dirs | fzf)
    }
    # Fallback without fzf: exact folder-name match wins, else most recently
    # modified wildcard match
    $exact = $dirs | Where-Object { (Split-Path $_ -Leaf) -ieq $Query }
    if ($exact) { return ($exact | Select-Object -First 1) }
    $m = $dirs | Where-Object { (Split-Path $_ -Leaf) -like "*$Query*" }
    if (-not $m) { $m = $dirs | Where-Object { $_ -like "*$Query*" } }
    return ($m | Sort-Object { (Get-Item $_).LastWriteTime } -Descending | Select-Object -First 1)
}

function cc {
    param([string]$Query)
    $sel = Select-ProjectDir $Query
    if ($sel) {
        Set-Location $sel
        Write-Host "-> $sel" -ForegroundColor DarkGray
        claude
    } else { Write-Host "No project matching '$Query'." }
}

function ccd {
    param([string]$Query)
    $sel = Select-ProjectDir $Query
    if ($sel) { Set-Location $sel } else { Write-Host "No project matching '$Query'." }
}

# ─── cd: smart cd — `cd dev` works from anywhere and lists projects ──
Remove-Item Alias:cd -Force -ErrorAction SilentlyContinue
function cd {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Path)
    if (-not $Path) { Set-Location $env:USERPROFILE }
    elseif ($Path[0] -eq 'dev' -and -not (Test-Path 'dev')) { Set-Location 'C:\dev' }
    else { Set-Location $Path[0] }
    if ((Get-Location).Path -ieq 'C:\dev') {
        Get-ChildItem -Directory | Where-Object { $_.Name -notlike '.*' } |
            Sort-Object Name | Format-Wide Name -AutoSize
    }
}
function dev { cd dev }

# ─── snag: pull recent files out of Downloads into the current folder ─
# Usage:
#   snag           → move the single most recent download here
#   snag 3         → move the 3 most recent downloads here
#   snag pdf       → move every download whose name matches *pdf* (confirms first)
#   snag pdf 2     → the 2 most recent *pdf* matches
function snag {
    param([string]$Pattern = '', [int]$Count = 0)
    if ($Pattern -match '^\d+$') { $Count = [int]$Pattern; $Pattern = '' }
    if (-not $Count) { $Count = if ($Pattern) { 1000 } else { 1 } }
    $filter = if (-not $Pattern) { '*' }
              elseif ($Pattern -match '[\*\?]') { $Pattern }
              else { "*$Pattern*" }
    $dl = Join-Path $env:USERPROFILE 'Downloads'
    $files = @(Get-ChildItem $dl -File -Filter $filter |
        Where-Object { $_.Extension -notin '.crdownload', '.tmp', '.partial' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First $Count)
    if (-not $files) { Write-Host "Nothing in Downloads matches '$filter'."; return }
    Write-Host "Downloads -> $((Get-Location).Path)" -ForegroundColor Cyan
    $files | ForEach-Object { Write-Host ("  {0}  ({1:g})" -f $_.Name, $_.LastWriteTime) }
    $ans = Read-Host "Move $($files.Count) file(s)? [Y/n]"
    if ($ans -match '^[Nn]') { Write-Host "Cancelled."; return }
    foreach ($f in $files) { Move-Item -LiteralPath $f.FullName -Destination . }
    Write-Host "Moved $($files.Count) file(s)."
}
