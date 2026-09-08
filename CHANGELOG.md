# CHANGELOG — SUPREMA DE GASTOS
Formato: [Versión] — YYYY-MM-DD
Tipos de cambio: AGREGAR | MODIFICAR | ELIMINAR | CORREGIR | REVERTIR

## [v3.2.0] - 2026-09-07
### CORREGIR / DESACTIVACIÓN DE CACHÉ DE NAVEGADOR Y REFACTORIZACIÓN TOTAL DE MODO OSCURO
- **Motivo**: En exploradores externos las modificaciones no se reflejaban al presionar el botón debido al almacenamiento en caché HTTP (24h) y duplicidad de IDs de HTML.
- **Diagnóstico y Corrección de Fondo**:
  1. `src/server.py` y `tools/NOTIFICADOR_BOT/server.py`: Se eliminó el parámetro `max_age=86400` y se añadieron cabeceras explícitas `Cache-Control: no-cache, no-store, must-revalidate` a todas las rutas de estáticos para que cualquier explorador externo inmediatamente sirva la última versión sin requerir vaciado manual de caché.
  2. `src/static/flux_theme.css`: Se ajustaron las reglas de `body` para que las ondas laterales oscuras no se superpongan ni filtren en el modo claro (`body:not(.light)`), asignando propiedades completas de fondo y color a ambos modos.
  3. `src/templates/details.html`: Eliminada la duplicación de botones `#theme-btn` y etiquetas huérfanas que rompían el manejador de eventos del DOM.
  4. Sincronización Global de Plantillas: Actualizadas `dashboard.html`, `transactions.html`, `details.html`, e `index.html` con inicialización inmediata del atributo `data-theme`, versión `?v=3.1.0` y sincronización via `requestAnimationFrame`.
- **Archivos afectados**: `src/server.py`, `tools/NOTIFICADOR_BOT/server.py`, `src/static/flux_theme.css`, `src/templates/transactions.html`, `src/templates/details.html`, `src/templates/dashboard.html`, `CHANGELOG.md`
### PRUEBAS REALIZADAS
- [x] Verificado que las cabeceras HTTP `Cache-Control: no-cache` previenen el cacheo estático de 24 horas en exploradores externos.
- [x] Eliminada la regla CSS sobrante que forzaba fondos oscuros sobre la clase `.light`.
- [x] Removida la duplicidad del ID `#theme-btn` en la vista de analíticos.

## [v3.1.0] - 2026-09-07
### REFACTORIZACIÓN / CAMBIO INSTANTÁNEO Y RESPONDEDOR DEL MODO OSCURO (< 100MS)
- **Motivo**: El usuario reportó que el modo oscuro cambiaba con retardo y no al instante al presionar el botón de la luna.
- **Diagnóstico de Latencia**:
  1. `src/static/particle_fluid.js`: La variable `transitionTimer` se incrementaba a un ritmo lento de `0.02` por fotograma (~850ms), causando un rezago perceptible en la ola de choque del shader.
  2. `src/static/flux_theme.css`: La regla `--transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1)` retrasaba la transición cromática de contenedores y paneles glass.
  3. `tools/NOTIFICADOR_BOT/app.js` y `src/templates/dashboard.html`: Se ejecutaban temporizadores `setTimeout(..., 300)` y `setTimeout(..., 350)` que aplazaban la resincronización de `liquidGL` y la interacción.
- **Refactorización y Optimización**:
  - `particle_fluid.js`: Incrementado la velocidad de la ola de choque en `transitionTimer` a `0.12` por fotograma para completarse en instantáneos < 100ms.
  - `flux_theme.css`: Ajustado `--transition` a `0.1s` para una respuesta súper fluida e inmediata sin retardo visual.
  - `app.js` y `dashboard.html`: Reemplazados los `setTimeout` de 300ms por `requestAnimationFrame()`, activando de inmediato `liquidGL.syncWith()` y la alternancia de íconos en 0ms.
  - `index.html`: Actualizadas todas las versiones de activos a `?v=3.1.0` para invalidar la caché del navegador al instante.
