<#
.SYNOPSIS
    Collects Authenticode facts about Windows binaries, one JSON line per file.

.DESCRIPTION
    Part of the Cosmyx artifact checks (wiki/cosmyx/artifact-checks.md). This script decides
    nothing: the rules live in policy_windows.py (decision 0142). For every file it writes:

      path, sha256, signtool_exit, signtool_tail, auth_status, signer_subject, signer_ekus,
      signer_thumbprint, timestamp_subject

    signtool_* come from `signtool verify /pa /all /tw /v` (the newest signtool of the installed
    Windows Kits, or COSMYX_SIGNTOOL). A failure that names revocation or the network is retried
    once. auth_status, signer_* and timestamp_subject come from Get-AuthenticodeSignature (the
    primary signature only).

.PARAMETER Path
    Files to inspect.

.PARAMETER PathList
    A text file with one path per line, for long lists.

.PARAMETER Out
    The JSON lines file to write (UTF-8, LF).
#>
param(
    [string[]] $Path = @(),
    [string] $PathList = '',
    [Parameter(Mandatory)] [string] $Out
)
$ErrorActionPreference = 'Stop'

$RetryPattern = 'revocation|offline|network|0x80092013|0x80092012|0x800b010e|timed? ?out'

function Find-Signtool {
    if ($env:COSMYX_SIGNTOOL) {
        return $env:COSMYX_SIGNTOOL
    }
    $kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    if (Test-Path -LiteralPath $kits) {
        $found = Get-ChildItem -LiteralPath $kits -Directory |
            Where-Object { $_.Name -match '^\d+(\.\d+)+$' } |
            Sort-Object { [version] $_.Name } -Descending |
            ForEach-Object { Join-Path $_.FullName 'x64\signtool.exe' } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1
        if ($found) {
            return $found
        }
    }
    $onPath = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($onPath) {
        return $onPath.Source
    }
    throw 'signtool.exe was not found (install the Windows SDK or set COSMYX_SIGNTOOL).'
}

function Invoke-Signtool([string] $signtool, [string] $file) {
    $lines = & $signtool verify /pa /all /tw /v $file 2>&1 | ForEach-Object { "$_" }
    [pscustomobject] @{ Exit = $LASTEXITCODE; Output = ($lines -join "`n") }
}

function Get-Tail([string] $text) {
    $lines = @($text -split "`n" | Where-Object { $_.Trim() })
    ($lines | Select-Object -Last 5) -join "`n"
}

$files = @($Path)
if ($PathList) {
    $files += Get-Content -LiteralPath $PathList -Encoding UTF8 | Where-Object { $_.Trim() }
}
$signtool = Find-Signtool

$lines = foreach ($file in $files) {
    $result = Invoke-Signtool $signtool $file
    if ($result.Exit -ne 0 -and $result.Output -match $RetryPattern) {
        Start-Sleep -Seconds 5
        $result = Invoke-Signtool $signtool $file
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $file
    $signer = $signature.SignerCertificate
    $ekus = @()
    if ($signer -and $signer.EnhancedKeyUsageList) {
        $ekus = @($signer.EnhancedKeyUsageList | ForEach-Object { "$($_.ObjectId)" })
    }
    $stamp = $signature.TimeStamperCertificate
    [ordered] @{
        path              = $file
        sha256            = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
        signtool_exit     = $result.Exit
        signtool_tail     = Get-Tail $result.Output
        auth_status       = "$($signature.Status)"
        signer_subject    = if ($signer) { $signer.Subject } else { $null }
        signer_ekus       = $ekus
        signer_thumbprint = if ($signer) { $signer.Thumbprint } else { $null }
        timestamp_subject = if ($stamp) { $stamp.Subject } else { $null }
    } | ConvertTo-Json -Compress -Depth 4
}

$text = ''
if ($lines) {
    $text = ($lines -join "`n") + "`n"
}
[System.IO.File]::WriteAllText($Out, $text, [System.Text.UTF8Encoding]::new($false))
Write-Host "Signature facts for $($files.Count) files written to $Out."
