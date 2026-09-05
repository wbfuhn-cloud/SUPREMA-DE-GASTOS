# CHANGELOG — SUPREMA DE GASTOS
Formato: [Versión] — YYYY-MM-DD
Tipos de cambio: AGREGAR | MODIFICAR | ELIMINAR | CORREGIR | REVERTIR

## [v2.3.0] — 2026-09-05 23:51
### AGREGAR / REDISEÑO DE UI (GBM.COM STYLE)
- `tools/NOTIFICADOR_BOT/style.css`:
  - Se implementó el sistema de diseño estilo **GBM.com** con fuentes `Plus Jakarta Sans`, fondo obsidian medianoche (`#07090E`), tarjetas con curvatura súper suave (`rounded-3xl` / `24px`), sombras profundas de alta gama y acentos azul eléctrico (`#0052FF`).
- `tools/NOTIFICADOR_BOT/index.html`:
  - Se rediseñó el header del escáner VISOR/IA con la barra de navegación flotante tipo píldora, la insignia de estado del mercado y el panel del modelo predictivo ML.
  - Se agregó el selector de vista dual (**Tarjetas GBM** / **Tabla Técnica**).
- `tools/NOTIFICADOR_BOT/app.js`:
  - Se añadieron las funciones `switchViewMode` y `renderGBMCards` para construir tarjetas dinámicas de acciones con métricas de viabilidad, RSI, ATR y nivel de confianza IA.
- `src/templates/dashboard.html`, `details.html` y `transactions.html`:
  - Se armonizó la barra de navegación superior compartiendo las pestañas en formato píldoras GBM.

## [v2.2.3] — 2026-09-05 22:08
### CORREGIR
- `src/server.py`:
  - Se corrigió la función `details_view()` añadiendo la llamada `render_template('details.html', **data)`, resolviendo la pantalla en blanco o no renderizada en la sección de Analíticos (`/details`).

## [v2.2.2] — 2026-09-05 19:49
### CORREGIR
- `src/templates/dashboard.html`:
  - Se aplicó el filtro `| safe` a las variables `years_html`, `unconfirmed_banner`, `top_merchants_html` y `recent_html_clean` para evitar que Jinja2 escape las etiquetas HTML y las muestre como texto plano en el navegador.
  - Se mejoró la función `submitExpense()` añadiendo validación de formulario, prevención de montos nulos/cero y auto-llenado de la fecha actual en la interfaz.
- `src/database.py`:
  - Se implementó la función `_normalize_expense_data` que calcula automáticamente el mes en español (ej. `SEPTIEMBRE`), el día y el número de semana ISO a partir de la fecha seleccionada (`date`), eliminando el valor por defecto `'GENERIC'` y `0`.

## [v2.2.1] — 2026-09-05 19:43
### CORREGIR
- `src/server.py`:
  - Se registró el filtro personalizado `@app.template_filter('format_currency')` para dar formato de moneda con separador de miles sin depender del operador de formateo `%` de Python.
- `src/templates/dashboard.html` y `src/templates/details.html`:
  - Se reemplazaron las llamadas `{{ '%,.2f'|format(...) }}` y `{{ '%,.0f'|format(...) }}` por el filtro `| format_currency`, resolviendo el error `ValueError: unsupported format character ',' (0x2c) at index 1`.
  - Se corrigió la referencia de contexto `{{ data['loans_html'] }}` y `{{ data['debts_html'] }}` a `{{ loans_html | safe }}` y `{{ debts_html | safe }}`.

## [v2.2.0] — 2026-09-05 19:40
### AGREGAR
- `src/bot.py`:
  - Se agregó persistencia a los gastos pendientes (`self.pending_expenses`) utilizando un archivo `database/pending_expenses.json`.
  - **Motivo**: Evitar pérdida de contexto si el usuario está en proceso de confirmar un gasto y el bot o servidor se reinicia o se pierde la red.

### MODIFICAR
- `src/database.py`:
  - Se envolvió todos los accesos de escritura (`ensure_email_log_table`, `log_email`) con `self._write_lock` para evitar errores `database is locked` en concurrencia (Fase 2).
  - Se implementaron bloques `try/except sqlite3.Error` en todas las lecturas de la base de datos local para que devuelvan listas o diccionarios vacíos en lugar de estrellar el programa.
- `src/email_reader.py`:
  - Se encapsularon las peticiones HTTP a Microsoft Graph (`_graph_get` y `_graph_patch`) dentro de un bloque `try/except` de `requests.exceptions.RequestException` para evitar cierres silenciosos por fallos temporales de red (Fase 3).
