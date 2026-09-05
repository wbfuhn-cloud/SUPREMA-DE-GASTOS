# Historial de continuidad del proyecto

Ultima actualizacion: 2026-08-23

Este documento permite retomar el proyecto despues de apagar la PC.

## Objetivo acordado

Convertir el Asistente Financiero en un sitio web que funcione sin dejar la
computadora encendida y sin depender de la electricidad local.

La primera etapa debe priorizar:

- Dashboard web de gastos.
- Registro manual de gastos.
- Edicion de gastos.
- Categorias existentes y nuevas categorias.
- Deudas: lo que debo.
- Prestamos: lo que me deben.
- Filtros Global, 2025 y 2026.
- Importacion automatica de correos BAZ como siguiente modulo.

Se decidio dejar fuera inicialmente:

- Telegram.
- Fotos de tickets.
- Gemini en el sitio web.
- Busqueda de precios de iPhone, drones y productos.
- Monitor de bolsa y funcionalidades de inversiones para esta migracion.

## Respaldo local

Antes de continuar se creo un respaldo completo fuera del proyecto:

`C:\Users\PLI INGENIERIA\Desktop\ELIMINADOR POTENTE REVO\SUPREMA DE GASTOS_BACKUP_20260822_215913`

Verificacion del respaldo:

- 22,902 archivos.
- Aproximadamente 824 MB.
- Sin errores de copia.
- Se comprobaron hashes SHA-256 de archivos clave.

La base local original sigue en:

`database/expenses.db`

## Cambios previos en la aplicacion local

Se elimino del flujo local la busqueda de precios:

- `src/monitor.py` ahora solo conserva el monitor de correos BAZ.
- `src/app.py` ya no inicia `hilo_precios`.
- Se elimino la ruta `/api/prices/history`.
- Se retiro Playwright de `requirements.txt`.
- `iniciar.bat` ya no abre el buscador ni el visor de precios.
- Se eliminaron los scripts principales de `tools/BUSCADOR DE PRECIOS`.
- Se creo `start.bat`, que llama a `iniciar.bat`.
- Se actualizo `README.md`.

La bolsa/portafolio de `tools/NOTIFICADOR_BOT` no se elimino.

## Infraestructura Cloudflare

Cuenta Cloudflare autenticada con Wrangler.

Subdominio:

`wbfuhn1.workers.dev`

Worker publicado:

`asistente-financiero`

URL publica:

`https://asistente-financiero.wbfuhn1.workers.dev`

Base D1:

- Nombre: `gastos`
- ID: `d7f8d98a-0f9c-46cc-9230-8cffb491e530`
- Region reportada: WNAM/DFW

El secreto `APP_ACCESS_TOKEN` ya fue creado en Cloudflare. Su valor no debe
guardarse en este documento ni enviarse por chat.

## Archivos creados para la web

Dentro de `cloudflare/`:

- `package.json`: comandos de Wrangler.
- `wrangler.jsonc`: Worker, assets y binding D1.
- `src/index.js`: API web y acceso protegido a D1.
- `web/index.html`: dashboard web.
- `migrations/0001_initial.sql`: esquema inicial.
- `migrations/0002_legacy_fields.sql`: columnas heredadas.
- `scripts/export_legacy_sql.py`: exportacion segura de SQLite a SQL.
- `README.md`: instrucciones de despliegue.

## Estado de la base remota

La base D1 contiene las tablas:

- `expenses`
- `email_log`
- `d1_migrations`

Datos migrados desde SQLite:

- Registros: 861.
- Total: $317,755.18.
- Fecha minima: 2025-01-01.
- Fecha maxima: 2026-08-19.
- Dias distintos con movimientos: 300.

Normalizacion de estados aplicada solo en D1:

- 793 gastos normales historicos: `paid`.
- 4 prestamos historicos ya pagados: `paid`.
- 16 deudas pendientes: `pending`.
- 9 prestamos pendientes: `pending`.
- 39 importaciones `AUTO-BAZ`: `source=email`, `unconfirmed`.

La SQLite local no fue modificada.

La migracion se hizo por bloques de 100 registros porque una primera carga
grande fue aceptada parcialmente por D1. La carga final fue verificada contra
la base local y los conteos y totales coinciden.

Los registros migrados tienen `source = 'legacy'` y un `source_id` unico para
evitar duplicarlos en futuras migraciones.

## Funciones web actuales

El sitio publicado permite:

- Conectar usando `APP_ACCESS_TOKEN`.
- Ver el total acumulado.
- Ver cantidad de registros.
- Ver promedio mensual y diario.
- Ver lo que se debe.
- Ver lo que deben.
- Ver categorias con barras de resumen.
- Ver gastos pendientes de confirmacion.
- Filtrar Global, 2025 y 2026.
- Registrar gastos manualmente.
- Seleccionar categorias existentes.
- Crear una categoria nueva.
- Clasificar como gasto normal, deuda o prestamo.
- Editar gastos existentes.
- Editar una transaccion directamente en su propia fila con Guardar y
  Cancelar, sin perder su posicion en la lista.
