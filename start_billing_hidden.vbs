Option Explicit
Dim shell, fso, scriptDir, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
command = Chr(34) & scriptDir & "\start_billing_background.bat" & Chr(34)
shell.Run command, 0, False
