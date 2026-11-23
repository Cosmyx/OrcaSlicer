# Pester 5 tests of scripts/cosmyx/find_windows_installer.ps1, the installer lookup of the
# cosmyx-sign verify step. They only create empty files under $TestDrive, so they run under pwsh
# on any OS.

Describe 'Cosmyx Windows installer lookup' {
    BeforeAll {
        $Script = Join-Path (Split-Path -Parent $PSScriptRoot) 'find_windows_installer.ps1'

        function New-BuildFile([string] $name, [datetime] $written = [datetime]::UtcNow) {
            $path = Join-Path $TestDrive $name
            $null = New-Item -ItemType File -Path $path -Force
            (Get-Item -LiteralPath $path).LastWriteTimeUtc = $written
            $path
        }
    }

    BeforeEach {
        Get-ChildItem -LiteralPath $TestDrive | Remove-Item -Recurse -Force
    }

    It 'finds the upstream OrcaSlicer installer' {
        $expected = New-BuildFile 'OrcaSlicer_Windows_Installer_V2.3.2_x64.exe'
        & $Script -Directory $TestDrive | Should -Be (Get-Item -LiteralPath $expected).FullName
    }

    It 'finds the CosmoSlice installer' {
        $expected = New-BuildFile 'CosmoSlice_Windows_Installer_V2.3.2_x64.exe'
        & $Script -Directory $TestDrive | Should -Be (Get-Item -LiteralPath $expected).FullName
    }

    It 'fails when the build wrote no installer' {
        $null = New-BuildFile 'orca-slicer.exe'
        $null = New-BuildFile 'CosmoSlice_Windows_V2.3.2_x64.zip'
        { & $Script -Directory $TestDrive } | Should -Throw '*No Windows installer*a signed build must verify its installer*'
    }

    It 'fails when the build directory does not exist' {
        { & $Script -Directory (Join-Path $TestDrive 'missing') } | Should -Throw '*No Windows installer*'
    }

    It 'prints nothing and does not fail with -Optional when there is no installer' {
        $found = & $Script -Directory $TestDrive -Optional 6>$null
        $found | Should -BeNullOrEmpty
    }

    It 'still returns the installer with -Optional' {
        $expected = New-BuildFile 'CosmoSlice_Windows_Installer_V2.3.2_arm64.exe'
        & $Script -Directory $TestDrive -Optional | Should -Be (Get-Item -LiteralPath $expected).FullName
    }

    It 'returns the most recent installer when several match' {
        $null = New-BuildFile 'OrcaSlicer_Windows_Installer_V2.3.1_x64.exe' ([datetime]::UtcNow.AddHours(-1))
        $expected = New-BuildFile 'CosmoSlice_Windows_Installer_V2.3.2_x64.exe'
        & $Script -Directory $TestDrive | Should -Be (Get-Item -LiteralPath $expected).FullName
    }

    It 'handles a build directory with spaces in its path' {
        $null = New-Item -ItemType Directory -Path (Join-Path $TestDrive 'build dir') -Force
        $expected = New-BuildFile (Join-Path 'build dir' 'CosmoSlice_Windows_Installer_V2.3.2_x64.exe')
        & $Script -Directory (Join-Path $TestDrive 'build dir') | Should -Be (Get-Item -LiteralPath $expected).FullName
    }
}
