Set UAC = CreateObject("Shell.Application")
UAC.ShellExecute "powershell.exe", "-ExecutionPolicy Bypass -NoProfile -Command ""& { Set-ExecutionPolicy Bypass -Scope Process; & 'C:\Users\PLI INGENIERIA\Desktop\ELIMINADOR POTENTE REVO\SUPREMA DE GASTOS\OptimizarLaboratorio.ps1' }""", "", "runas", 1
