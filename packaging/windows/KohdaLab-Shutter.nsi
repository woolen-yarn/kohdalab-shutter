; KohdaLab Shutter Windows installer.
; SPDX-License-Identifier: MIT
;
; Required compile-time definitions from scripts/build_windows_installer.py:
; PAYLOAD_INCLUDE, OUTPUT_FILE, VERSION, VERSION_FILE.

Unicode true
SetCompressor /SOLID zlib
SetDatablockOptimize on

!ifndef PAYLOAD_INCLUDE
  !error "PAYLOAD_INCLUDE must name the generated payload include"
!endif
!ifndef OUTPUT_FILE
  !error "OUTPUT_FILE must name Setup.exe"
!endif
!ifndef VERSION
  !error "VERSION must be set"
!endif
!ifndef VERSION_FILE
  !error "VERSION_FILE must be a four-part numeric version"
!endif

!include "MUI2.nsh"
!include "x64.nsh"
!include "LogicLib.nsh"
!include "${PAYLOAD_INCLUDE}"

Name "KohdaLab Shutter ${VERSION}"
OutFile "${OUTPUT_FILE}"
InstallDir "$PROGRAMFILES64\Kohdalab\KohdaLab Shutter"
RequestExecutionLevel admin
ShowInstDetails show
ShowUninstDetails show
BrandingText "KohdaLab Shutter"
Icon "${__FILEDIR__}\..\..\assets\shutter.ico"
UninstallIcon "${__FILEDIR__}\..\..\assets\shutter.ico"

VIProductVersion ${VERSION_FILE}
VIAddVersionKey /LANG=1033 "ProductName" "KohdaLab Shutter"
VIAddVersionKey /LANG=1033 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1033 "CompanyName" "Kohdalab"
VIAddVersionKey /LANG=1033 "FileDescription" "KohdaLab Shutter Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Copyright Kohdalab contributors"

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "KohdaLab Shutter Setup"
!define MUI_WELCOMEPAGE_TEXT "This installs KohdaLab Shutter for all Windows users. Existing settings are kept."
!define MUI_FINISHPAGE_TITLE "KohdaLab Shutter is ready"
!define MUI_FINISHPAGE_TEXT "Start KohdaLab Shutter from the Start menu or desktop shortcut."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "KohdaLab Shutter requires 64-bit Windows."
    SetErrorLevel 1
    Abort
  ${EndIf}
  SetRegView 64
  ; Do not accept a registry value or /D override for this application.
  StrCpy $INSTDIR "$PROGRAMFILES64\Kohdalab\KohdaLab Shutter"
  SetShellVarContext all
FunctionEnd

Function un.onInit
  SetRegView 64
  ; NSIS may launch a temporary uninstaller copy, but retains the original
  ; install path in $INSTDIR. Refuse caller-supplied removal paths.
  StrCpy $0 $INSTDIR
  StrCpy $INSTDIR "$PROGRAMFILES64\Kohdalab\KohdaLab Shutter"
  SetShellVarContext all
  ${If} $0 != ""
  ${AndIf} $0 != $INSTDIR
    IfSilent reject
    MessageBox MB_ICONSTOP|MB_OK "KohdaLab Shutter can only be removed from its installed location."
reject:
    SetErrorLevel 1
    Abort
  ${EndIf}
FunctionEnd

; Request an exclusive write handle before changing an existing installation.
; This detects a running or otherwise locked process without terminating it.
Function EnsureShutterIsClosed
  IfFileExists "$INSTDIR\kohdalab-shutter-gui.exe" 0 install_probe_cli
  System::Call 'kernel32::CreateFileW(w "$INSTDIR\kohdalab-shutter-gui.exe", i 0x40000000, i 0, p 0, i 3, i 0, p 0) p.r0'
  ${If} $0 == -1
    IfSilent install_abort_gui
    MessageBox MB_ICONEXCLAMATION|MB_OK "Close KohdaLab Shutter before installing or updating it."