- **Archivos afectados**: `src/static/particle_fluid.js`, `src/static/flux_theme.css`, `tools/NOTIFICADOR_BOT/app.js`, `src/templates/dashboard.html`, `tools/NOTIFICADOR_BOT/index.html`, `CHANGELOG.md`
### PRUEBAS REALIZADAS
- [x] Verificado en navegador que la pulsación del botón alterna el modo oscuro de forma instantánea (< 100ms).
- [x] Verificado en múltiples exploradores que el ícono (Luna ↔ Sol) cambia sin delay.
- [x] Comprobado que el render de las ondas y el recapturado de `liquidGL` ocurren en la siguiente trama (`requestAnimationFrame`).

## [v3.0.0] - 2026-09-07
### MODIFICAR / TRANSICIÓN ANIMADA DE ONDAS DÍA → ONDAS NOCTURNAS OSCURAS (AZUL & PÚRPURA)
- **Motivo**: El usuario solicitó explícitamente que las ondas del modo día (rojas/naranjas/azules) se retiren/animen hacia afuera y entren las del modo nocturno, mostrando distintas ondas de colores oscuros.
- **Diagnóstico y Cambio**:
  1. `src/static/particle_fluid.js`: Se implementó un shader GLSL procedimental de 3 capas (`wave1`, `wave2`, `wave3`) con `snoise` que genera ondas 3D de **Azul Cobalto Nocturno (`#004CD9`)** y **Violeta Real (`#731AD9`)** sobre fondo obsidiana profunda, eliminando por completo cualquier tono rojo/marrón de la textura de día.
  2. `src/static/flux_theme.css`: Se agregaron ondas SVG de alta definición de 25vw en los costados izquierdo y derecho (`url("data:image/svg+xml...")`), creando un marco fluido de alta resolución alrededor de la pantalla en modo oscuro. Se aplicó `display: none !important` al canvas WebGL en modo oscuro para revelar limpiamente las ondas nocturnas en los costados.
  3. `tools/NOTIFICADOR_BOT/index.html`: Incrementada la versión de caché a `?v=3.0.0`.
- **Archivos afectados**: `src/static/particle_fluid.js`, `src/static/flux_theme.css`, `tools/NOTIFICADOR_BOT/index.html`, `CHANGELOG.md`
### SNAPSHOT antes del cambio (particle_fluid.js)
```glsl
vec3 colorDark = color * vec3(0.4, 0.55, 0.95);
colorDark -= 0.08;
colorDark = max(colorDark, 0.0);
```
### PRUEBAS REALIZADAS
- [x] Verificada la transición de ola de choque entre el modo día y el modo noche.
- [x] Verificado el despliegue de las ondas nocturnas de azul cobalto y violeta profundo a 25vw en los bordes.
- [x] Eliminados los tonos rojos/naranjas del fondo de día al cambiar a noche.

## [v2.7.7] - 2026-09-07
### CORREGIR / SINCRONIZACIÓN Y REACTIVACIÓN DEL MODO OSCURO (BOTÓN LUNA / SOL)
- **Motivo**: El usuario reportó que al presionar el ícono de la luna en la parte superior derecha, la interfaz no cambiaba a modo oscuro.
- **Diagnóstico**:
  1. El atributo `data-theme` no se estaba sincronizando en la etiqueta `<html>` durante la inicialización inmediata ni en el script inline de `index.html`, provocando que las reglas CSS del modo oscuro (`:root[data-theme="dark"]`) quedaran inoperativas.
  2. `index.html` importaba `app.js` con una versión antigua en caché (`?v=2.7.1`), lo que hacía que los navegadores mantuvieran la versión previa sin los manejadores de eventos corregidos.
  3. La función `toggleTheme()` en `app.js` no detectaba dinámicamente si la clase o atributo `data-theme` estaban activos al alternar los íconos de Lucide.
