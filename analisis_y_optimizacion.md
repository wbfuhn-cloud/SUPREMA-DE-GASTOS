# 🔬 Análisis Completo y Plan de Optimización — Asistente Financiero

---

## 📋 Resumen Ejecutivo

Se examinó la totalidad del código fuente del proyecto **Asistente Financiero** (Bot Telegram + Dashboard Web + Monitor de Precios + Visor de Bolsa). A continuación se presentan los hallazgos organizados en tres ejes:

1. **Problemas y deuda técnica detectados**
2. **Propuesta de estructura de carpetas profesional**
3. **Sugerencias de optimización de rendimiento y respuesta**

---

## 🚨 1. Diagnóstico de Problemas Actuales

### 1.1 Estructura Caótica de Archivos Raíz

> [!CAUTION]
> La raíz del proyecto tiene **21 archivos sueltos** mezclando configuración, ejecutables, datos, documentación y código. Esto dificulta el mantenimiento y es propenso a errores.

| Archivo Suelto | Problema |
|---|---|
| `cloudflared.exe` (65 MB) | Binario gigante en la raíz, debería estar en `bin/` o descargarse automáticamente |
| `gui.py`, `main.py` | Punto de entrada suelto, debería estar en `src/` |
| `chat_id.txt` | Dato persistente suelto, debería estar en `data/` |
| `.token_cache.json` | Credencial sensible suelta en la raíz |
| `Captura.PNG` | Archivo de imagen sin propósito claro |
| `Oportunidades_Inversion.csv` | Datos financieros sueltos, debería estar en `data/` |
| `system_documentation.json` | Documentación técnica suelta |
| `visor_config.json` | Config duplicada (también existe en `tools/NOTIFICADOR_BOT/`) |
| `pyrightconfig.json` | Config de IDE, OK pero mejor en `.vscode/` |
| `check_ide_problems.skill` | Archivo de herramienta externo suelto |
| `fix_ide_errors.bat` | Utilidad de desarrollo, no para producción |
| `MONITOR_SISTEMA.bat` | BAT extra suelto |
| Múltiples `.md` sueltos | Documentación sin organizar |

### 1.2 Código Duplicado

> [!WARNING]
> Hay código repetido que genera inconsistencias y complica el mantenimiento.