- La categoria de edicion directa ofrece sugerencias desplegables con las
  categorias guardadas y permite escribir una categoria nueva.
- En la edicion directa, el campo Categoria se convierte en un menu `select`
  real con las categorias guardadas.
- Las fechas de la tabla se muestran como dia, mes abreviado en letras y año
  corto, por ejemplo `15 Jul 26`, manteniendo el formato interno ISO para
  filtros y edicion.
- Cambiar la clasificacion entre gasto normal, deuda y prestamo.
- Cambiar el estado entre pendiente, pagado y sin confirmar.
- Auditar la lista completa del periodo seleccionado, no solo los ultimos 30
  movimientos.
- Buscar la auditoria por texto, rango de fechas, categoria, clasificacion y
  estado.
- Aplicar o limpiar filtros de auditoria con botones visibles y contador de
  filas resultantes.
- Ver en la tabla de auditoria ID, fecha, comercio, categoria, subcategoria,
  metodo, clasificacion, estado, detalles y total.
- Ver los detalles junto al comercio con una columna amplia y legible.
- La auditoria usa una columna ID compacta y una columna Detalles amplia de
  520 px, con ajuste de linea y desplazamiento horizontal.
- La celda Detalles se expande hasta 760 px al hacer clic y permite leer el
  texto largo con ajuste de linea tipo Excel.
- La tabla usa layout fijo para evitar que el texto se desborde sobre la
  columna Accion; las filas crecen automaticamente al envolver Detalles.
- Se definieron anchos independientes para cada columna y recorte seguro en
  campos cortos para evitar que los textos se encimen.
- El layout final usa anchos fijos, ajuste forzado de palabras y filas
  autoajustables para que los detalles largos no se encimen.
- Cada registro muestra si procede de `Correo BAZ` o de `Historico/Web`.
- Se implemento el plan `mejoras cloud`: paginacion server-side de 50 filas,
  filtros SQL, agregados en D1, endpoints de categorias, pendientes y años,
  indices de rendimiento, cache privada corta y validacion de entradas.
- Se reforzo el guardado de ediciones usando tambien la ruta compatible
  `/api/update-expense`, con errores visibles para el usuario.
- Se agrego boton `Eliminar` en cada fila con doble confirmacion antes de
  borrar permanentemente el movimiento.
- La eliminacion quedo oculta en la vista normal y solo aparece como icono
  `x` dentro de la fila cuando se activa la edicion.
- El frontend fue refactorizado con el diseño Financial Clarity, carga
  paralela, skeleton loading, boton Cargar mas, filtros server-side, badges,
  tabla fluida en escritorio y tarjetas en movil.
- Version publicada despues de estas mejoras: `3ae12c93-761d-475c-95cd-8ccebfec4777`.

## Lo que aun falta

Orden recomendado:

1. Completar el dashboard avanzado original: graficas semanales, vistas de
   detalles, exportacion y manejo completo de deudas/prestamos.
2. Crear autenticacion de usuario mas robusta que el token inicial.
3. Migrar el lector BAZ a una tarea programada de Cloudflare.
4. Configurar OAuth de Microsoft Graph con una URL HTTPS de retorno.
5. Guardar tokens OAuth como secretos, nunca en Git.
6. Probar correos reales sin duplicar gastos.
7. Agregar Gemini solo como respaldo para correos cuyo formato no se pueda
   leer con expresiones regulares.
8. Hacer una copia/exportacion periodica de D1.

## Comandos utiles

Desde `cloudflare/`:

```bat
npm install
npx wrangler whoami
npx wrangler d1 list
npm run db:remote
npx wrangler d1 execute gastos --remote --command "SELECT COUNT(*) FROM expenses"
npm run deploy
```

Para volver a publicar despues de cambios:

```bat
cd "C:\Users\PLI INGENIERIA\Desktop\ELIMINADOR POTENTE REVO\SUPREMA DE GASTOS\cloudflare"
npm run deploy
```

## Reglas de seguridad

- No subir `.env`.
- No subir `.token_cache.json`.
- No publicar tokens de Cloudflare.
- No publicar claves de Gemini.
- No publicar contrasenas de correo.
- No borrar `database/expenses.db` hasta confirmar varias copias de D1.
- Antes de una migracion destructiva, crear otro respaldo.

## Ultimo punto conocido

La web esta publicada y los 861 gastos ya estan en D1. El dashboard web
funciona con filtros, categorias, deudas, prestamos, edicion y cambio de
estado. La auditoria muestra la lista completa mediante paginas de 50 filas y
permite editar en la misma fila. El siguiente
trabajo debe ser completar el lector automatico de correo BAZ y terminar las
funciones avanzadas del dashboard original.
