# Plan global de mejoras — Suprema de Gastos

## Propósito

Convertir el proyecto en una aplicación financiera consistente, rápida y mantenible, con una transición visual de tema claro/oscuro que se sienta premium sin consumir recursos innecesarios ni romper la interacción en escritorio o móvil.

El plan cubre la aplicación local de Flask, la web publicada en Cloudflare y el visor de inversiones. Se divide en etapas para que cada entrega se pueda probar y revertir de forma aislada.

## Diagnóstico de partida

El repositorio contiene tres productos relacionados, pero no completamente unificados:

1. Aplicación local: GUI de escritorio, Flask, Telegram, Gemini, correo BAZ y SQLite/D1.
2. Web Cloudflare: Worker, D1 y un dashboard independiente con token de acceso.
3. Visor de inversiones: escáner técnico, aprendizaje adaptativo y modelo ML servido desde `/bolsa`.

El tema visual se implementa con CSS, `particle_fluid.js`, `liquidGL.js`, Tailwind y scripts repetidos en cada plantilla. Las tres plantillas locales (`dashboard.html`, `transactions.html` y `details.html`) y el visor de Bolsa tienen inicialización propia. LiquidGL añade otra capa WebGL y genera capturas con `html2canvas`; junto al fondo Three.js, esto crea riesgo de uso alto de GPU/CPU, animaciones duplicadas y diferencias entre vistas.

Hallazgos técnicos que justifican la prioridad visual:

- `particle_fluid.js` mantiene un `requestAnimationFrame` continuo, incluso cuando la página no está visible.
- El renderer del fondo usa `preserveDrawingBuffer: true`, opción costosa que no se necesita para dibujar un fondo animado normal.
- El tema se consulta desde el DOM en cada cuadro y la transición actual avanza por cuadro (`+0.12`), por lo que su duración cambia según la frecuencia real de la pantalla.
- Cada vista llama LiquidGL sobre grupos completos de tarjetas; el costo crece con la cantidad de elementos visibles.
- Las implementaciones locales comparten la clave `theme`, pero repiten funciones, iconos e inicialización.

## Objetivos medibles

| Objetivo | Criterio de aceptación |
| --- | --- |
| Cambio de tema | Respuesta visual inmediata al pulsar y transición principal de 220 a 320 ms. |
| Fluidez | Ninguna tarea larga mayor a 50 ms durante el cambio; cuadros dentro de 16.7 ms en el perfil de escritorio y 33.3 ms en el perfil móvil definidos para pruebas. |
| Interacción | Botones, formularios, tablas y scroll responden durante la transición. |
| Accesibilidad | Respeta `prefers-reduced-motion`, contraste AA y no depende solo del color. |
| Consistencia | Un único estado de tema para Dashboard, Transacciones, Analíticos y Bolsa. |
| Rendimiento | Sin capturas completas de página por cada cambio de tema ni renderizadores WebGL duplicados. |
| Estabilidad | Sin IDs HTML repetidos, rutas frontend inexistentes ni pruebas obsoletas bloqueando cambios. |
| Respuesta | INP menor a 200 ms en el cambio de tema y sin desplazamiento de diseño visible (`CLS` atribuible al cambio igual a 0). |

Antes de implementar, fijar dos perfiles reproducibles de prueba: un navegador y resolución de escritorio, y un teléfono Android físico o emulado de gama media. Registrar la línea base con DevTools Performance para comparar cada entrega.

## Arquitectura visual propuesta

### Una fuente de verdad para el tema

Crear un módulo único, por ejemplo `src/static/theme-controller.js`, cargado por las cuatro vistas locales y, adaptado al Worker, por la web Cloudflare.

Responsabilidades:

- Leer el tema guardado en `localStorage` antes del primer render.
- Aplicar únicamente `data-theme="dark"` o `data-theme="light"` en `<html>`.
- Exponer `window.ThemeController.toggle()` y `window.ThemeController.set(theme)`.
- Emitir el evento `themechange` con el tema anterior, el nuevo y si se debe reducir movimiento.
- Sincronizar iconos, gráficas y fondo sin duplicar lógica en cada plantilla.
- Usar el color del sistema como preferencia inicial cuando el usuario todavía no ha elegido un tema.