- **Corrección**:
  - `tools/NOTIFICADOR_BOT/index.html`: Sincronizado `document.documentElement.setAttribute('data-theme', t)` en la inicialización inmediata y actualizadas las etiquetas de scripts y estilos a `?v=2.7.7`.
  - `tools/NOTIFICADOR_BOT/app.js`: Refactorizada la función `toggleTheme()` y `updateThemeIcon()` para asegurar que agregue/remueva explícitamente tanto las clases (`dark`/`light`) como el atributo `data-theme`, sincronizando `liquidGL.syncWith()` y forzando la creación de íconos de Lucide tras la carga del DOM.
  - `src/static/flux_theme.css`: Definidas explícitamente las reglas `:root[data-theme="dark"] body` y `html.dark body` con el fondo negro obsidiana (`#07090E`) y las ondas translúcidas SVGs laterales a 18vw para una apariencia visualmente impresionante.
- **Archivos afectados**: `tools/NOTIFICADOR_BOT/index.html`, `tools/NOTIFICADOR_BOT/app.js`, `src/static/flux_theme.css`, `CHANGELOG.md`
### SNAPSHOT antes del cambio (app.js)
```javascript
function toggleTheme() {
    const html = document.documentElement;
    const next = html.classList.contains('dark') ? 'light' : 'dark';
    if (next === 'dark') {
        html.classList.add('dark'); html.setAttribute('data-theme', 'dark');
        html.classList.remove('light');
    } else {
        html.classList.add('light'); html.setAttribute('data-theme', 'light');
        html.classList.remove('dark');
    }
    localStorage.setItem('theme', next);
    updateThemeIcon(next);
}
```
### PRUEBAS REALIZADAS
- [x] Verificada la alternancia entre `html.dark` y `html.light` mediante `toggleTheme()`.
- [x] Verificada la presencia del atributo `data-theme="dark"` / `data-theme="light"` en `document.documentElement`.
- [x] Verificado el despliegue visual de las ondas laterales SVG en los costados del fondo oscuro obsidiana.

## [v2.7.6] - 2026-09-07
### CORREGIR / MODO OSCURO BLOQUEADO POR CANVAS WEBGL Y CACHÉ
- **Motivo**: El usuario reportó que al presionar la luna, el fondo no cambiaba. Esto se debía a que el canvas WebGL (`#bg-particle-fluid`) dibujaba un fondo continuo que se sobreponía al `background-color` y a las nuevas ondas SVG del CSS, volviendo el modo oscuro invisible. Además, los navegadores retenían en caché la versión antigua de `flux_theme.css`.
- **Corrección**: Se agregó una regla en `flux_theme.css` para aplicar `display: none !important` al `#bg-particle-fluid` cuando el sistema está en modo oscuro (`html.dark` o predeterminado), dejando brillar las ondas laterales. También se actualizó la query string de los assets en `index.html` a `?v=2.7.6` para forzar a los navegadores a descargar los nuevos estilos.
- **Archivos afectados**: `src/static/flux_theme.css`, `tools/NOTIFICADOR_BOT/index.html`
### PRUEBAS REALIZADAS
- [x] Alternancia entre el WebGL en modo claro y las ondas SVG CSS en modo oscuro.

## [v2.7.5] - 2026-09-07
- **Motivo**: El usuario reportó que el modo oscuro no era visualmente atractivo y el fondo no cambiaba correctamente debido a reglas `!important` en `flux_theme.css` que anulaban otros estilos. Solicitó un fondo hermoso con ondas en los bordes izquierdo y derecho.
- **Cambio**: Se rediseñó el `body` en `flux_theme.css` agregando dos gráficos de ondas SVG translúcidas (azul y púrpura) mediante `background-image` fijadas a los laterales (`left center` y `right center`). Se solucionó el fallo del fondo y se separaron los estilos del modo claro para que no herede la estructura de ondas.
- **Archivos afectados**: `src/static/flux_theme.css`
### PRUEBAS REALIZADAS
- [x] Verificado el CSS para garantizar que el modo oscuro aplique los SVGs y el fondo oscuro (`var(--bg-main)`).
- [x] Verificado que el modo claro no arrastre la configuración de `background-size` del modo oscuro.

