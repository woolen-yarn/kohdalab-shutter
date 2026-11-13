# Requires a disposable Windows user profile. Installs, updates, then uninstalls
# the supplied machine-wide Setup.exe and verifies the Windows integration points.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Installer,
 [Parameter(Mandatory=$true)][ValidatePattern('^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$')][string]$Version
)
$ErrorActionPreference='Stop'
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run this disposable-machine test in an elevated PowerShell.'}
$installerPath=[IO.Path]::GetFullPath($Installer)
if(!(Test-Path -LiteralPath $installerPath -PathType Leaf)){throw "Installer was not found: $installerPath"}
$installed=Join-Path $env:ProgramFiles 'Kohdalab\KohdaLab Shutter'
$uninstallKey='HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter'
$menu=Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'KohdaLab\KohdaLab Shutter.lnk'
$demoMenu=Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'KohdaLab\KohdaLab Shutter Demo.lnk'
$desktop=Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) 'KohdaLab Shutter.lnk'
if((Test-Path -LiteralPath $installed) -or (Test-Path -LiteralPath $uninstallKey) -or (Test-Path -LiteralPath $menu) -or (Test-Path -LiteralPath $demoMenu) -or (Test-Path -LiteralPath $desktop)){
 throw 'Refusing to run installer verification over an existing KohdaLab Shutter installation.'
}
function Invoke-Setup([string]$Path,[string[]]$Arguments=@('/S')) {
 $result=Start-Process -FilePath $Path -ArgumentList $Arguments -Wait -PassThru
 if($result.ExitCode -ne 0){throw "Setup returned exit code $($result.ExitCode)"}
}
function Invoke-SetupExpectFailure([string]$Path,[string[]]$Arguments=@('/S')) {
 $result=Start-Process -FilePath $Path -ArgumentList $Arguments -Wait -PassThru
 if($result.ExitCode -eq 0){throw 'Setup unexpectedly succeeded while the application file was locked.'}
}
$redirect=Join-Path $env:TEMP ('KohdaLab-Shutter-installer-redirect-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $redirect | Out-Null
$redirectSentinel=Join-Path $redirect 'must-not-be-removed.txt'
[IO.File]::WriteAllText($redirectSentinel,'keep')
$productKey='HKLM:\Software\KohdaLab\KohdaLab Shutter'
if(Test-Path -LiteralPath $productKey){throw 'Refusing to change an existing Shutter product registration.'}
New-Item -Path $productKey -Force | Out-Null
New-ItemProperty -Path $productKey -Name InstallLocation -Value $redirect -PropertyType String -Force | Out-Null
Invoke-Setup $installerPath @('/S',("/D="+$redirect))
if(!(Test-Path -LiteralPath $redirectSentinel)){throw 'Installer accepted a redirected installation path.'}
foreach($path in @((Join-Path $installed 'kohdalab-shutter-gui.exe'),(Join-Path $installed 'kohdalab-shutter.exe'),(Join-Path $installed 'LICENSE'),(Join-Path $installed 'licenses'))){if(!(Test-Path -LiteralPath $path)){throw "Missing installed payload: $path"}}
if((& (Join-Path $installed 'kohdalab-shutter.exe') --version) -notmatch [Regex]::Escape($Version)){throw 'Installed CLI version did not match Setup version.'}
if(!(Test-Path -LiteralPath $menu)){throw 'Start menu shortcut was not created.'}
if(!(Test-Path -LiteralPath $demoMenu)){throw 'Demo Start menu shortcut was not created.'}
if(!(Test-Path -LiteralPath $desktop)){throw 'Desktop shortcut was not created.'}
if((Get-ItemProperty -LiteralPath $uninstallKey).DisplayVersion -ne $Version){throw 'Apps uninstall version did not match.'}
$userFile=Join-Path $installed 'kept-by-user.txt'
[IO.File]::WriteAllText($userFile,'keep')
$configDirectory=Join-Path $env:USERPROFILE '.kohdalab\shutter'
New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
$configFile=Join-Path $configDirectory ('installer-validation-'+[Guid]::NewGuid().ToString('N')+'.txt')
[IO.File]::WriteAllText($configFile,'keep')
$lock=$null
try {
 $lock=[IO.File]::Open((Join-Path $installed 'kohdalab-shutter-gui.exe'),[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None)
 Invoke-SetupExpectFailure $installerPath
 if(!(Test-Path -LiteralPath $userFile)){throw 'A failed locked update changed the installation.'}
 if((Get-ItemProperty -LiteralPath $uninstallKey).DisplayVersion -ne $Version){throw 'A failed locked update changed Apps registration.'}
} finally {if($lock){$lock.Dispose()}}
Invoke-Setup $installerPath
if(!(Test-Path -LiteralPath $userFile)){throw 'Reinstall removed a user-created file.'}
if(!(Test-Path -LiteralPath $configFile)){throw 'Reinstall removed a user configuration file.'}
$uninstaller=Join-Path $installed 'Uninstall.exe'
Invoke-Setup $uninstaller
if(Test-Path -LiteralPath $uninstallKey){throw 'Apps uninstall entry was not removed.'}
if(Test-Path -LiteralPath $menu){throw 'Start menu shortcut was not removed.'}
if(Test-Path -LiteralPath $demoMenu){throw 'Demo Start menu shortcut was not removed.'}
if(Test-Path -LiteralPath $desktop){throw 'Desktop shortcut was not removed.'}
if(Test-Path -LiteralPath (Join-Path $installed 'kohdalab-shutter-gui.exe')){throw 'GUI executable was not removed.'}
if(!(Test-Path -LiteralPath $userFile)){throw 'Uninstall removed a user-created file.'}
if(!(Test-Path -LiteralPath $configFile)){throw 'Uninstall removed a user configuration file.'}
Remove-Item -LiteralPath $userFile -Force
if(Test-Path -LiteralPath $installed){Remove-Item -LiteralPath $installed -Force}
Remove-Item -LiteralPath $configFile -Force
if(!(Get-ChildItem -LiteralPath $configDirectory -Force)){Remove-Item -LiteralPath $configDirectory -Force}
Remove-Item -LiteralPath $redirectSentinel -Force
Remove-Item -LiteralPath $redirect -Force
Write-Output "Verified install, reinstall, and uninstall of KohdaLab Shutter $Version."