La clase `dark` de Tailwind puede mantenerse mientras sea necesaria, pero debe derivarse de `data-theme`; no debe ser una segunda fuente de estado.

### Sistema de tokens visuales

Centralizar en `flux_theme.css` los colores, transparencias, bordes, sombras y duraciones. Todas las pantallas deben consumir variables, en lugar de fijar colores dentro de HTML o JavaScript.

Variables mínimas:

```css
:root {
  --theme-duration: 260ms;
  --theme-ease: cubic-bezier(.22, 1, .36, 1);
  --bg-base: ...;
  --bg-aurora-a: ...;
  --bg-aurora-b: ...;
  --surface: ...;
  --surface-border: ...;
  --text-primary: ...;
  --text-secondary: ...;
  --focus-ring: ...;
}
```

Esto permite que la transición sea una propiedad del sistema, no una serie de ajustes independientes por archivo.

## Experiencia de cambio de tema recomendada

### Decisión técnica

Usar `document.startViewTransition()` como mejora progresiva cuando el navegador la soporte. Esta API conserva visualmente el estado anterior y permite revelar el nuevo tema desde el botón sin capturar la página con JavaScript. Para navegadores sin soporte, usar una capa CSS fija de color sólido con la misma geometría radial. El estado del tema debe cambiar una sola vez y ambos caminos deben terminar en el mismo evento `themechange`.

No hacer que la transición dependa de View Transitions, WebGL ni `html2canvas`: cualquiera de esas capacidades puede faltar y el cambio de colores debe seguir funcionando.

### Secuencia visual

1. El usuario pulsa el control de tema.
2. El botón confirma el gesto en menos de 80 ms: icono rota suavemente 90 grados y cambia de luna a sol, o viceversa.
3. Un velo radial nace desde el centro del botón y expande el nuevo tema por la pantalla durante 260 ms.
4. El fondo cambia primero; las superficies de vidrio, texto y bordes siguen con un retraso de 25 a 45 ms.
5. Las gráficas actualizan sus colores sin destruir ni volver a crear sus instancias.
6. El fondo animado adapta paleta e intensidad; nunca bloquea el cambio de tema.

La transición debe comunicar continuidad. No debe hacer una captura completa de la página, congelar tarjetas, oscurecer los controles ni producir destellos blancos.

### Implementación preferida: View Transitions + respaldo CSS ligero

En navegadores compatibles, animar los pseudoelementos `::view-transition-old(root)` y `::view-transition-new(root)` con `clip-path: circle()` desde las coordenadas del botón. El radio final debe calcularse con la distancia a la esquina más lejana para cubrir cualquier resolución.

Como respaldo, usar una capa fija `#theme-transition` con `pointer-events: none` y color tomado de los tokens. El controlador define sus coordenadas con la posición del botón y activa la misma expansión radial. Al terminar o cancelarse, debe retirar clases, estilos temporales y escuchadores.

Ventajas:

- Evita incorporar y mantener una captura manual de toda la página.
- Funciona en WebGL deshabilitado, pantallas táctiles y navegadores modernos.
- Mantiene controles operables durante la animación.
- Reduce el costo frente a `html2canvas`.

### Fondo animado

Mantener `particle_fluid.js` como mejora estética opcional, pero desacoplarlo de la transición principal.