install_abort_gui:
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::CloseHandle(p r0)'
install_probe_cli:
  IfFileExists "$INSTDIR\kohdalab-shutter.exe" 0 install_done
  System::Call 'kernel32::CreateFileW(w "$INSTDIR\kohdalab-shutter.exe", i 0x40000000, i 0, p 0, i 3, i 0, p 0) p.r0'
  ${If} $0 == -1
    IfSilent install_abort_cli
    MessageBox MB_ICONEXCLAMATION|MB_OK "Close KohdaLab Shutter before installing or updating it."
install_abort_cli:
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::CloseHandle(p r0)'
install_done:
FunctionEnd

Function un.EnsureShutterIsClosed
  IfFileExists "$INSTDIR\kohdalab-shutter-gui.exe" 0 uninstall_probe_cli
  System::Call 'kernel32::CreateFileW(w "$INSTDIR\kohdalab-shutter-gui.exe", i 0x40000000, i 0, p 0, i 3, i 0, p 0) p.r0'
  ${If} $0 == -1
    IfSilent uninstall_abort_gui
    MessageBox MB_ICONEXCLAMATION|MB_OK "Close KohdaLab Shutter before uninstalling it."
uninstall_abort_gui:
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::CloseHandle(p r0)'
uninstall_probe_cli:
  IfFileExists "$INSTDIR\kohdalab-shutter.exe" 0 uninstall_done
  System::Call 'kernel32::CreateFileW(w "$INSTDIR\kohdalab-shutter.exe", i 0x40000000, i 0, p 0, i 3, i 0, p 0) p.r0'
  ${If} $0 == -1
    IfSilent uninstall_abort_cli
    MessageBox MB_ICONEXCLAMATION|MB_OK "Close KohdaLab Shutter before uninstalling it."
uninstall_abort_cli:
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::CloseHandle(p r0)'
uninstall_done:
FunctionEnd

Section "KohdaLab Shutter" SecMain
  Call EnsureShutterIsClosed
  !insertmacro InstallPayload
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\KohdaLab\KohdaLab Shutter" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "DisplayName" "KohdaLab Shutter"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "Publisher" "Kohdalab"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "DisplayIcon" "$INSTDIR\kohdalab-shutter-gui.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "URLInfoAbout" "https://github.com/woolen-yarn/kohdalab-shutter"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter" "NoRepair" 1
  CreateDirectory "$SMPROGRAMS\KohdaLab"
  CreateShortcut "$SMPROGRAMS\KohdaLab\KohdaLab Shutter.lnk" "$INSTDIR\kohdalab-shutter-gui.exe" "" "$INSTDIR\kohdalab-shutter-gui.exe" 0
  CreateShortcut "$SMPROGRAMS\KohdaLab\KohdaLab Shutter Demo.lnk" "$INSTDIR\kohdalab-shutter-gui.exe" "--demo" "$INSTDIR\kohdalab-shutter-gui.exe" 0
  CreateShortcut "$DESKTOP\KohdaLab Shutter.lnk" "$INSTDIR\kohdalab-shutter-gui.exe" "" "$INSTDIR\kohdalab-shutter-gui.exe" 0
SectionEnd

Section "Uninstall"
  Call un.EnsureShutterIsClosed
  Delete "$SMPROGRAMS\KohdaLab\KohdaLab Shutter.lnk"
  Delete "$SMPROGRAMS\KohdaLab\KohdaLab Shutter Demo.lnk"
  Delete "$DESKTOP\KohdaLab Shutter.lnk"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KohdaLabShutter"
  DeleteRegKey HKLM "Software\KohdaLab\KohdaLab Shutter"
  !insertmacro RemovePayload
  Delete /REBOOTOK "$INSTDIR\Uninstall.exe"
  RMDir "$SMPROGRAMS\KohdaLab"
  RMDir "$INSTDIR"
SectionEnd
