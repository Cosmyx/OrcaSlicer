# Pester 5 tests of scripts/cosmyx/sign_windows_azure.ps1 and of its dispatch hook in
# scripts/sign_windows.ps1. They never sign anything: signing runs as a dry run
# (COSMYX_SIGN_DRYRUN=1), and Get-AuthenticodeSignature is replaced by a global stub function
# (a function wins over a cmdlet of the same name), so the suite runs under pwsh on any OS.

Describe 'Cosmyx Azure signing' {
    BeforeAll {
        $ScriptsDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $AzureScript = Join-Path (Join-Path $ScriptsDir 'cosmyx') 'sign_windows_azure.ps1'
        $UpstreamScript = Join-Path $ScriptsDir 'sign_windows.ps1'
        $Subject = 'CN=Cosmyx Test, O=Cosmyx Test, C=FR'
        $EnvNames = 'COSMYX_SIGN_BACKEND', 'COSMYX_SIGN_ENDPOINT', 'COSMYX_SIGN_ACCOUNT', 'COSMYX_SIGN_PROFILE',
            'COSMYX_SIGN_SUBJECT', 'COSMYX_SIGN_TOKEN', 'COSMYX_SIGN_TOKEN_EXPIRES', 'COSMYX_SIGN_RESOURCE',
            'COSMYX_SIGN_DRYRUN', 'ORCA_SIGN_JSIGN', 'ORCA_SIGN_REUSE', 'ORCA_SIGN_KMS_KEY', 'ORCA_SIGN_CERTFILE',
            'ORCA_SIGN_TOKEN', 'JAVA_HOME'
        $SavedEnv = @{}
        foreach ($name in $EnvNames) {
            $SavedEnv[$name] = [Environment]::GetEnvironmentVariable($name)
        }

        # Signatures the stub reports, keyed by file name; any other file is unsigned.
        $global:CosmyxTestSignatures = @{}
        function global:Get-AuthenticodeSignature {
            param([string] $LiteralPath, [string] $FilePath)
            $target = $LiteralPath
            if (-not $target) {
                $target = $FilePath
            }
            $known = $global:CosmyxTestSignatures[(Split-Path -Leaf $target)]
            if ($known) {
                return $known
            }
            [pscustomobject] @{ SignerCertificate = $null; TimeStamperCertificate = $null; Status = 'NotSigned' }
        }

        function New-Signature([string] $signerSubject, [bool] $timestamped = $true, [string] $status = 'Valid') {
            $stamp = $null
            if ($timestamped) {
                $stamp = [pscustomobject] @{ Subject = 'CN=Timestamp' }
            }
            [pscustomobject] @{
                SignerCertificate      = [pscustomobject] @{ Subject = $signerSubject; Thumbprint = 'AB' }
                TimeStamperCertificate = $stamp
                Status                 = $status
            }
        }

        function Invoke-Captured([string] $script, [hashtable] $arguments) {
            & $script @arguments *>&1 | Out-String
        }
    }

    AfterAll {
        Remove-Item -Path Function:\Get-AuthenticodeSignature -ErrorAction SilentlyContinue
        Remove-Variable -Name CosmyxTestSignatures -Scope Global -ErrorAction SilentlyContinue
        foreach ($name in $EnvNames) {
            [Environment]::SetEnvironmentVariable($name, $SavedEnv[$name])
        }
    }

    BeforeEach {
        foreach ($name in $EnvNames) {
            [Environment]::SetEnvironmentVariable($name, $null)
        }
        $global:CosmyxTestSignatures = @{}
        $env:COSMYX_SIGN_ENDPOINT = 'https://weu.codesigning.azure.net/'
        $env:COSMYX_SIGN_ACCOUNT = 'test-account'
        $env:COSMYX_SIGN_PROFILE = 'test-profile'
        $env:COSMYX_SIGN_SUBJECT = $Subject
        $env:ORCA_SIGN_JSIGN = 'jsign-test.jar'
        $env:COSMYX_SIGN_DRYRUN = '1'

        $App = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
        $Sub = Join-Path $App 'sub'
        New-Item -ItemType Directory -Path $Sub -Force | Out-Null
        foreach ($name in 'app.exe', 'lib.dll', 'mod.pyd', 'readme.txt') {
            Set-Content -LiteralPath (Join-Path $App $name) -Value $name
        }
        Set-Content -LiteralPath (Join-Path $Sub 'nested.dll') -Value 'nested'
        $Named = Join-Path $TestDrive 'makensis-temp.tmp'
        Set-Content -LiteralPath $Named -Value 'installer'
    }

    Context 'sign_windows_azure.ps1 dry run' {
        It 'prints the Jsign TRUSTEDSIGNING command' {
            $out = Invoke-Captured $AzureScript @{ Path = @($App) }
            $out | Should -Match '--storetype TRUSTEDSIGNING'
            $out | Should -Match '--keystore weu\.codesigning\.azure\.net '
            $out | Should -Match '--alias test-account/test-profile'
            $out | Should -Match '--storepass env:COSMYX_SIGN_TOKEN'
            $out | Should -Match '--alg SHA-256'
            $out | Should -Match '--tsaurl http://timestamp\.acs\.microsoft\.com'
            $out | Should -Match '--tsmode RFC3161'
            $out | Should -Match '-jar jsign-test\.jar'
        }

        It 'finds .exe, .dll and .pyd files recursively and skips other files' {
            $out = Invoke-Captured $AzureScript @{ Path = @($App) }
            ([regex]::Matches($out, 'DRYRUN sign ')).Count | Should -Be 4
            $out | Should -Match 'nested\.dll'
            $out | Should -Not -Match 'readme\.txt'
        }

        It 'signs a file named directly whatever its extension' {
            $out = Invoke-Captured $AzureScript @{ Path = @($Named) }
            $out | Should -Match 'DRYRUN sign .*makensis-temp\.tmp'
        }

        It 'leaves already signed files alone' {
            $global:CosmyxTestSignatures['lib.dll'] = New-Signature 'CN=Vendor'
            $out = Invoke-Captured $AzureScript @{ Path = @($App) }
            $out | Should -Match '3 of 4 files to sign'
            $out | Should -Not -Match 'DRYRUN sign .*lib\.dll'
        }

        It 'does nothing when every file is signed' {
            foreach ($name in 'app.exe', 'lib.dll', 'mod.pyd', 'nested.dll') {
                $global:CosmyxTestSignatures[$name] = New-Signature $Subject
            }
            $out = Invoke-Captured $AzureScript @{ Path = @($App) }
            $out | Should -Match '0 of 4 files to sign'
            $out | Should -Not -Match 'TRUSTEDSIGNING'
        }

        It 'copies a file from the reuse record instead of signing it again' {
            $signedCopy = Join-Path $TestDrive 'signed-app.exe'
            Set-Content -LiteralPath $signedCopy -Value 'signed'
            $global:CosmyxTestSignatures['signed-app.exe'] = New-Signature $Subject
            $hash = (Get-FileHash -LiteralPath (Join-Path $App 'app.exe') -Algorithm SHA256).Hash
            $record = Join-Path $TestDrive 'record.json'
            @{ $hash = $signedCopy } | ConvertTo-Json | Set-Content -LiteralPath $record -Encoding UTF8
            $env:ORCA_SIGN_REUSE = $record
            $out = Invoke-Captured $AzureScript @{ Path = @($App) }
            $out | Should -Match 'DRYRUN copy .*signed-app\.exe'
            $out | Should -Match '1 of them copied'
            $out | Should -Not -Match 'DRYRUN sign .*app\.exe'
        }

        It 'does not reuse a file signed by another subject' {
            $signedCopy = Join-Path $TestDrive 'other-app.exe'
            Set-Content -LiteralPath $signedCopy -Value 'other'
            $global:CosmyxTestSignatures['other-app.exe'] = New-Signature 'CN=Someone Else'
            $hash = (Get-FileHash -LiteralPath (Join-Path $App 'app.exe') -Algorithm SHA256).Hash
            $record = Join-Path $TestDrive 'record-other.json'
            @{ $hash = $signedCopy } | ConvertTo-Json | Set-Content -LiteralPath $record -Encoding UTF8
            $env:ORCA_SIGN_REUSE = $record
            $out = Invoke-Captured $AzureScript @{ Path = @($App) }
            $out | Should -Match '0 of them copied'
            $out | Should -Match 'DRYRUN sign .*app\.exe'
        }

        It 'never prints the access token' {
            $env:COSMYX_SIGN_TOKEN = 'secret-token-value'
            $out = Invoke-Captured $AzureScript @{ Path = @($App) }
            $out | Should -Not -Match 'secret-token-value'
        }

        It 'fails on a path that does not exist' {
            { & $AzureScript -Path (Join-Path $TestDrive 'missing') *>&1 | Out-Null } | Should -Throw '*does not exist*'
        }

        It 'fails when <Variable> is not set' -ForEach @(
            @{ Variable = 'COSMYX_SIGN_ENDPOINT' }, @{ Variable = 'COSMYX_SIGN_ACCOUNT' },
            @{ Variable = 'COSMYX_SIGN_PROFILE' }, @{ Variable = 'ORCA_SIGN_JSIGN' }
        ) {
            [Environment]::SetEnvironmentVariable($Variable, $null)
            { & $AzureScript -Path $App *>&1 | Out-Null } | Should -Throw "*$Variable is not set*"
        }
    }

    Context 'sign_windows_azure.ps1 signing' {
        It 'needs COSMYX_SIGN_TOKEN outside a dry run' {
            $env:COSMYX_SIGN_DRYRUN = $null
            { & $AzureScript -Path $App *>&1 | Out-Null } | Should -Throw '*COSMYX_SIGN_TOKEN is not set*'
        }

        It 'fails clearly when the token has expired and cannot be refreshed' {
            $env:COSMYX_SIGN_DRYRUN = $null
            $env:COSMYX_SIGN_TOKEN = 'old-token'
            $env:COSMYX_SIGN_TOKEN_EXPIRES = '1'
            function global:az { $global:LASTEXITCODE = 1 }
            try {
                { & $AzureScript -Path $App *>&1 | Out-Null } | Should -Throw '*could not be refreshed*'
            } finally {
                Remove-Item -Path Function:\az -ErrorAction SilentlyContinue
            }
        }
    }

    Context 'sign_windows_azure.ps1 -Verify' {
        BeforeEach {
            $env:COSMYX_SIGN_DRYRUN = $null
        }

        It 'passes when every file is signed and ours are timestamped' {
            $global:CosmyxTestSignatures['app.exe'] = New-Signature $Subject
            $global:CosmyxTestSignatures['lib.dll'] = New-Signature 'CN=Vendor'
            $global:CosmyxTestSignatures['mod.pyd'] = New-Signature $Subject
            $global:CosmyxTestSignatures['nested.dll'] = New-Signature $Subject
            $global:CosmyxTestSignatures['makensis-temp.tmp'] = New-Signature $Subject
            $out = Invoke-Captured $AzureScript @{ Path = @($App, $Named); Verify = $true }
            $out | Should -Match 'All 5 files are signed, 4 of them with'
        }

        It 'fails on an unsigned file' {
            $global:CosmyxTestSignatures['app.exe'] = New-Signature $Subject
            { & $AzureScript -Path $App -Verify *>&1 | Out-Null } | Should -Throw '*failed the signature check*'
        }

        It 'fails on a named file signed by another subject' {
            $global:CosmyxTestSignatures['makensis-temp.tmp'] = New-Signature 'CN=Vendor'
            { & $AzureScript -Path $Named -Verify *>&1 | Out-Null } | Should -Throw '*1 of 1 files failed*'
        }

        It 'fails on our signature without a timestamp' {
            $global:CosmyxTestSignatures['makensis-temp.tmp'] = New-Signature $Subject $false
            { & $AzureScript -Path $Named -Verify *>&1 | Out-Null } | Should -Throw '*1 of 1 files failed*'
        }

        It 'fails on a damaged signature' {
            $global:CosmyxTestSignatures['makensis-temp.tmp'] = New-Signature $Subject $true 'HashMismatch'
            { & $AzureScript -Path $Named -Verify *>&1 | Out-Null } | Should -Throw '*1 of 1 files failed*'
        }

        It 'needs COSMYX_SIGN_SUBJECT' {
            $env:COSMYX_SIGN_SUBJECT = $null
            { & $AzureScript -Path $Named -Verify *>&1 | Out-Null } | Should -Throw '*COSMYX_SIGN_SUBJECT is not set*'
        }
    }

    Context 'scripts/sign_windows.ps1 dispatch' {
        It 'hands over to the Azure script when COSMYX_SIGN_BACKEND is azure' {
            $env:COSMYX_SIGN_BACKEND = 'azure'
            $out = Invoke-Captured $UpstreamScript @{ Path = @($App) }
            $out | Should -Match '--storetype TRUSTEDSIGNING'
        }

        It 'passes -Verify through' {
            $env:COSMYX_SIGN_BACKEND = 'azure'
            $env:COSMYX_SIGN_DRYRUN = $null
            $global:CosmyxTestSignatures['makensis-temp.tmp'] = New-Signature $Subject
            $out = Invoke-Captured $UpstreamScript @{ Path = @($Named); Verify = $true }
            $out | Should -Match 'All 1 files are signed'
        }

        It 'keeps the upstream backend otherwise' {
            { & $UpstreamScript -Path $App *>&1 | Out-Null } | Should -Throw '*ORCA_SIGN_CERTFILE is not set*'
        }
    }
}
