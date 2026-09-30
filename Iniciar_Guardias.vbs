Set WshShell = CreateObject("WScript.Shell")
Dim ScriptDir
ScriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
WshShell.Run """" & ScriptDir & "dist\Guardias\Guardias.exe""", 0, False