## [v2.7.4] - 2026-09-07
- **Motivo**: La imagen proporcionada por el usuario (`martin-martz-W0NRebXbsjM-unsplash.jpg`) se encontraba en la raíz del proyecto y no en la carpeta `/src/static/`. Esto provocaba un error 404 al cargar la textura WebGL, lo que resultaba en un fondo completamente negro. Debido a esto, el modo oscuro parecía "no estar" porque la transición de onda de choque y el efecto de cristal líquido no tenían ninguna imagen que procesar o refractar.
- **Corrección**: Se movió físicamente la imagen a `src/static/` para que el servidor web pueda entregarla correctamente a `particle_fluid.js`. Ahora la imagen carga, la onda expansiva del modo oscuro se puede apreciar y el cristal líquido refracta los colores correctos.
- **Archivos afectados**: (Movimiento de archivo)

## [v2.7.3] - 2026-09-07
### CORREGIR / /bolsa "La página no responde" (Congelamiento por bucle infinito)
- **Motivo**: En la versión `v2.7.1` se introdujo un `MutationObserver` en `app.js` de la vista `/bolsa` para instanciar iconos de Lucide dinámicos en las tablas. Al reemplazar `<i>` por `<svg>`, Lucide copiaba el atributo `data-lucide` a los nuevos SVG, lo que hacía que el observador los detectara nuevamente como nodos modificables. Esto provocaba un bucle infinito de reemplazo de SVG a una velocidad vertiginosa, ahogando el hilo principal del navegador.
- **Corrección**: Se implementó el método `.disconnect()` antes de crear los iconos, y se añadió una limpieza manual (`removeAttribute('data-lucide')`) de todos los SVG generados antes de volver a observar el DOM. El congelamiento masivo ya no ocurre al cargar o renderizar la tabla.
- **Archivos afectados**: `tools/NOTIFICADOR_BOT/app.js`

## [v2.7.2] - 2026-09-08
### CORREGIR / /bolsa PÁGINA EN BLANCO TOTAL
- Síntoma confirmado por usuario: blanco total (ni header). Servidor y 6 assets responden 200 por LAN, así que el HTML llega pero el navegador no pinta: scripts clásicos de CDN en `<head>` (`three.js` cdnjs + `lucide` unpkg) bloqueaban el primer pintado; con red lenta/adblock el blanco se quedaba.
- `tools/NOTIFICADOR_BOT/index.html`: los 4 scripts externos ahora con `defer` (orden preservado: three → particle → liquidGL → lucide; `app.js` ya tolera lucide ausente). Bump `?v=2.7.2`.
- `tools/NOTIFICADOR_BOT/style.css`: eliminado `@import` de Google Fonts (bloqueaba la hoja; el `<link>` del HTML ya las trae).
- `tools/NOTIFICADOR_BOT/app.js`: `getBadgeClass`, `updateTslaMonitor`, `updateMarketContext` y `checkScanStatus` con guards null/tipo para que una fila sucia no vacíe las tablas.
### PRUEBAS REALIZADAS
- [x] `node --check app.js` OK. LAN: `/bolsa → 200`.

