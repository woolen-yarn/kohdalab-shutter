Option Explicit

Dim shell, fso, projectRoot, pythonwPath, uvPath, command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
If Not fso.FileExists(projectRoot & "\client\gui.py") Then
  projectRoot = "C:\pythonKernel\kohdalab-shutter"
End If

If Not fso.FileExists(projectRoot & "\client\gui.py") Then
  MsgBox "Could not find client\gui.py." & vbCrLf & projectRoot, vbCritical, "KohdaLab Shutter"
  WScript.Quit 1
End If

pythonwPath = projectRoot & "\.venv\Scripts\pythonw.exe"
uvPath = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.local\bin\uv.exe"

If fso.FileExists(pythonwPath) Then
  command = "cmd.exe /c cd /d """ & projectRoot & """ && set ""PYTHONPATH=" & projectRoot & ";%PYTHONPATH%"" && """ & pythonwPath & """ -m client.gui > gui_launcher.log 2>&1"
ElseIf fso.FileExists(uvPath) Then
  command = "cmd.exe /c cd /d """ & projectRoot & """ && set ""PYTHONPATH=" & projectRoot & ";%PYTHONPATH%"" && """ & uvPath & """ run pythonw -m client.gui > gui_launcher.log 2>&1"
Else
  command = "cmd.exe /c cd /d """ & projectRoot & """ && set ""PYTHONPATH=" & projectRoot & ";%PYTHONPATH%"" && uv run pythonw -m client.gui > gui_launcher.log 2>&1"
End If

shell.Run command, 0, False