- Usar un solo canvas para cada documento.
- Crear el renderer con `preserveDrawingBuffer: false` y medir si `antialias` aporta una mejora visible en un shader de pantalla completa; desactivarlo si no la aporta.
- No ocultarlo en oscuro; bajar su opacidad y renderizar una paleta nocturna real.
- Cambiar los uniformes de color con tiempo transcurrido (`performance.now()`), no sumando una cantidad fija por cuadro.
- Pausar el loop al perder visibilidad (`document.visibilityState === 'hidden'`).
- Limitar `devicePixelRatio` a 1.25 en móvil y 1.5 o 2 en escritorio según rendimiento.
- Ajustar calidad a partir del tiempo de cuadro medido: bajar resolución o limitar a 30 FPS solo si el perfil móvil no sostiene el presupuesto de 33.3 ms. `navigator.hardwareConcurrency` puede ayudar como indicio, pero no debe decidir por sí solo.
- Apagarlo con `prefers-reduced-motion` y ofrecer fondo CSS estático equivalente.
- Escuchar cambios de `prefers-reduced-motion` durante la sesión y liberar renderer, geometría, material y textura cuando el canvas se desactive.

### Vidrio LiquidGL

`liquidGL.js` usa WebGL y capturas con `html2canvas`; debe reservarse para pocos elementos visibles y no para todas las tarjetas de una página extensa.

Estrategia:

- Usar CSS glassmorphism como base universal.
- Activar LiquidGL solamente en tarjetas hero o módulos destacados de escritorio.
- Desactivarlo por defecto en móvil y en páginas largas de auditoría/transacciones.
- No volver a ejecutar `liquidGL()` al alternar tema.
- Reemplazar el recálculo completo por actualización de variables CSS y, si hace falta, una única recaptura programada tras terminar la transición.
- Medir el número máximo de lentes activos; objetivo inicial: 3 en Dashboard, 0 en Transacciones, 0 en Analíticos y 2 en Bolsa.

## Etapa 0 — Seguridad operativa y línea base

Prioridad: crítica. Antes de rediseñar.

1. Crear respaldo de las bases SQLite y de las configuraciones antes de migraciones.
2. Eliminar la ejecución automática de `git reset --hard` desde `iniciar.bat`; un actualizador no debe borrar cambios locales sin una copia verificable.
3. Separar scripts auxiliares y ajenos al producto (`mavic_toolkit`, optimización de Windows) del flujo de gastos.
4. Añadir una guía única de arranque para modo local, Cloudflare y visor de inversiones.
5. Registrar versión de aplicación, esquema de base y fecha de despliegue en un lugar único.

Resultado esperado: arranque predecible y sin acciones destructivas implícitas.

## Etapa 1 — Saneamiento estructural

Prioridad: crítica. Dependencia de las etapas siguientes.

1. Corregir el HTML duplicado de `tools/NOTIFICADOR_BOT/index.html`; conservar una sola instancia de cada panel e ID.
2. Retirar o aislar el servidor legado `tools/NOTIFICADOR_BOT/server.py`; el servidor canónico debe ser `src/server.py` si el visor sigue integrado en `/bolsa`.
3. Crear un inventario de rutas frontend y validarlo contra las rutas Flask/Worker.
4. Implementar o retirar la llamada local a `/api/add-category`.
5. Eliminar referencias al historial de precios ya retirado (`/api/prices/history`) o restituir el módulo de forma deliberada.
6. Unificar `visor_config.json`: definir una sola ubicación y hacer que GUI, servidor y resumen de portafolio la usen.
7. Sustituir `except: pass` por manejo explícito, logging y fallback seguro.
8. Corregir pruebas que esperan la versión anterior de `ExpenseBot`; ninguna prueba debe llamar Telegram, Gemini o servicios remotos sin una marca explícita de integración.

Resultado esperado: una sola ruta de ejecución por función y una base confiable para cambios visuales.

## Etapa 2 — Estado de datos y API

Prioridad: crítica.

1. Normalizar estados a `pending`, `paid` y `unconfirmed`; convertir los registros existentes `PENDING` y `completed` con una migración respaldada.
2. Normalizar tipo a `Normal`, `Deuda` y `Prestamo`.
3. Definir qué significa cada estado para totales, gráficas, deudas y préstamos.
4. Añadir validación de campos editables en backend con una lista permitida; evitar formar columnas SQL directamente desde JSON del cliente.
5. Validar y convertir `year`, límites y offsets antes de construir consultas; en Cloudflare usar parámetros enlazados.
6. Restringir CORS en producción a los dominios reales.
7. Homologar contratos de API entre Flask y Cloudflare: nombres de rutas, payload, respuesta de error, paginación y filtros.
8. Resolver el comportamiento de caché local para que `limit` y `offset` nunca devuelvan una página equivocada.