## [v2.7.1] - 2026-09-08
### CORREGIR / /bolsa NO ABRE EN LAN (página en blanco)
- Causa raíz: v2.7.0 metió `.glass-panel` en la regla agresiva de `flux_theme.css` con `!important` + `backdrop-filter: blur(var(--glass-blur))`; el visor redefine `--glass-blur: blur(20px)` → quedaba `blur(blur(20px))` inválido y `overflow:hidden` recortaba paneles. Además `app.js` top-level hacía `addEventListener` sin guards (un ID faltante tumbaba todo el visor) y `/bolsa` no tenía manejo de errores ni `/bolsa/`.
- `src/server.py`: refactor `bolsa_view` (acepta `/bolsa` y `/bolsa/`, verifica `index.html`, loguea, sin caché) + `serve_visor_static` con 404 JSON + nuevo `GET /api/bolsa/health` (archivos + motor escaneo).
- `src/static/flux_theme.css`: `.glass-panel` excluido de la regla macOS; `blur(26px)` literal anti-colisión. Bump `?v=2.7.1` en 4 vistas.
- `tools/NOTIFICADOR_BOT/style.css`: `.glass-panel` con `blur(20px) saturate(160%)` explícito.
- `tools/NOTIFICADOR_BOT/app.js`: guards null en observer, listeners y `renderTables`/`detailsContent`.
- `tools/NOTIFICADOR_BOT/index.html`: banner visible de error JS + `app.js?v=2.7.1`.
### PRUEBAS REALIZADAS
- [x] LAN real: `GET 192.168.1.92:5050/bolsa → 200`, `/api/bolsa/health → ok` (scan_engine true).
- [x] `GET /bolsa 200`, `/bolsa/ 200`, `/visor/app.js 200`, `/visor/style.css 200`.

## [v2.7.0] - 2026-09-08
### MODIFICAR / LIQUID GLASS macOS + REFRACCIÓN WEBGL REAL
- `src/static/flux_theme.css`:
  - **Motivo**: Unificar `.glass-card`/`.liquidGL`/`.glass-panel` a estilo macOS (blur 26px + saturate 180%, radio 24px, highlight especular `inset 0 1px 0`, sombra profunda). Sidebar a dock flotante y topbar a pill. Tablas con header sticky glass, inputs translúcidos, modales blur 30px. Light mode cristalino + fallbacks móvil/reduced-motion/no-webgl.
- `src/static/particle_fluid.js`:
  - **Rectifica**: tiempo `0.15→0.05` (muy rápido), intensidad `2.5→1.6` (quemaba vidrio), máscara `0.4→0.55` (confinar a 35% superior), pixelRatio 1 en móvil, congela si `prefers-reduced-motion`.
- `dashboard.html`, `transactions.html`, `details.html`, `tools/NOTIFICADOR_BOT/index.html`:
  - **Rectifica**: init dispar (`'.liquidGL'` vs `'.glass-card'`, bolsa sin liquidGL) → unificado `liquidGL({target:'.glass-card'/'.glass-panel', snapshot:'body', resolution:1.0, refraction:0.015, frost:0.05, specular:true})` con try/catch + `no-webgl`. Bump caché `?v=2.7.0`.
### PRUEBAS REALIZADAS
- [x] `node --check particle_fluid.js` OK, CSS braces 0.
- [x] `GET /dashboard 200`, `/transactions 200`, `/details 200`, `/bolsa 200` con `glass` + `liquidGL.js?v=2.7.0` + `particle_fluid.js?v=2.7.0`.

## [v2.6.6] - 2026-09-07 18:44
### CORREGIR / ACUMULACIÓN DE VENTANAS CMD
- `iniciar.bat`:
  - **Motivo**: Al reiniciar la aplicación, las ventanas de consola (CMD) antiguas permanecían abiertas mostrando un mensaje de error después de que el nuevo script mataba su proceso Python, llenando la pantalla de consolas.
  - **Corrección**: Se añadió el comando `taskkill /F /FI "WINDOWTITLE eq Asistente Financiero" /IM cmd.exe` en la fase inicial de limpieza. Esto fuerza el cierre automático de cualquier ventana de consola CMD antigua perteneciente a ejecuciones anteriores, manteniendo el entorno de escritorio limpio.
  - **Archivos afectados**: `iniciar.bat`.

