# Local runners set up

## Windows

```powershell

winget install --id Microsoft.PowerShell --source winget

Set-ExecutionPolicy RemoteSigned -Scope LocalMachine

Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

choco feature enable -n allowGlobalConfirmation

choco install visualstudio2022buildtools --package-parameters "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --includeOptional --passive --norestart"

choco install gzip
choco install libcurl
choco install openssl

Copy-Item "C:\Program Files\OpenSSL-Win64\lib\VC\x64\MD\*" -Destination "C:\Program Files\OpenSSL-Win64\lib\" -Force

git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg integrate install

.\vcpkg install curl[core,ssl]:x64-windows

$env:VCPKG_INSTALLATION_ROOT = "C:\Users\Shadow\Documents\vcpkg"

```

## Macos

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install git-lfs zstd

git lfs install
git lfs install --system
```