Resultado esperado: datos consistentes y APIs seguras que alimentan cualquier interfaz.

## Etapa 3 — Sistema unificado de tema

Prioridad: alta.

1. Crear `theme-controller.js` y retirar las funciones `toggleTheme` duplicadas de plantillas y visor.
2. Consolidar tokens de claro y oscuro en `flux_theme.css`.
3. Crear la capa `#theme-transition` y la animación radial basada en la posición del control.
4. Añadir soporte completo para teclado: foco visible, etiqueta accesible y cambio con Enter/Espacio.
5. Mantener el tema seleccionado entre vistas y entre sesiones.
6. Establecer fallback sin JavaScript: colores correctos según `prefers-color-scheme`.
7. Preparar una variante equivalente para `cloudflare/web/index.html`.

Resultado esperado: el tema cambia igual en todas las vistas y se conserva sin destellos al cargar.

## Etapa 4 — Animación clara/oscura de calidad premium

Prioridad: alta.

### Reglas de animación

- Duración estándar: 260 ms.
- Transición de fondo: 280 ms.
- Superficies y texto: 220 ms, retraso de 30 ms.
- Icono del control: 180 ms.
- Nunca animar `width`, `height`, `top`, `left` o filtros costosos en listas grandes.
- Usar `opacity`, `transform`, colores CSS y `clip-path` solo en una capa fija.
- Interrumpir una transición anterior si el usuario vuelve a pulsar; el estado final siempre debe ser correcto.
- Con `prefers-reduced-motion: reduce`, omitir onda y rotación; aplicar el tema directamente sin animación.
- Calcular el progreso por tiempo transcurrido para que 60, 90 y 120 Hz tengan la misma duración percibida.
- Para pulsaciones repetidas, bloquear únicamente la animación visual durante su tramo corto o cancelar la anterior y aplicar el último estado solicitado; probar explícitamente esta carrera.

### Pruebas visuales obligatorias

| Escenario | Resultado esperado |
| --- | --- |
| Dashboard en escritorio | Onda radial limpia, gráficas legibles y sin salto de layout. |
| Transacciones con cientos de filas | Cambio fluido sin congelar scroll ni inputs. |
| Bolsa durante escaneo | El progreso y los botones siguen activos durante el cambio. |
| Móvil gama media | Sin caída perceptible de frames ni canvas de alta resolución. |
| Sin WebGL | CSS completo y transiciones normales. |
| Movimiento reducido | Sin onda, sin rotación y cambio instantáneo accesible. |
| Pulsación doble rápida | Sin tema intermedio, capas huérfanas ni icono desincronizado. |
| Carga y navegación entre vistas | El tema correcto aparece antes del primer render, sin destello claro. |
| 60/90/120 Hz | La duración percibida se mantiene por tiempo, no por número de cuadros. |

## Etapa 5 — Rendimiento y experiencia móvil

Prioridad: alta.

1. Cargar Chart.js, Three.js y LiquidGL solo en las páginas que realmente los necesitan.
2. Aplazar recursos no críticos hasta después del contenido funcional.
3. Crear un presupuesto de rendimiento: JavaScript inicial menor a 300 KB propios, máximo un canvas animado y máximo una actualización visual por frame.
4. Aplicar paginación server-side también a la vista local de transacciones; no renderizar todos los movimientos en HTML inicial.
5. Conservar filtros en URL para que se puedan compartir y restaurar.
6. Usar `requestAnimationFrame` para cambios visuales agrupados y `requestIdleCallback` para recálculos no urgentes.
7. Evitar renderizado de LiquidGL y fondo animado mientras la pestaña está oculta.
8. Medir con Performance API y DevTools: INP, Long Tasks, tiempo por cuadro, CLS y memoria de canvas. Guardar perfil, dispositivo, resolución y escenario para que la comparación sea repetible.

