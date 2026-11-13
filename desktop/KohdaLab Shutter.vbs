Option Explicit
Dim shell, fso, projectRoot, appPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
projectRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
appPath = projectRoot & "\target\release\kohdalab-shutter-gui.exe"
If Not fso.FileExists(appPath) Then
  MsgBox "Rust GUI has not been built. Run cargo build --release --locked in:" & vbCrLf & projectRoot, vbCritical, "KohdaLab Shutter"
  WScript.Quit 1
End If
shell.CurrentDirectory = projectRoot
shell.Run """" & appPath & """", 1, False