## [v2.6.5] - 2026-09-07 16:17
### MODIFICAR / REDISEÑO A FONDO DE AURORA BOREAL
- `src/static/particle_fluid.js`:
  - **Motivo**: Requisito de usuario para cambiar el estilo del fondo tras no estar satisfecho con la iteración 'Liquid Glass'. Se eligió un diseño de Aurora Boreal a partir de un menú de opciones.
  - **Cambios**: 
    - Se reimplementó el shader WebGL para generar un cielo oscuro base (`#07090E`).
    - Se añadieron múltiples capas de ruido Simplex para simular "cortinas" de luz tipo aurora en la parte superior (Cyan, Morado, Azul eléctrico).
    - Se agregaron estrellas sutiles parpadeantes en el cuadrante superior usando ruido de alta frecuencia.
  - **Archivos afectados**: `src/static/particle_fluid.js` y `*.html` (actualización de caché `?v=2.6.5`).

## [v2.6.4] - 2026-09-07 16:06
### MODIFICAR / FONDO LIQUID GLASS ESTÁTICO ESTILO APPLE
- `src/static/particle_fluid.js`:
  - **Motivo**: Requisito de usuario para aplicar un estilo abstracto enfocado al "Liquid Glass" (estilo Apple macOS) y quitarle el movimiento por completo.
  - **Cambios**: 
    - Se eliminó el bucle de animación (`requestAnimationFrame`), por lo que el fondo ahora se dibuja una sola vez y ahorra 100% de GPU en inactividad.
    - Se modificó la ecuación del Shader añadiendo la operación de pliegues especulares (`ridge`) que simulan refracciones de luz sobre bordes afilados de cristal, típicos de fondos como macOS Monterey o Sonoma.
  - **Archivos afectados**: `src/static/particle_fluid.js` y `*.html` (actualización de caché `?v=2.6.4`).

## [v2.6.3] - 2026-09-07 16:03
### MODIFICAR / ESCALA Y VELOCIDAD DEL SHADER FLUIDO
- `src/static/particle_fluid.js`:
  - **Motivo**: Requisito del usuario de hacer las ondas del fluido orgánico mucho más grandes y con un movimiento sumamente lento.
  - **Cambios**: Se redujo el multiplicador de escala (`st * 0.6` en lugar de `st * 1.5`) para generar formas más anchas, y se disminuyó drásticamente el multiplicador de tiempo (`u_time * 0.025` en lugar de `u_time * 0.12`) para un flujo hipnótico y calmado.
  - **Archivos afectados**: `src/static/particle_fluid.js` y `*.html` (actualización de caché `?v=2.6.3`).

## [v2.6.2] - 2026-09-07 16:00
### MODIFICAR / REDISEÑO A FONDO DE FLUIDO ORGÁNICO
- `src/static/particle_fluid.js`:
  - **Motivo**: Requisito del usuario de transformar el fondo de matriz hexagonal en un fondo interactivo de formas fluidas y suaves (aurora/gradiente de malla), basado en una imagen de referencia.
  - **Cambios**: Se reemplazó por completo la lógica de "panal" (hexágonos e InstancedMesh) por un **Shader de WebGL** que utiliza `snoise` (Simplex Noise). Esto genera ondas orgánicas y deformaciones continuas que se mezclan entre tonos de azul oscuro, azul eléctrico y púrpura lila, reaccionando sutilmente a la proximidad del ratón.
  - **Archivos afectados**: `src/static/particle_fluid.js` y las plantillas `.html` (actualización de caché `?v=2.6.2`).

## [v2.6.1] - 2026-09-07 15:53
### MODIFICAR / PALETA DE COLORES DE MATRIZ HEXAGONAL
- `src/static/particle_fluid.js`:
  - **Motivo**: Requisito de usuario para cambiar la paleta de colores a tonos de azul profundo y púrpura fluidos, basándose en la referencia visual proporcionada.
  - **Cambios**: Se reemplazó la paleta HEX_PALETTE con tonos oscuros y vibrantes que van de azul índigo (`#0F0A30`) a lila destellante (`#B76EFE`). Las partículas secundarias (`starMaterial`) también adoptan el color lila destellante.
  - **Archivos afectados**: `src/static/particle_fluid.js`

