<#
.SYNOPSIS
    Finds the NSIS installer the Windows build wrote, whatever its product prefix.

.DESCRIPTION
    cpack names the installer <Product>_Windows_Installer_<version>.exe. The product prefix is
    OrcaSlicer upstream and CosmoSlice once the Cosmyx product name lands, so any prefix matches
    and the merge order of the two changes does not matter. When several installers match, the
    most recent one is returned.

    Prints the installer's full path. When none is found the script fails, because the verify
    step of a signed build must check the installer; with -Optional it prints nothing instead
    (builds that do not make an installer, such as self-hosted runners).

.PARAMETER Directory
    The build directory cpack writes the installer to.

.PARAMETER Optional
    Do not fail when no installer is found.
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $Directory,
    [switch] $Optional
)

$ErrorActionPreference = 'Stop'

$Pattern = '*_Windows_Installer_*.exe'

$installer = $null
if (Test-Path -LiteralPath $Directory -PathType Container) {
    $installer = Get-ChildItem -LiteralPath $Directory -Filter $Pattern -File |
        Sort-Object -Property LastWriteTimeUtc -Descending |
        Select-Object -First 1
}

if ($installer) {
    $installer.FullName
    return
}
if ($Optional) {
    Write-Host "No Windows installer ($Pattern) in '$Directory'; this build does not make one."
    return
}
throw "No Windows installer ($Pattern) in '$Directory': a signed build must verify its installer."
