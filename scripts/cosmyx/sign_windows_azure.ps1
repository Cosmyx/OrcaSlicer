<#
.SYNOPSIS
    Authenticode-signs the Windows binaries the Cosmyx build ships with Azure Artifact Signing, or
    checks that they are signed.

.DESCRIPTION
    The Cosmyx counterpart of scripts/sign_windows.ps1, with the same interface. That script hands
    over to this one when COSMYX_SIGN_BACKEND is 'azure', so the NSIS hooks CMake writes
    (CMakeLists.txt, ORCA_SIGN_KMS_KEY gate) and the CI steps reach it unchanged.

    Signs with Jsign (https://github.com/ebourg/jsign) and its TRUSTEDSIGNING keystore: Jsign sends
    each file's digest to the Artifact Signing account and builds the signature from the result.
    Every signature is timestamped (RFC 3161), which matters here: Artifact Signing certificates
    are valid for a few days only.

    A directory is searched recursively for .exe, .dll and .pyd files. A file named directly is
    handled whatever its name, which covers the temporary files makensis passes for the uninstaller
    and the installer. Files that already carry a signature are left alone (vendor-signed
    redistributables).

    With -Verify nothing is signed. The check fails if any of those files is unsigned or has a
    damaged signature, if a file named directly is not signed with a certificate whose subject is
    COSMYX_SIGN_SUBJECT, or if such a signature has no timestamp. The subject is compared, not the
    thumbprint, because Artifact Signing renews the certificate every few days.

    Environment:
      COSMYX_SIGN_ENDPOINT        Account endpoint, for example https://weu.codesigning.azure.net/
                                  (the scheme and the trailing slash are optional).
      COSMYX_SIGN_ACCOUNT         Artifact Signing account name.
      COSMYX_SIGN_PROFILE         Certificate profile name.
      COSMYX_SIGN_SUBJECT         Subject of the profile's certificates, as Windows prints it
                                  (for example 'CN=Example, O=Example, L=City, C=FR'). Needed for
                                  -Verify; when signing, it limits ORCA_SIGN_REUSE to our files.
      COSMYX_SIGN_TOKEN           Access token for the Artifact Signing resource. Not needed for
                                  -Verify or a dry run.
      COSMYX_SIGN_TOKEN_EXPIRES   Optional Unix time the token expires at. Within five minutes of
                                  it, the token is refreshed with the Azure CLI when it can be.
      COSMYX_SIGN_RESOURCE        Optional token resource, default https://codesigning.azure.net.
      COSMYX_SIGN_DRYRUN          '1' prints the Jsign command and the files instead of signing.
      ORCA_SIGN_JSIGN             Path of the Jsign jar. Java comes from JAVA_HOME, else from PATH.
      ORCA_SIGN_REUSE             Optional record of the files signed so far, as in
                                  scripts/sign_windows.ps1.

    Runs under PowerShell 7 and Windows PowerShell 5.1.

.PARAMETER Path
    Files and directories to sign or check.

.PARAMETER Verify
    Check the signatures instead of signing.
#>
param(
    [Parameter(Mandatory)] [string[]] $Path,
    [switch] $Verify
)
$ErrorActionPreference = 'Stop'

$TimestampUrl = 'http://timestamp.acs.microsoft.com'
$DefaultResource = 'https://codesigning.azure.net'
$DryRun = $env:COSMYX_SIGN_DRYRUN -eq '1'
$OnWindows = [Environment]::OSVersion.Platform -eq 'Win32NT'

function Require-Env([string] $name) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if (-not $value) {
        throw "$name is not set. See the description in $PSCommandPath."
    }
    $value
}

# Get-AuthenticodeSignature exists on Windows only. A dry run elsewhere treats every file as
# unsigned, so the command can still be previewed from any OS.
$CanReadSignatures = [bool] (Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue)
function Get-Signature([string] $file) {
    if ($CanReadSignatures) {
        return Get-AuthenticodeSignature -LiteralPath $file
    }
    if ($DryRun) {
        return [pscustomobject] @{ SignerCertificate = $null; TimeStamperCertificate = $null; Status = 'NotSigned' }
    }
    throw 'Reading Authenticode signatures needs Windows (Get-AuthenticodeSignature).'
}

$Subject = $env:COSMYX_SIGN_SUBJECT
if ($Subject) {
    $Subject = $Subject.Trim()
}
function Test-Ours($signature) {
    $signer = $signature.SignerCertificate
    if (-not $signer) {
        return $false
    }
    if (-not $Subject) {
        return $true
    }
    $signer.Subject -eq $Subject
}

# Each entry is a file and whether it was named directly.
$files = @()
foreach ($item in $Path) {
    if (Test-Path -LiteralPath $item -PathType Container) {
        $files += Get-ChildItem -LiteralPath $item -Recurse -File |
            Where-Object { $_.Extension -in '.exe', '.dll', '.pyd' } |
            ForEach-Object { [pscustomobject] @{ Path = $_.FullName; Named = $false } }
    } elseif (Test-Path -LiteralPath $item -PathType Leaf) {
        $files += [pscustomobject] @{ Path = (Resolve-Path -LiteralPath $item).ProviderPath; Named = $true }
    } else {
        throw "$item does not exist."
    }
}

