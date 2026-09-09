# Requiere ser ejecutado como Administrador
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Este script debe ejecutarse como Administrador."
    Write-Warning "Por favor, haz clic derecho en el archivo y selecciona 'Ejecutar con PowerShell', o abre una terminal como Administrador."
    Pause
    exit
}

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host " OPTIMIZACION PARA LABORATORIO - FASE 6"        -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# ─── 1. Desactivar Windows Defender ──────────────────────────────────
Write-Host "[1/5] Desactivando Windows Defender..." -ForegroundColor Yellow

# Registry: desactivar Defender permanentemente
try {
    New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender" -Force | Out-Null
    New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender" `
        -Name "DisableAntiSpyware" -Value 1 -PropertyType DWord -Force | Out-Null
    Write-Host "   -> Defender desactivado via registro" -ForegroundColor Green
} catch {
    Write-Host "   -> Error en registro: $_" -ForegroundColor Red
}

# Desactivar proteccion en tiempo real
try {
    Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction Stop
    Set-MpPreference -DisableBehaviorMonitoring $true
    Set-MpPreference -DisableBlockAtFirstSeen $true
    Set-MpPreference -DisableIOAVProtection $true
    Set-MpPreference -DisablePrivacyMode $true
    Set-MpPreference -SignatureDisableUpdateOnStartupWithoutEngine $true
    Set-MpPreference -DisableArchiveScanning $true
    Set-MpPreference -DisableCatchupFullScan $true
    Set-MpPreference -DisableCatchupQuickScan $true
    Set-MpPreference -DisableEmailScanning $true
    Set-MpPreference -DisableRealtimeMonitoring $true
    Write-Host "   -> Proteccion en tiempo real desactivada" -ForegroundColor Green
} catch {
    Write-Host "   -> Error en MpPreference: $_" -ForegroundColor Red
}

# Desactivar tareas programadas de Defender
$defenderTasks = @(
    "\Microsoft\Windows\Windows Defender\Windows Defender Cache Maintenance",
    "\Microsoft\Windows\Windows Defender\Windows Defender Cleanup",
    "\Microsoft\Windows\Windows Defender\Windows Defender Scheduled Scan",
    "\Microsoft\Windows\Windows Defender\Windows Defender Verification"
)
foreach ($t in $defenderTasks) {
    Disable-ScheduledTask -TaskPath (Split-Path $t) -TaskName (Split-Path $t -Leaf) -ErrorAction SilentlyContinue | Out-Null
    Write-Host "   -> Tarea desactivada: $t" -ForegroundColor DarkGray
}

# Detener servicio de Defender
Stop-Service -Name "WinDefend" -Force -ErrorAction SilentlyContinue
Set-Service -Name "WinDefend" -StartupType Disabled -ErrorAction SilentlyContinue
Stop-Service -Name "WdBoot" -Force -ErrorAction SilentlyContinue
Stop-Service -Name "WdFilter" -Force -ErrorAction SilentlyContinue
Stop-Service -Name "WdNisDrv" -Force -ErrorAction SilentlyContinue
Stop-Service -Name "WdNisSvc" -Force -ErrorAction SilentlyContinue
Stop-Service -Name "WinDefend" -Force -ErrorAction SilentlyContinue
Write-Host "   -> Servicio WinDefend detenido" -ForegroundColor Green

# ─── 2. Servicios innecesarios ────────────────────────────────────────
Write-Host "[2/5] Desactivando servicios innecesarios..." -ForegroundColor Yellow