- `tools/NOTIFICADOR_BOT/stock_scanner.py` y `tools/NOTIFICADOR_BOT/app.js`:
  - Se adaptó la lógica de extracción de predicción ML para renderizar un desglose dinámico (*Feature Importance*) de impacto de predicción en el UI.

## [v2.1.0] — 2026-09-05 13:17
### AGREGAR
- `tools/NOTIFICADOR_BOT/ml_predictor.py`:
  - Se implementó un modelo supervisado de Machine Learning (`GradientBoostingClassifier`) entrenado sobre 4,001 muestras históricas de `learner.db`.
  - Extrae e ingenia 18 características clave (RSI, MACD, Posición en Bollinger Bands, Volatilidad, Ratio de Volumen, Log Market Cap, Indicadores activos).
  - Precisión validada: **33.69%** (vs 15.5% baseline) y AUC: **74.78%**.
- `SPEC.md`: Especificación técnica formal bajo metodología Spec-Driven Development (SDD).

### CORREGIR / REFACTORIZAR
- `tools/NOTIFICADOR_BOT/recommendation_learner.py`:
  - Se eliminó la vulnerabilidad de inyección SQL en la función `has_recent_alert` utilizando parametrización nativa en SQLite.
- `tools/NOTIFICADOR_BOT/stock_scanner.py`:
  - Se eliminaron 8 excepciones silenciosas (`except: pass`) sustituyéndolas por captura de excepciones específicas y logging estructurado.
  - Se integró la predicción `ML_Score` y el nivel de confianza (`ALTA`, `MEDIA`, `BAJA`).
- `tools/NOTIFICADOR_BOT/config_manager.py`:
  - Se corrigió el error en la llamada a `json.dump` dentro de `save_config`.
- `tools/NOTIFICADOR_BOT/portfolio_analyzer.py`:
  - Se eliminó la duplicación de código en `_get_usd_mxn` y `LEVERAGED_ETFS`.
- `src/server.py` y `tools/NOTIFICADOR_BOT/app.js`:
  - Se expusieron los endpoints `/api/ml/status` y `/api/ml/retrain`.
  - Se añadió la métrica `ML Score` en el panel de detalles del frontend.

---

## [v2.0.2] — 2026-09-05 12:55
### AGREGAR
- `autorizar_correo.bat`:
  - Se creó un nuevo script (acceso directo) para autorizar manualmente la lectura de correos desde nuevas computadoras.
  - **Motivo**: Al cambiar de computadora, el token de sesión (`.token_cache.json`) no se copia por seguridad. Como el sistema intenta abrir el navegador desde un proceso en segundo plano en la interfaz, esto puede fallar o no ser visible. Este script permite hacer el proceso de autorización OAuth2 de forma manual, visible e interactiva.

## [v2.0.1] — 2026-09-05 10:20
### CORREGIR
- `iniciar.bat`:
  - Se agregó `pandas` a la lista de dependencias que se verifican en la línea 38.
  - **Motivo**: Asegurar que si falta `pandas` en el entorno, `iniciar.bat` reinstale las dependencias y evite errores al abrir el módulo `/bolsa`.

## [v2.0.0] — 2026-09-05 05:56
### AGREGAR / MODIFICAR
- **Migración a la Nube (Cloudflare D1)**:
  - Se exportó la base de datos local SQLite y se subió exitosamente a Cloudflare D1.
  - `src/database.py`: Se reescribió la arquitectura del gestor de base de datos para soportar una conexión dual. Si las credenciales de Cloudflare están presentes en `.env`, el sistema se conecta a la nube mediante la API REST HTTP. De lo contrario, funciona con SQLite local.
  - **Motivo**: Permitir que el sistema se pueda ejecutar en cualquier computadora o subir a GitHub sin preocuparse por corromper la base de datos o tener desincronizaciones, habilitando verdadera portabilidad en la nube.

## [v1.1.6] — 2026-09-05 02:49
### ELIMINAR
- `start.bat`:
  - Se eliminó este archivo porque solo era un acceso directo que llamaba a `iniciar.bat`.
  - **Motivo**: Mantener un único punto de entrada (`iniciar.bat`) para arrancar el sistema y evitar confusiones con múltiples scripts de inicio.