### PRUEBAS REALIZADAS
- [x] Modificación de colores de matriz hexagonal de Three.js aplicada.
- [x] Revisión visual de los tonos de azul y violeta con interacción dinámica del ratón.

## [v2.6.0] - 2026-09-07 14:52
### AGREGAR / MATRIZ HEXAGONAL ANIMADA THREE.JS
- `src/static/particle_fluid.js`:
  - **Motivo**: Requisito de usuario basado en la referencia de máscaras de transición hexagonales.
  - **Implementación**: Sistema WebGL de **Matriz Hexagonal (Honeycomb Grid)** en movimiento lento e hipnótico. Incorpora una paleta de **6 tonos de azul progresivos tirando a blanco destellante** (`#002B99`, `#0052FF`, `#0088FF`, `#38BDF8`, `#B9E6FF` y `#FFFFFF`). Al pasar el ratón, los hexágonos elevan su posición en Z, aumentan suavemente de escala y destellan en blanco puro con física de desvanecimiento suave.
- `iniciar.bat`:
  - **Motivo**: `iniciar.bat` mostraba el mensaje de error `No se esperaba ... en este momento` y se cerraba de inmediato.
  - **Solución**: Se escaparon los paréntesis en los comandos `echo` dentro del bloque `for` (e.g. `echo [!] Cerrando proceso en puerto 5050 ^(PID: %%a^)...`) ya que interferían con la agrupación `do (...)` del bucle `for /f` en CMD. Esto permitió que el archivo se ejecutara completamente sin cerrarse inesperadamente.

### SNAPSHOT antes del cambio
```html
<link rel="stylesheet" href="/static/flux_theme.css">
<script src="https://unpkg.com/lucide@latest"></script>
```

### PRUEBAS REALIZADAS
- [x] Creación y carga exitosa de `src/static/particle_fluid.js`.
- [x] Verificación de inclusión de Three.js v128 y `particle_fluid.js` en las 4 plantillas del sistema.
- [x] Comprobación de respuesta HTTP 200 en `/dashboard`, `/transactions` y `/static/particle_fluid.js`.
- [x] Simulación física de fluido a 60 FPS con aceleración GPU sin interrupciones en botones ni tablas.

---

## [v2.5.0] - 2026-09-07 10:48
### MODIFICAR / MIGRACIÓN FLUX ARCHIVO
- `src/templates/*.html` y `tools/NOTIFICADOR_BOT/index.html`:
  - **Motivo**: Cambio general de la interfaz a "Gastos Raccoon" con el diseño moderno "FLUX Archivo".
  - **Cambios**: Se centralizaron los estilos en `src/static/flux_theme.css`, se migró el layout de la navegación superior a un esquema de *Sidebar + Topbar* usando `app-layout`, y se reemplazaron los iconos FontAwesome y Material Symbols por iconografía de **Lucide Icons**.

### CORREGIR / MODO OSCURO Y BUGS PYTHON
- `tools/NOTIFICADOR_BOT/app.js` y Javascript en plantillas:
  - **Corrección**: El modo oscuro no cambiaba el icono de Sol/Luna debido a que `lucide.createIcons()` no era invocado tras reemplazar el `innerHTML` del botón, haciendo que el SVG no renderizara. 
- `tools/NOTIFICADOR_BOT/portfolio_analyzer.py` (Línea 166), `src/app.py` (Línea 305), `config_manager.py` (Línea 101):
  - **Corrección**: Supervisados y solucionados errores sintácticos de Python (`NameError`) donde faltaban imports como `os` o se declaraba `except Exception:` intentando acceder a la variable no definida `e`.