$services = @(
    "WMPNetworkSvc",   # Windows Media Player Network Sharing
    "MapsBroker",      # Downloaded Maps Manager
    "lfsvc",           # Geolocation Service
    "upnphost",        # UPnP Device Host
    "SSDPSRV",         # SSDP Discovery
    "TrkWks",          # Distributed Link Tracking Client
    "XblAuthManager",  # Xbox Live Auth Manager
    "XblGameSave",     # Xbox Live Game Save
    "XboxNetApiSvc",   # Xbox Live Networking
    "DiagTrack",       # Connected User Experiences and Telemetry
    "dmwappushservice",# WAP Push Message Routing
    "WSearch",         # Windows Search (si es HDD, libera mucha CPU)
    "RemoteRegistry",  # Remote Registry
    "SysMain",         # SysMain (Superfetch) util si es SSD, contraproducente en HDD
    "TabletInputService", # Touch Keyboard
    "WlanSvc",         # WiFi (desactivar solo si es cableada)
    "FontCache",       # Windows Font Cache
    "PcaSvc",          # Program Compatibility Assistant
    "wscsvc",          # Security Center
    "SecurityHealthService", # Windows Security Health
    "Themes",          # Temas visuales (libera ~20-40MB)
    "BITS",            # Background Intelligent Transfer (usado por Windows Update)
    "wuauserv",        # Windows Update
    "UsoSvc",          # Update Session Orchestrator
    "DoSvc"            # Delivery Optimization (P2P updates)
)

# Preguntar por WiFi y temas
Write-Host "   NOTA: WlanSvc (WiFi) se desactiva solo si usas cable de red." -ForegroundColor DarkYellow
Write-Host "   NOTA: Themes se desactiva, pierdes transparencia/efectos." -ForegroundColor DarkYellow

foreach ($s in $services) {
    try {
        $current = Get-Service -Name $s -ErrorAction Stop
        Set-Service -Name $s -StartupType Disabled -ErrorAction SilentlyContinue
        Stop-Service -Name $s -Force -ErrorAction SilentlyContinue
        Write-Host "   -> $s desactivado" -ForegroundColor DarkGray
    } catch {
        # Service doesn't exist, skip silently
    }
}

# ─── 3. Tareas programadas ────────────────────────────────────────────
Write-Host "[3/5] Desactivando tareas programadas..." -ForegroundColor Yellow

$taskPaths = @(
    # Windows Update
    "\Microsoft\Windows\WindowsUpdate",
    "\Microsoft\Windows\UpdateOrchestrator",
    
    # Mantenimiento
    "\Microsoft\Windows\DiskDiagnostic",
    "\Microsoft\Windows\DiskCleanup",
    "\Microsoft\Windows\Maintenance",
    "\Microsoft\Windows\Registry",
    "\Microsoft\Windows\Speech",
    "\Microsoft\Windows\Application Experience",
    "\Microsoft\Windows\Customer Experience Improvement Program",
    "\Microsoft\Windows\Power Efficiency Diagnostics",
    "\Microsoft\Windows\Windows Error Reporting",
    "\Microsoft\Windows\FileHistory",
    "\Microsoft\Windows\Chkdsk",
    "\Microsoft\Windows\Defrag",
    "\Microsoft\Windows\Location",
    "\Microsoft\Windows\Media Center",
    "\Microsoft\Windows\Offline Files",
    "\Microsoft\Windows\PI",
    "\Microsoft\Windows\PrintDiagnostics",
    "\Microsoft\Windows\Recovery",
    "\Microsoft\Windows\RetailDemo",
    "\Microsoft\Windows\Shell\FamilySafety",
    "\Microsoft\Windows\SyncCenter",
    "\Microsoft\Windows\SystemRestore",
    "\Microsoft\Windows\TextServicesFramework",
    "\Microsoft\Windows\Time Zone",
    "\Microsoft\Windows\TPM",
    "\Microsoft\Windows\WDI",
    "\Microsoft\Windows\Windows Filtering Platform",
    "\Microsoft\Windows\Work Folders",
    
    # Xbox
    "\Microsoft\XblGameSave",
    
    # OneDrive (no lo borra, solo desactiva tareas)
    "\Microsoft\Office"
)