## [v1.1.5] — 2026-09-05 02:46
### CORREGIR
- `requirements.txt` y entorno virtual:
  - Se instaló la dependencia faltante `pandas` en el entorno virtual (`.venv`).
  - Se agregó `pandas` al archivo `requirements.txt`.
  - **Motivo**: Resolver el error `Error: Motor de escaneo no disponible. Error: No module named 'pandas'` reportado en el apartado `/bolsa`.

## [v1.1.4] — 2026-09-05 01:58
### CORREGIR / REFACTORIZAR
- `src/transactions_view.py`:
  - Se refactorizó la función `confirmExpense()` para realizar una **actualización optimista instantánea en el DOM**.
  - Al hacer clic en la paloma verde de confirmación, la sombra morada desaparece en 0 ms y la paloma se remueve inmediatamente, enviando la actualización al servidor en segundo plano con notificación de guardado suave (`✓ Guardado`).
  - **Motivo**: Corregir la falta de respuesta visual percibida por la latencia en recargar la página completa.

## [v1.1.3] — 2026-09-05 01:36
### AGREGAR / MODIFICAR
- `src/database.py` y `src/transactions_view.py`:
  - Se agregó la purga automática de categorías sin uso (`cleanUnusedCategories()`).
  - **Motivo**: Si una categoría deja de existir en todos los gastos (debido a reasignación o eliminación), se elimina automáticamente en tiempo real de todos los desplegables y filtros de la aplicación.

## [v1.1.2] — 2026-09-05 01:21
### CORREGIR
- `src/transactions_view.py`:
  - Se reemplazó el menú flotante JS por `<select>` nativos del navegador con carga diferida (`onpointerdown="ensureCatOptions(this)"`).
  - **Motivo**: Eliminar el problema donde el menú desplegable se cerraba instantáneamente debido a eventos de scroll automático y garantizar compatibilidad 100% nativa con móviles y navegadores web sin sobrecargar el DOM.

## [v1.1.1] — 2026-09-05 01:15
### CORREGIR
- `src/transactions_view.py`:
  - Se agregó el atributo `value` pre-formateado directamente desde el HTML en Python para las casillas de montos (`amount-input`).
  - Se cambió el inicializador JS de `DOMContentLoaded` a `initPage()` con ejecución inmediata para evitar que las cantidades aparezcan en blanco cuando el script se ejecuta tras la carga del DOM o mediante caché.

## [v1.1.0] — 2026-09-05 00:48
### MODIFICAR
- `src/transactions_view.py`:
  - Se eliminó el `<select>` individual repetido en cada fila de la tabla y se sustituyó por un único dropdown global flotante en JS (`#global-cat-dropdown`).
  - **Motivo**: Reducir drásticamente los nodos DOM de ~84,000 a ~100 y acelerar la visualización en 85-98%.
  - **Archivos afectados**: `src/transactions_view.py` (métodos `_build_row` y `generate_html`)
- `src/server.py`:
  - Se modificó la ruta `/transactions` para cargar por defecto únicamente el año actual (`2026`). Se habilitó la opción `year=all` para el botón "TODOS".
  - **Motivo**: Reducir el tiempo de renderizado inicial al entrar a `/transactions`.
  - **Archivos afectados**: `src/server.py` (`transactions_view()`)

### CORREGIR
- `src/transactions_view.py`:
  - Se corrigió la función JS `applyFilters()` cambiando el selector `input[data-field="category"]` a `[data-field="category"]` para que el filtro por categoría funcione correctamente con elementos botón/badge.
  - Se arreglaron los diálogos JS `confirm()` en `confirmExpense` y `deleteExpense` reemplazando los caracteres escapados `\\u00bf` por `¿` y `á/ó` unicode correctos.

### SNAPSHOT antes del cambio
```html
<!-- Select repetido por cada fila en transactions_view.py -->
<select class="form-input text-xs" data-field="category" onchange="handleCategoryChange(this, 123)" data-oldval="ALIMENTACIÓN">
  <option value="">(Sin categoría)</option>
  <option value="ALIMENTACIÓN">Alimentación</option>
  <!-- ... 97 opciones repetidas x 864 filas ... -->
</select>
```

### PRUEBAS REALIZADAS
- [x] Generación de HTML para 2026 en 0.019s (917 KB).
- [x] Generación de HTML para TODOS los registros en 0.155s (1,852 KB).
- [x] Verificación de sintaxis e importación limpia en Python.
- [x] Cierre y filtrado del dropdown global de categorías sin errores de consola.

---

## [v1.0.0] — 2026-09-04
### AGREGAR
- Versión inicial del sistema de gestión financiera personal "SUPREMA DE GASTOS".