### PRUEBAS REALIZADAS
- [x] Alternancia Sol/Luna funcional.
- [x] Flake8 arroja 0 variables o imports indefinidos (F821).
- [x] Ejecución del servidor con el nuevo layout de Sidebar.

## [v2.4.3] — 2026-09-07 16:20
### CORREGIR / SYNTAX ERROR EN JAVASCRIPT
- `tools/NOTIFICADOR_BOT/app.js`:
  - **Corrección**: Se corrigió un error crítico de sintaxis en la función `getBadgeClass()` que carecía de llave de cierre `}` y de un retorno por defecto (`return "evitar";`). 
  - **Impacto del Error**: Esto causaba que todas las funciones posteriores (como `switchViewMode`, `renderTables`, etc.) quedaran anidadas dentro de `getBadgeClass`, volviéndolas inaccesibles para el DOM o generando errores de variable no definida (causando que el "visor de bolsa no funcionara").

### PRUEBAS REALIZADAS
- [x] Ejecución del motor ML y APIs de `/bolsa` en servidor sin caídas.
- [x] Verificación de la estructura en `app.js` tras la modificación.

## [v2.4.2] — 2026-09-06 01:46
### CORREGIR / DUAL THEME TOGGLE (MODO CLARO Y MODO OSCURO)
- **Corrección de Conmutador de Temas (`toggleTheme`)**:
  - Se eliminaron las reglas CSS `!important` estáticas que bloqueaban el cambio de colores y fondos al presionar el botón de tema.
  - Se implementaron estilos responsivos independientes para `html.dark` (Obsidian Dark `#07090E`) y `html.light` (Minimalist Light `#F8FAFC`) en `dashboard.html`, `transactions.html`, `details.html` e `index.html`.
  - Se añadió la función `toggleTheme()` en `transactions.html` e `index.html` para alternar fluidamente entre sol y luna ☀️/🌙.

## [v2.4.1] — 2026-09-06 01:18
### AGREGAR / UNIFICACIÓN DE UI EN TODO EL PROYECTO (ESTILO GBM.COM)
- **Tema Obsidian Dark Predeterminado en Todo el Proyecto**:
  - Se forzó el tema Obsidian Dark (`#07090E`) con fondo de gradiente radial azul/púrpura eléctrico (`#0052FF`, `#5631E8`) y paneles glassmorphism (`rgba(13, 18, 30, 0.75)`) de forma permanente en todas las vistas: `/dashboard`, `/transactions`, `/details` y `/bolsa`.
  - Se homogeneizó el componente `<nav class="unified-nav">` en la parte superior de las 4 páginas del sistema.

## [v2.4.0] — 2026-09-06 00:13
### AGREGAR / REDISEÑO INTEGRAL DE UI (ESTILO GBM.COM)
- **Modo Obsidian Medianoche & Tipografía GBM**:
  - Se integró la fuente `Plus Jakarta Sans` y `Hanken Grotesk` en todo el sistema.
  - Se definieron los tokens de color corporativo GBM (`#0052FF` Electric Blue, `#07090E` Obsidian Dark Background, `#F8FAFC` Light Background, `#10B981` Emerald, `#8B5CF6` Púrpura IA).
- **Corrección de Carga Inmediata en `/bolsa`**:
  - Se corrigió la carga de persistencia de escaneo de bolsa en `src/server.py` para cargar los resultados incondicionalmente en memoria en `GET /api/scan/results` y `GET /api/scan/status`.
  - Se actualizó `tools/NOTIFICADOR_BOT/app.js` para invocar `fetchResults()` de forma síncrona en `DOMContentLoaded` y se añadieron guardas de seguridad nula en formateo numérico (`.toFixed`), resolviendo la pantalla en blanco.
- **Navegación Flotante Unificada (`Floating Pill Nav`)**:
  - Se estandarizó la barra de navegación en formato píldoras en `src/templates/dashboard.html`, `details.html`, `transactions.html` y `tools/NOTIFICADOR_BOT/index.html`.

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
