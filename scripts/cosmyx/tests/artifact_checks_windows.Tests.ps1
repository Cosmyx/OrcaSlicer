# Pester 5 tests of scripts/cosmyx/artifact_checks/facts_windows.ps1.
#
# The mocked part runs under pwsh on any OS: signtool is a fake script named by COSMYX_SIGNTOOL whose
# exit codes follow COSMYX_FAKE_CODES, and Get-AuthenticodeSignature is replaced by a global stub
# function (a function wins over a cmdlet of the same name), as in sign_windows_azure.Tests.ps1.
# The real-tool part runs on Windows only: it copies the Microsoft-signed signtool.exe into
# TestDrive, breaks one byte of its code section, and clears its certificate table.

Describe 'Cosmyx artifact checks: Windows signature facts' {
    BeforeAll {
        $Script = Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'artifact_checks') 'facts_windows.ps1'
        $EnvNames = 'COSMYX_SIGNTOOL', 'COSMYX_FAKE_CODES', 'COSMYX_FAKE_MESSAGE', 'COSMYX_FAKE_STATE'
        $SavedEnv = @{}
        foreach ($name in $EnvNames) {
            $SavedEnv[$name] = [Environment]::GetEnvironmentVariable($name)
        }

        $FakeSigntool = Join-Path $TestDrive 'fake-signtool.ps1'
        Set-Content -LiteralPath $FakeSigntool -Value @'
$count = 0
if (Test-Path -LiteralPath $env:COSMYX_FAKE_STATE) { $count = [int] (Get-Content -LiteralPath $env:COSMYX_FAKE_STATE) }
$count++
Set-Content -LiteralPath $env:COSMYX_FAKE_STATE -Value $count
$codes = $env:COSMYX_FAKE_CODES -split ','
$code = [int] $codes[[Math]::Min($count - 1, $codes.Count - 1)]
Write-Output "Verifying: $($args[-1])"
if ($code -ne 0) { Write-Output $env:COSMYX_FAKE_MESSAGE }
exit $code
'@

        function Install-SignatureStub {
            function global:Get-AuthenticodeSignature {
                param([string] $LiteralPath, [string] $FilePath)
                $eku = @(
                    [pscustomobject] @{ ObjectId = '1.3.6.1.5.5.7.3.3' },
                    [pscustomobject] @{ ObjectId = '1.3.6.1.4.1.311.97.1.0' }
                )
                [pscustomobject] @{
                    Status                 = 'Valid'
                    SignerCertificate      = [pscustomobject] @{
                        Subject = 'CN=Cosmyx Test'; Thumbprint = 'AB12'; EnhancedKeyUsageList = $eku
                    }
                    TimeStamperCertificate = [pscustomobject] @{ Subject = 'CN=Timestamp' }
                }
            }
        }

        function Read-Facts([string] $out) {
            @(Get-Content -LiteralPath $out | Where-Object { $_ } | ForEach-Object { $_ | ConvertFrom-Json })
        }
    }

    AfterAll {
        Remove-Item -Path Function:\Get-AuthenticodeSignature -ErrorAction SilentlyContinue
        foreach ($name in $EnvNames) {
            [Environment]::SetEnvironmentVariable($name, $SavedEnv[$name])
        }
    }

    Context 'with a fake signtool' {
        BeforeEach {
            Install-SignatureStub
            $env:COSMYX_SIGNTOOL = $FakeSigntool
            $env:COSMYX_FAKE_STATE = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
            $env:COSMYX_FAKE_MESSAGE = 'SignTool Error: A certificate chain could not be built.'
            $File = Join-Path $TestDrive 'app with space.exe'
            Set-Content -LiteralPath $File -Value 'binary'
            $Out = Join-Path $TestDrive 'facts.jsonl'
        }

        It 'writes one JSON line with every fact' {
            $env:COSMYX_FAKE_CODES = '0'
            & $Script -Path $File -Out $Out | Out-Null
            $facts = Read-Facts $Out
            $facts.Count | Should -Be 1
            $facts[0].path | Should -Be $File
            $facts[0].sha256 | Should -Match '^[0-9a-f]{64}$'
            $facts[0].signtool_exit | Should -Be 0
            $facts[0].auth_status | Should -Be 'Valid'
            $facts[0].signer_subject | Should -Be 'CN=Cosmyx Test'
            $facts[0].signer_ekus | Should -Contain '1.3.6.1.4.1.311.97.1.0'
            $facts[0].signer_thumbprint | Should -Be 'AB12'
            $facts[0].timestamp_subject | Should -Be 'CN=Timestamp'
        }

        It 'reports exit codes 1 and 2 with the output tail' {
            foreach ($code in 1, 2) {
                $env:COSMYX_FAKE_STATE = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
                $env:COSMYX_FAKE_CODES = "$code"
                & $Script -Path $File -Out $Out | Out-Null
                $fact = (Read-Facts $Out)[0]
                $fact.signtool_exit | Should -Be $code
                $fact.signtool_tail | Should -Match 'certificate chain'
            }
        }

        It 'retries once on a revocation or network failure' {
            $env:COSMYX_FAKE_CODES = '1,0'
            $env:COSMYX_FAKE_MESSAGE = 'SignTool Error: The revocation function was unable to check revocation.'
            & $Script -Path $File -Out $Out | Out-Null
            (Read-Facts $Out)[0].signtool_exit | Should -Be 0
            [int] (Get-Content -LiteralPath $env:COSMYX_FAKE_STATE) | Should -Be 2
        }

        It 'retries only once' {
            $env:COSMYX_FAKE_CODES = '1,1,0'
            $env:COSMYX_FAKE_MESSAGE = 'The server is offline (0x80092013).'
            & $Script -Path $File -Out $Out | Out-Null
            (Read-Facts $Out)[0].signtool_exit | Should -Be 1
            [int] (Get-Content -LiteralPath $env:COSMYX_FAKE_STATE) | Should -Be 2
        }

        It 'does not retry other failures' {
            $env:COSMYX_FAKE_CODES = '1,0'
            & $Script -Path $File -Out $Out | Out-Null
            (Read-Facts $Out)[0].signtool_exit | Should -Be 1
            [int] (Get-Content -LiteralPath $env:COSMYX_FAKE_STATE) | Should -Be 1
        }

        It 'reads a path list and writes LF without a byte order mark' {
            $env:COSMYX_FAKE_CODES = '0'
            $second = Join-Path $TestDrive 'lib.dll'
            Set-Content -LiteralPath $second -Value 'lib'
            $list = Join-Path $TestDrive 'list.txt'
            Set-Content -LiteralPath $list -Value @($File, $second)
            & $Script -PathList $list -Out $Out | Out-Null
            (Read-Facts $Out).Count | Should -Be 2
            $bytes = [System.IO.File]::ReadAllBytes($Out)
            $bytes[0] | Should -Be ([byte] [char] '{')
            [System.Text.Encoding]::UTF8.GetString($bytes) | Should -Not -Match "`r"
        }

        It 'reports an unsigned file with empty signer facts' {
            function global:Get-AuthenticodeSignature {
                param([string] $LiteralPath)
                [pscustomobject] @{ Status = 'NotSigned'; SignerCertificate = $null; TimeStamperCertificate = $null }
            }
            $env:COSMYX_FAKE_CODES = '1'
            & $Script -Path $File -Out $Out | Out-Null
            $fact = (Read-Facts $Out)[0]
            $fact.auth_status | Should -Be 'NotSigned'
            $fact.signer_subject | Should -BeNullOrEmpty
            @($fact.signer_ekus).Count | Should -Be 0
        }
    }

    Context 'with the real signtool' -Skip:(-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
        BeforeAll {
            Remove-Item -Path Function:\Get-AuthenticodeSignature -ErrorAction SilentlyContinue
            $env:COSMYX_SIGNTOOL = $null
            $kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
            $RealSigntool = Get-ChildItem -LiteralPath $kits -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
                Where-Object { $_.DirectoryName -match '\\x64$' } | Select-Object -First 1

            # Offsets of a PE file: the first section's raw data and the certificate table entry.
            function Get-PeLayout([byte[]] $bytes) {
                $pe = [BitConverter]::ToInt32($bytes, 0x3C)
                $sections = [BitConverter]::ToUInt16($bytes, $pe + 6)
                $optionalSize = [BitConverter]::ToUInt16($bytes, $pe + 20)
                $optional = $pe + 24
                $magic = [BitConverter]::ToUInt16($bytes, $optional)
                $directories = if ($magic -eq 0x20b) { $optional + 112 } else { $optional + 96 }
                $table = $optional + $optionalSize
                $code = $null
                for ($i = 0; $i -lt $sections; $i++) {
                    $entry = $table + 40 * $i
                    $name = [System.Text.Encoding]::ASCII.GetString($bytes, $entry, 8).TrimEnd([char] 0)
                    if ($name -eq '.text') {
                        $code = [BitConverter]::ToInt32($bytes, $entry + 20)
                    }
                }
                [pscustomobject] @{ Code = $code; CertificateEntry = $directories + 4 * 8 }
            }
        }

        BeforeEach {
            if (-not $RealSigntool) {
                Set-ItResult -Skipped -Because 'no Windows SDK signtool.exe on this machine'
            }
            $Out = Join-Path $TestDrive 'real.jsonl'
        }

        It 'reports a Microsoft-signed copy as valid' {
            $copy = Join-Path $TestDrive 'signed.exe'
            Copy-Item -LiteralPath $RealSigntool.FullName -Destination $copy
            & $Script -Path $copy -Out $Out | Out-Null
            $fact = (Read-Facts $Out)[0]
            $fact.signtool_exit | Should -Be 0
            $fact.auth_status | Should -Be 'Valid'
            $fact.signer_subject | Should -Match 'Microsoft'
        }

        It 'reports a changed code byte as a failure' {
            $bytes = [System.IO.File]::ReadAllBytes($RealSigntool.FullName)
            $layout = Get-PeLayout $bytes
            $bytes[$layout.Code + 0x100] = $bytes[$layout.Code + 0x100] -bxor 0xFF
            $broken = Join-Path $TestDrive 'broken.exe'
            [System.IO.File]::WriteAllBytes($broken, $bytes)
            & $Script -Path $broken -Out $Out | Out-Null
            $fact = (Read-Facts $Out)[0]
            $fact.signtool_exit | Should -Be 1
            $fact.auth_status | Should -Not -Be 'Valid'
        }

        It 'reports a copy without its certificate table as unsigned' {
            $bytes = [System.IO.File]::ReadAllBytes($RealSigntool.FullName)
            $layout = Get-PeLayout $bytes
            for ($i = 0; $i -lt 8; $i++) {
                $bytes[$layout.CertificateEntry + $i] = 0
            }
            $unsigned = Join-Path $TestDrive 'unsigned.exe'
            [System.IO.File]::WriteAllBytes($unsigned, $bytes)
            & $Script -Path $unsigned -Out $Out | Out-Null
            $fact = (Read-Facts $Out)[0]
            $fact.signtool_exit | Should -Be 1
            $fact.auth_status | Should -Be 'NotSigned'
        }
    }
}
