Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = baseDir

env = "PATH"
nvidiaPath = baseDir & "\.venv\Lib\site-packages\nvidia\cublas\bin;" & baseDir & "\.venv\Lib\site-packages\nvidia\cudnn\bin;"
shell.Environment("Process")(env) = nvidiaPath & shell.Environment("Process")(env)

shell.Run """" & baseDir & "\.venv\Scripts\pythonw.exe"" """ & baseDir & "\src\main.py""", 0, False