if ($Verify) {
    $null = Require-Env 'COSMYX_SIGN_SUBJECT'
    $problems = @()
    $ourCount = 0
    foreach ($file in $files) {
        $signature = Get-Signature $file.Path
        $signer = $signature.SignerCertificate
        $ours = Test-Ours $signature
        if ($ours) {
            $ourCount++
        }
        if (-not $signer) {
            $problems += "unsigned: $($file.Path)"
        } elseif ($file.Named -and -not $ours) {
            $problems += "signed by $($signer.Subject), not $Subject`: $($file.Path)"
        } elseif ($ours -and -not $signature.TimeStamperCertificate) {
            $problems += "no timestamp: $($file.Path)"
        } elseif ("$($signature.Status)" -ne 'Valid') {
            $problems += "signature status $($signature.Status): $($file.Path)"
        }
    }
    if ($problems) {
        $problems | ForEach-Object { Write-Host $_ }
        throw "$($problems.Count) of $($files.Count) files failed the signature check."
    }
    Write-Host "All $($files.Count) files are signed, $ourCount of them with $Subject."
    return
}

$endpoint = (Require-Env 'COSMYX_SIGN_ENDPOINT') -replace '^https?://', '' -replace '/+$', ''
$account = Require-Env 'COSMYX_SIGN_ACCOUNT'
$certProfile = Require-Env 'COSMYX_SIGN_PROFILE'
$jsign = Require-Env 'ORCA_SIGN_JSIGN'
if (-not $DryRun) {
    $null = Require-Env 'COSMYX_SIGN_TOKEN'
}

$unsigned = @($files | Where-Object { -not (Get-Signature $_.Path).SignerCertificate } |
    ForEach-Object { $_.Path })
Write-Host "$($unsigned.Count) of $($files.Count) files to sign; the rest are already signed."
if (-not $unsigned) {
    return
}

# The record maps a file's SHA-256 before signing to the signed file. A copy is taken only from a
# file that still carries our signature.
$record = @{}
$hashes = @{}
$toSign = $unsigned
if ($env:ORCA_SIGN_REUSE) {
    if (Test-Path -LiteralPath $env:ORCA_SIGN_REUSE) {
        (Get-Content -LiteralPath $env:ORCA_SIGN_REUSE -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties |
            ForEach-Object { $record[$_.Name] = $_.Value }
    }
    $toSign = @()
    foreach ($file in $unsigned) {
        $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
        $hashes[$file] = $hash
        $signed = $record[$hash]
        if ($signed -and (Test-Path -LiteralPath $signed) -and (Test-Ours (Get-Signature $signed))) {
            if ($DryRun) {
                Write-Host "DRYRUN copy $signed -> $file"
            } else {
                Copy-Item -LiteralPath $signed -Destination $file -Force
            }
        } else {
            $toSign += $file
        }
    }
    Write-Host "$($unsigned.Count - $toSign.Count) of them copied from files already signed."
    if (-not $toSign) {
        return
    }
}

# Artifact Signing tokens last about an hour. cpack signs the uninstaller and the installer at the
# end of a long makensis run, so a token close to its end is renewed from the Azure CLI login.
function Update-Token {
    if (-not $env:COSMYX_SIGN_TOKEN_EXPIRES) {
        return
    }
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    if ($now + 300 -lt [long] $env:COSMYX_SIGN_TOKEN_EXPIRES) {
        return
    }
    $resource = $env:COSMYX_SIGN_RESOURCE
    if (-not $resource) {
        $resource = $DefaultResource
    }
    $answer = $null
    if (Get-Command az -ErrorAction SilentlyContinue) {
        $answer = (& az account get-access-token --resource $resource --query '{token:accessToken,expires:expires_on}' -o json 2>$null) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            $answer = $null
        }
    }
    if (-not $answer) {
        throw 'COSMYX_SIGN_TOKEN has expired and could not be refreshed with the Azure CLI.'
    }
    $fresh = $answer | ConvertFrom-Json
    if (-not $fresh.token) {
        throw 'COSMYX_SIGN_TOKEN has expired and could not be refreshed with the Azure CLI.'
    }
    $env:COSMYX_SIGN_TOKEN = $fresh.token
    $env:COSMYX_SIGN_TOKEN_EXPIRES = "$($fresh.expires)"
    Write-Host 'Refreshed the Artifact Signing access token.'
}

$java = 'java'
if ($env:JAVA_HOME) {
    $javaName = 'java'
    if ($OnWindows) {
        $javaName = 'java.exe'
    }
    $java = Join-Path (Join-Path $env:JAVA_HOME 'bin') $javaName
}
# Jsign reads the files to sign from a list file, one path per line (UTF-8 without a BOM).
# The token is passed by name (env:), so it never appears on a command line or in a log.
$list = [IO.Path]::GetTempFileName()
try {
    [IO.File]::WriteAllLines($list, [string[]] $toSign)
    $arguments = @('-jar', $jsign, '--storetype', 'TRUSTEDSIGNING', '--keystore', $endpoint,
        '--alias', "$account/$certProfile", '--storepass', 'env:COSMYX_SIGN_TOKEN', '--alg', 'SHA-256',
        '--tsaurl', $TimestampUrl, '--tsmode', 'RFC3161', '--tsretries', '5', '--tsretrywait', '15',
        "@$list")
    if ($DryRun) {
        $toSign | ForEach-Object { Write-Host "DRYRUN sign $_" }
        Write-Host "DRYRUN $java $($arguments -join ' ')"
        return
    }
    Update-Token
    & $java @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Jsign failed with exit code $LASTEXITCODE."
    }
} finally {
    Remove-Item -LiteralPath $list -ErrorAction SilentlyContinue
}

if ($env:ORCA_SIGN_REUSE) {
    foreach ($file in $toSign) {
        $record[$hashes[$file]] = $file
    }
    $record | ConvertTo-Json | Set-Content -LiteralPath $env:ORCA_SIGN_REUSE -Encoding UTF8
}
