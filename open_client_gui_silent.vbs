Option Explicit

Dim shell, fso, projectDir, env, oldPythonPath, command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FileExists(projectDir & "\client\gui.py") Then
    projectDir = "C:\pythonKernel\kohdalab-shutter"
End If

If Not fso.FileExists(projectDir & "\client\gui.py") Then
    MsgBox "Could not find client\gui.py." & vbCrLf & projectDir, vbCritical, "Kohda Lab Shutter"
    WScript.Quit 1
End If

shell.CurrentDirectory = projectDir

Set env = shell.Environment("PROCESS")
oldPythonPath = env("PYTHONPATH")
If Len(oldPythonPath) > 0 Then
    env("PYTHONPATH") = projectDir & ";" & oldPythonPath
Else
    env("PYTHONPATH") = projectDir
End If

command = "cmd.exe /c ""uv run pythonw -m client.gui"""
shell.Run command, 0, False