foreach ($tp in $taskPaths) {
    try {
        $tasks = Get-ScheduledTask -TaskPath "$tp\" -ErrorAction SilentlyContinue
        foreach ($t in $tasks) {
            if ($t.State -ne 'Disabled') {
                Disable-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath -ErrorAction SilentlyContinue | Out-Null
                Write-Host "   -> Tarea desactivada: $($t.TaskName)" -ForegroundColor DarkGray
            }
        }
    } catch {
        # Task path doesn't exist, skip
    }
}

# ─── 4. Servicios opcionales de terceros ──────────────────────────────
Write-Host "[4/5] Deteniendo servicios de terceros no esenciales..." -ForegroundColor Yellow

$thirdParty = @(
    "Lightshot",           # Screenshot tool
    "E_YATIYIE",           # EPSON printer
    "AdskAccessService",   # Autodesk licensing
    "AdskAccessServiceHost",
    "AdskLicensingService",
    "FNPLicensingService", # FlexNet licensing
    "FNPLicensingService64",
    "sntlsrtsrvr",         # Sentinel licensing
    "sntlkeyssrvr",
    "spnsrvnt",
    "FileCoAuth",          # Office file sync
    "nvxdsync",            # NVIDIA sync
    "EEventManager",       # EPSON event manager
    "cer_service"          # Certificate services (3rd party)
)

foreach ($s in $thirdParty) {
    try {
        Stop-Service -Name $s -Force -ErrorAction SilentlyContinue
        Set-Service -Name $s -StartupType Disabled -ErrorAction SilentlyContinue
        Write-Host "   -> $s detenido" -ForegroundColor DarkGray
    } catch {
        Stop-Process -Name $s -Force -ErrorAction SilentlyContinue
    }
}

# ─── 5. Limpieza de memoria ──────────────────────────────────────────
Write-Host "[5/5] Forzando limpieza de memoria..." -ForegroundColor Yellow

# Limpiar cache de DNS
ipconfig /flushdns 2>$null | Out-Null
Write-Host "   -> DNS cache limpiado" -ForegroundColor DarkGray

# Liberar memoria de procesos en segundo plano
try {
    # Clear working sets de procesos del sistema (no los mata, solo libera RAM no usada)
    Get-Process | Where-Object { $_.WorkingSet64 -gt 50MB -and $_.ProcessName -notlike "OpenCode" -and $_.ProcessName -notlike "python*" -and $_.ProcessName -notlike "ngrok*" -and $_.ProcessName -notlike "explorer" -and $_.ProcessName -notlike "OneDrive*" -and $_.ProcessName -notlike "GoogleDrive*" } | ForEach-Object {
        try {
            [System.GC]::Collect()
            [System.GC]::WaitForPendingFinalizers()
            if ([System.Environment]::OSVersion.Version.Major -ge 10) {
                # EmptyWorkingSet en Windows
                $_.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::Idle
            }
        } catch {}
    }
    Write-Host "   -> Working sets optimizados" -ForegroundColor DarkGray
} catch {}

[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host " OPTIMIZACION COMPLETADA"                       -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Resumen:" -ForegroundColor White
Write-Host "  - Windows Defender: DESACTIVADO" -ForegroundColor Green
Write-Host "  - Servicios innecesarios: DESACTIVADOS" -ForegroundColor Green
Write-Host "  - Tareas programadas: DESACTIVADAS" -ForegroundColor Green
Write-Host "  - Servicios de terceros: DETENIDOS" -ForegroundColor Green
Write-Host ""
Write-Host "RECOMENDACION: Reinicia el equipo para liberar toda la RAM." -ForegroundColor Cyan
Write-Host "Despues de reiniciar, ejecuta este comando para verificar:" -ForegroundColor Cyan
Write-Host "  Get-Process | Sort-Object WorkingSet64 -Desc | Select Name, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet64/1MB,1)}} -First 10" -ForegroundColor Gray
Pause