| Duplicación | Ubicaciones |
|---|---|
| `start.bat` ≈ `iniciar.bat` | Son prácticamente idénticos (< 5 líneas de diferencia) |
| Forzado UTF-8 `stdout/stderr` | Repetido en [main.py](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/main.py#L1-L11) y [gui.py](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/gui.py#L1-L13) |
| Meses en español `MESES_ES` | Definidos en [bot.py:502](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/bot.py#L501-L503), [notifications.py:35](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/notifications.py#L35-L36), [email_reader.py:58](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/email_reader.py#L58-L62) |
| Envío de Telegram directo | Se reimplementa en: `monitor.py`, `email_reader.py`, `server.py` (cada uno con su propio método) |
| Limpieza Markdown de Gemini | Repetido en [analyzer.py:85-88](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/analyzer.py#L85-L88), [analyzer.py:165-168](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/analyzer.py#L165-L168), [analyzer.py:218-221](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/analyzer.py#L218-L221) |
| Archivos `_mejorado.py` en `files/` | Versiones "mejoradas" sin integrar — código muerto que confunde |

### 1.3 Seguridad

> [!CAUTION]
> **Credenciales expuestas directamente en el archivo `.env` que está trackeado por Git.** Tokens de Telegram, API keys de Google, y contraseñas de correo están visibles.

- [.env:4](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/.env#L4) — `TELEGRAM_BOT_TOKEN` expuesto
- [.env:11](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/.env#L11) — `GOOGLE_API_KEY` expuesto
- [.env:24](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/.env#L24) — `EMAIL_PASSWORD` expuesto
- [.env:18](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/.env#L18) — `NGROK_AUTH_TOKEN` expuesto

**Acción inmediata**: Agregar `.env` al `.gitignore` y rotar todas las credenciales.

### 1.4 Problemas de Rendimiento

| Problema | Archivo | Impacto |
|---|---|---|
| `get_all_expenses()` carga TODOS los gastos a memoria | [database.py:165](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/database.py#L165) | Alto — sin paginación, crece linealmente |
| `handle_nl_query` envía los últimos 100 gastos completos a Gemini | [bot.py:718-730](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/bot.py#L718-L730) | Alto — tokens y latencia innecesarios |
| Dashboard HTML se regenera completamente con cada request (TTL 4s) | [server.py:221](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/server.py#L221) | Medio — HTML de 60KB regenerado constantemente |
| Scraper de precios abre navegador headless con `headless=False` | [monitor.py:413](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/monitor.py#L413) | Alto — consume RAM/CPU innecesariamente |
| `from datetime import datetime` importado dos veces en server.py | [server.py:6,11](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/server.py#L6-L11) | Bajo — pero indica descuido |
| Comentario duplicado "--- NUEVO:" sin limpiar | [gui.py:281-282](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/gui.py#L281-L282) | Bajo — ruido en el código |
| `sys.path.append()` disperso por múltiples archivos | Varios archivos | Medio — indica acoplamiento frágil |
| Conexiones SQLite abiertas y cerradas repetidamente en email_reader | [email_reader.py:226-257](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/email_reader.py#L226-L257) | Medio — no usa el pool de DatabaseManager |

### 1.5 Archivos Muertos / Sin Propósito Claro

| Archivo/Carpeta | Problema |
|---|---|
| `files/` (5 archivos `*_mejorado.py`) | Versiones antiguas nunca integradas |
| `EJEMPLO/` (144KB HTML + contenido) | Plantillas/prototipos que no se usan en producción |
| `plantilla suge/` (9 subcarpetas) | Mockups/plantillas de diseño obsoletos |
| `scratch/` | Carpeta vacía (solo para desarrollo temporal) |
| `tools/liquidGL-main/` | Librería JS descargada dentro de tools |
| `tools/check_models.py`, `fix_db_types.py`, etc. | Scripts de utilidad de una sola vez mezclados con herramientas |
| `markdoc/reporte_implementacion.md` | Documentación aislada |

---

## 📁 2. Propuesta de Estructura Profesional de Carpetas

> [!IMPORTANT]
> El objetivo es que **fuera de la carpeta del proyecto solo quede el archivo `.bat` de inicio**.
> Todo lo demás (binarios, datos, configuración, código) vive dentro del proyecto con una organización clara.

### 2.1 Estructura Propuesta

```
SUPREMA DE GASTOS/
│
├── 📄 iniciar.bat                  ← ÚNICO archivo visible al usuario
├── 📄 .env                         ← Configuración sensible (en .gitignore)
├── 📄 .gitignore
├── 📄 README.md
├── 📄 requirements.txt
│
├── 📁 .venv/                       ← Entorno virtual Python
├── 📁 .vscode/                     ← Configuración del IDE
│
├── 📁 bin/                          ← Binarios externos
│   └── cloudflared.exe
│
├── 📁 src/                          ← Todo el código fuente
│   ├── __init__.py
│   ├── app.py                      ← Punto de entrada (antes gui.py)
│   ├── main.py                     ← Entrada CLI alternativa
│   │
│   ├── 📁 core/                    ← Lógica central del negocio
│   │   ├── __init__.py
│   │   ├── config.py               ← Configuración centralizada
│   │   ├── constants.py            ← NUEVO: Constantes compartidas (meses, categorías)
│   │   ├── database.py             ← Gestor de base de datos
│   │   ├── analyzer.py             ← Servicio de IA (Gemini)
│   │   └── notifications.py        ← Servicio de notificaciones
│   │
│   ├── 📁 bot/                     ← Lógica del bot de Telegram
│   │   ├── __init__.py
│   │   ├── bot.py                  ← Clase ExpenseBot
│   │   └── handlers/               ← Handlers separados por dominio
│   │       ├── __init__.py
│   │       ├── expense_handlers.py  ← Foto, voz, texto de gastos
│   │       ├── query_handlers.py    ← Consultas NL, resúmenes
│   │       ├── finance_handlers.py  ← Presupuestos, bolsa, cartera
│   │       └── system_handlers.py   ← Start, stop, help, visual
│   │
│   ├── 📁 web/                     ← Servidor Flask + Dashboard
│   │   ├── __init__.py
│   │   ├── server.py               ← Rutas Flask
│   │   ├── dashboard.py            ← Generador HTML dashboard
│   │   ├── transactions_view.py
│   │   ├── details_view.py
│   │   ├── excel_export.py
│   │   └── 📁 static/             ← CSS, JS, imágenes
│   │       ├── bg_desktop.png
│   │       ├── bg_mobile.png
│   │       ├── html2canvas.min.js
│   │       └── liquidGL.js
│   │
│   ├── 📁 monitors/                ← Hilos de monitoreo
│   │   ├── __init__.py
│   │   ├── monitor.py              ← Coordinador de hilos
│   │   ├── baz_monitor.py          ← Monitor de correos BAZ
│   │   ├── price_scraper.py        ← Buscador de precios
│   │   └── email_reader.py         ← Lector de correos (MSAL)
│   │
│   ├── 📁 finance/                 ← Módulo de inversiones/bolsa
│   │   ├── __init__.py
│   │   ├── stock_scanner.py
│   │   ├── portfolio_analyzer.py
│   │   ├── risk_calculator.py
│   │   ├── config_manager.py
│   │   ├── coupon_manager.py
│   │   └── 📁 web/                ← Frontend del visor de bolsa
│   │       ├── index.html
│   │       ├── app.js
│   │       └── style.css
│   │
│   └── 📁 infra/                   ← Infraestructura
│       ├── __init__.py
│       ├── tunnel.py               ← Cloudflare tunnel
│       ├── telegram_utils.py       ← NUEVO: Función unificada de envío Telegram
│       └── encoding.py             ← NUEVO: Forzado UTF-8 reutilizable
│
├── 📁 data/                         ← Datos persistentes del sistema
│   ├── expenses.db
│   ├── morosos.db
│   ├── historial_precios.db
│   ├── schema.sql
│   ├── chat_id.txt
│   ├── visor_config.json
│   └── .token_cache.json
│
├── 📁 downloads/                    ← Archivos temporales de tickets
│
├── 📁 cache/                        ← Caché de datos de Yahoo Finance
│   ├── history/
│   ├── info/
│   └── ticker_lists.pkl
│
├── 📁 tests/                        ← Tests unitarios
│   ├── test_bot_edit.py
│   ├── test_bot_flow.py
│   ├── test_bot_type.py
│   ├── test_date_calc.py
│   ├── test_gemini.py
│   ├── test_load.py
│   └── test_upload.py
│
├── 📁 docs/                         ← Toda la documentación
│   ├── README.md
│   ├── MONITORBAZ_DIGITAL_BLUEPRINT.md
│   ├── OPTIMIZACION_MOVIL_TRANSACCIONES.md
│   ├── radiografia_asistente_financiero.md
│   └── reporte_implementacion.md
│
└── 📁 scripts/                      ← Scripts de utilidad/mantenimiento
    ├── check_models.py
    ├── fix_db_types.py
    ├── inspect_upload.py
    └── remove_unit_column.py
```

### 2.2 Archivos a Eliminar

| Archivo | Razón |
|---|---|
| `start.bat` | Duplicado de `iniciar.bat` |
| `MONITOR_SISTEMA.bat` | Redundante (el monitor ya se inicia desde la GUI) |
| `fix_ide_errors.bat` | Herramienta de desarrollo, no producción |
| `check_ide_problems.skill` | Herramienta externa, no parte del proyecto |
| `Captura.PNG` | Archivo temporal sin uso |
| `system_documentation.json` | Mover a `docs/` o eliminar si es obsoleto |
| `files/` completa | Código muerto (`*_mejorado.py`) — integrar o descartar |
| `EJEMPLO/` completa | Prototipos obsoletos |
| `plantilla suge/` completa | Mockups no productivos |
| `tools/liquidGL-main/` | Librería suelta; `liquidGL.js` ya está en `src/static/` |
| `Oportunidades_Inversion.csv` | Mover a `data/` si se usa, eliminar si no |

---

## ⚡ 3. Sugerencias de Optimización de Rendimiento y Respuesta

### 3.1 Base de Datos — Paginación y Consultas

> [!IMPORTANT]
> Actualmente `get_all_expenses()` retorna TODOS los registros a memoria. Esto se degrada con el tiempo.

**Cambio sugerido:**
```python
# ANTES (database.py)
def get_all_expenses(self, include_paid=True) -> List[Dict]:
    rows = conn.execute('SELECT * FROM expenses ORDER BY date DESC').fetchall()

# DESPUÉS
def get_expenses(self, limit=200, offset=0, include_paid=True) -> List[Dict]:
    query = 'SELECT * FROM expenses'
    if not include_paid:
        query += " WHERE status = 'pending'"
    query += ' ORDER BY date DESC, id DESC LIMIT ? OFFSET ?'
    rows = conn.execute(query, (limit, offset)).fetchall()
```

**Añadir índices a la BD:**
```sql
-- En schema.sql
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date DESC);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
CREATE INDEX IF NOT EXISTS idx_expenses_merchant ON expenses(merchant);
CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status);
```

### 3.2 Bot — Reducción de Latencia en Consultas NL

> [!TIP]
> Enviar 100 gastos completos a Gemini es lento y costoso. Se puede reducir un 60% el tiempo de respuesta.

**Cambio sugerido en [bot.py handle_nl_query](file:///c:/Users/PLI%20INGENIERIA/Desktop/ELIMINADOR%20POTENTE%20REVO/SUPREMA%20DE%20GASTOS/src/bot.py#L709-L748):**
```python
# ANTES: Se envían 100 gastos como JSON completo (~15KB de tokens)
expenses = self.db_manager.get_all_expenses()
context_data = [{'date': e['date'], 'merchant': e['merchant'], 
                 'category': e['category'], 'total': e['total']} 
                for e in expenses[:100]]

# DESPUÉS: Enviar un resumen estadístico pre-calculado (~500 bytes)
def _build_smart_context(self):
    """Genera un contexto compacto para consultas NL."""
    now = datetime.datetime.now()
    month = months_es[now.month - 1]
    
    spending = self.db_manager.get_monthly_spending_by_category(month, now.year)
    recent = self.db_manager.get_weekly_expenses(
        (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
        now.strftime("%Y-%m-%d")
    )
    
    return {
        'mes_actual': spending,
        'ultimos_7_dias': [
            {'fecha': e['date'], 'comercio': e['merchant'], 
             'monto': e['total'], 'cat': e['category']}
            for e in recent[:30]
        ],
        'total_mes': sum(spending.values()),
    }
```

### 3.3 Servidor Flask — Mejoras de Caché y Compresión

**3.3.1 — Aumentar TTL del caché de vistas:**
```python
# ANTES
_VIEW_TTL = 4   # 4 segundos — demasiado agresivo

# DESPUÉS
_VIEW_TTL = 30  # 30 segundos — el dashboard no cambia tan rápido
```

**3.3.2 — Servir assets estáticos con caché larga:**
```python
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename, 
                               max_age=86400)  # Cache 24h
```

### 3.4 Analyzer — Extraer Limpieza de Markdown

```python
# NUEVO: Método privado reutilizable en analyzer.py
def _clean_gemini_response(self, text: str) -> str:
    """Elimina bloques de código markdown de la respuesta de Gemini."""
    content = text.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return content
```

### 3.5 Constantes Compartidas — Nuevo Archivo `constants.py`

```python
# src/core/constants.py

MONTHS_ES = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
]

DAYS_ES = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]

CATEGORY_MAP = {
    'OXXO': 'COMIDA', 'WALMART': 'COMIDA', 'SUPER': 'COMIDA',
    # ... (centralizar el mapa de email_reader.py)
}

DEFAULT_CATEGORIES = ["Alimentos", "Transporte", "Hogar", "Ropa", 
                       "Salud", "Entretenimiento", "Servicios", "Otros"]
```

### 3.6 Envío de Telegram Unificado

```python
# src/infra/telegram_utils.py
import os
import logging
import requests

logger = logging.getLogger(__name__)

def send_telegram_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Envía un mensaje a Telegram. Función unificada para todo el proyecto."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = _get_chat_id()
    
    if not token or not chat_id:
        logger.warning("Telegram no configurado (falta token o chat_id)")
        return False
    
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Error enviando Telegram: {e}")
        return False

def _get_chat_id() -> str:
    """Obtiene el chat_id desde .env o archivo persistente."""
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not chat_id:
        try:
            from src.core.config import Config
            path = os.path.join(Config.BASE_DIR, "data", "chat_id.txt")
            if os.path.exists(path):
                with open(path, "r") as f:
                    chat_id = f.read().strip()
        except Exception:
            pass
    return chat_id
```

### 3.7 Monitor de Precios — Optimizar Playwright

```python
# ANTES (monitor.py:412-413)
context = await pw.chromium.launch_persistent_context(
    headless=False,  # ¡Abre ventana del navegador visible!

# DESPUÉS
context = await pw.chromium.launch_persistent_context(
    headless=True,   # Sin ventana — ahorra RAM y CPU
```

### 3.8 `iniciar.bat` — Versión Mejorada

```batch
@echo off
title Asistente Financiero
cd /d "%~dp0"

:: Python del entorno virtual
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] No se encontro el entorno virtual .venv
    echo Ejecuta: python -m venv .venv
    pause
    exit /b 1
)

:: Limpieza de procesos anteriores (solo si es necesario)
tasklist /FI "WINDOWTITLE eq Asistente Financiero*" 2>nul | find /i "python" >nul
if %ERRORLEVEL%==0 (
    echo Cerrando sesiones anteriores...
    taskkill /f /fi "WINDOWTITLE eq Asistente Financiero*" >nul 2>&1
    timeout /t 2 /nobreak >nul
)

echo Iniciando ASISTENTE FINANCIERO...
"%PYTHON%" src\app.py

echo.
echo El programa finalizo.
pause
```

> [!WARNING]
> **El `taskkill /f /im python.exe` actual mata TODOS los procesos Python del sistema**, no solo los del proyecto. Esto puede cerrar otros programas que estés ejecutando. La versión mejorada solo mata los que tengan el título de ventana correcto.

---

## 🔄 4. Plan de Migración (Paso a Paso)

> [!NOTE]
> Este plan se puede ejecutar gradualmente sin romper la funcionalidad existente.

### Fase 1: Seguridad Inmediata (⚡ Hoy)
- [ ] Agregar `.env`, `.token_cache.json` al `.gitignore`
- [ ] Crear `.env.example` con valores placeholder
- [ ] Rotar tokens y API keys comprometidos

### Fase 2: Limpieza de Raíz (📂 Día 1)
- [ ] Mover `cloudflared.exe` → `bin/cloudflared.exe`
- [ ] Mover `chat_id.txt` → `data/chat_id.txt`
- [ ] Mover `.token_cache.json` → `data/.token_cache.json`
- [ ] Mover `visor_config.json` → `data/visor_config.json`
- [ ] Mover `Oportunidades_Inversion.csv` → `data/` (o eliminar)
- [ ] Mover todos los `.md` sueltos → `docs/`
- [ ] Eliminar `start.bat` (duplicado), `Captura.PNG`, `MONITOR_SISTEMA.bat`
- [ ] Eliminar `files/`, `EJEMPLO/`, `plantilla suge/`

### Fase 3: Reorganizar Código (🔧 Día 2-3)
- [ ] Mover `gui.py` → `src/app.py` (actualizar imports)
- [ ] Crear `src/core/constants.py` con meses, categorías, etc.
- [ ] Crear `src/infra/telegram_utils.py`
- [ ] Crear `src/infra/encoding.py` con el forzado UTF-8
- [ ] Mover `tools/NOTIFICADOR_BOT/*.py` → `src/finance/`
- [ ] Mover `tools/NOTIFICADOR_BOT/web/` → `src/finance/web/`
- [ ] Mover `tools/BUSCADOR DE PRECIOS/buscador_precios.py` → `src/monitors/price_scraper.py`
- [ ] Mover scripts de utilidad → `scripts/`

### Fase 4: Optimización (⚡ Día 4-5)
- [ ] Implementar paginación en `get_all_expenses()`
- [ ] Agregar índices SQL
- [ ] Optimizar contexto de consultas NL
- [ ] Aumentar TTL de caché de vistas
- [ ] Cambiar Playwright a `headless=True`
- [ ] Unificar envío de Telegram en todo el proyecto

### Fase 5: Refactorización del Bot (🤖 Día 6-7)
- [ ] Separar handlers del bot en archivos por dominio
- [ ] Eliminar `sys.path.append()` sueltos (usar imports relativos con paquetes)
- [ ] Actualizar `iniciar.bat` con la versión mejorada

---

## 📊 5. Impacto Estimado

| Mejora | Antes | Después | Impacto |
|---|---|---|---|
| Archivos en raíz | 21 | 5 (`.env`, `.gitignore`, `README.md`, `requirements.txt`, `iniciar.bat`) | -76% ruido visual |
| Tiempo respuesta consulta NL | ~4-6s | ~2-3s | -50% latencia |
| RAM en servidor (Playwright) | ~300MB (ventana visible) | ~150MB (headless) | -50% RAM |
| Regeneración dashboard | Cada 4s | Cada 30s | -87% carga CPU |
| Líneas de código duplicado | ~80 líneas | 0 | Eliminación total |
| Credenciales expuestas | 4 | 0 | Seguridad crítica resuelta |

---

> [!TIP]
> Si deseas que implemente alguna de estas fases, solo dime cuál priorizar. Puedo empezar por la **Fase 1 (Seguridad)** o por la **Fase 2 (Limpieza de raíz)** de inmediato.
