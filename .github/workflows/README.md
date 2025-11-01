# Local runners set up

## Windows

```powershell
Set-ExecutionPolicy RemoteSigned -Scope LocalMachine

Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

choco feature enable -n allowGlobalConfirmation

choco install visualstudio2022buildtools --force --package-parameters "--add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.VC.CMake.Project --add Microsoft.VisualStudio.Component.Windows10SDK.19041 --includeRecommended --includeOptional --passive"


choco install gzip

winget search Microsoft.PowerShell
winget install --id Microsoft.PowerShell --source winget
```

## Macos

```sh
brew install git-lfs
```