Resultado esperado: interfaz usable en móvil y rápida con bases de datos más grandes.

## Etapa 6 — Dashboard y flujos financieros

Prioridad: media-alta.

1. Definir métricas oficiales: total de gasto, gasto confirmado, pendiente de revisión, deuda por pagar y préstamo por cobrar.
2. Corregir la tarjeta de salud financiera para que use presupuestos y no una constante fija.
3. Añadir creación de categorías con validación y reutilización en todas las vistas.
4. Completar exportación Excel desde ambas plataformas o declarar claramente la plataforma soportada.
5. Añadir confirmación y auditoría de cambios: fecha, operación y origen del movimiento.
6. Separar gastos, deudas y préstamos en visualizaciones claras.
7. Mostrar fuente del dato (`web`, `email`, `legacy`, `Telegram`) y estado de conciliación.

## Etapa 7 — Correo BAZ, Telegram y servicios externos

Prioridad: media.

1. Mantener Regex como primera opción para BAZ y Gemini como fallback con límites claros.
2. Convertir el lector BAZ de Cloudflare en tarea programada con OAuth seguro, como plantea el historial del proyecto.
3. Evitar que el monitor local solicite autorización interactiva desde un hilo de fondo; la autorización debe hacerse desde el script visible.
4. Hacer idempotente cada importación con `message_id` y pruebas de duplicado.
5. Centralizar envío de Telegram en `src/infra/telegram_utils.py`.
6. Añadir reintentos con espera progresiva y trazas sin secretos.

## Etapa 8 — Visor de inversiones

Prioridad: media.

1. Separar claramente el puntaje heurístico, confianza histórica y predicción ML en la interfaz.
2. Mostrar fecha y tamaño de muestra del modelo ML; no presentar una predicción como certeza.
3. Validar el entrenamiento con datos temporales y guardar métricas versionadas.
4. Unificar configuración de watchlist, cartera y alertas.
5. Quitar dependencias no usadas, por ejemplo `yfinance` si el motor ya consulta Yahoo directamente.
6. Añadir límites de concurrencia, cancelación real de escaneo y caché con vencimiento visible.
7. Mantener advertencias de ETF apalancados y añadirlas también a las alertas Telegram.

## Orden recomendado de implementación

1. Etapa 0: respaldo y arranque seguro.
2. Etapa 1: limpiar duplicados, rutas obsoletas y pruebas.
3. Etapa 2: normalizar datos y asegurar API.
4. Etapa 3: controlador y tokens de tema.
5. Etapa 4: transición radial y adaptación de fondo/vidrio.
6. Etapa 5: optimización móvil y presupuesto de rendimiento.
7. Etapas 6 a 8: completar funciones financieras, automatizaciones y bolsa.

## Entregables por versión

### Versión A — Base estable

- Duplicados eliminados.
- Rutas y configuraciones unificadas.
- Pruebas locales sin servicios externos.
- Migración de estados respaldada.

### Versión B — Tema premium

- Controlador único de tema.
- Tokens visuales centralizados.
- Transición radial clara/oscura accesible.
- Fondo WebGL opcional y adaptativo.

### Versión C — Rendimiento y móvil

- Paginación local y carga diferida de librerías.
- LiquidGL limitado a módulos destacados.
- Mediciones de carga y fluidez documentadas.

### Versión D — Producto consolidado

- Contrato API común Flask/Cloudflare.
- Flujos financieros completos y auditables.
- Correo BAZ programado en nube.
- Visor de inversiones estabilizado.

## Criterio final de aceptación

El proyecto estará listo cuando cambiar de claro a oscuro y de oscuro a claro sea inmediato, elegante y consistente en las cuatro vistas; funcione sin WebGL; respete accesibilidad; no genere parpadeos ni bloqueos; y el sistema de datos, API y despliegue tenga una única ruta confiable por función.
