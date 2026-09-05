# CHANGELOG — SUPREMA DE GASTOS
Formato: [Versión] — YYYY-MM-DD
Tipos de cambio: AGREGAR | MODIFICAR | ELIMINAR | CORREGIR | REVERTIR

---

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
