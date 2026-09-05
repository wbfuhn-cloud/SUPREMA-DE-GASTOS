# Documentación de Exportación de Reporte y Envío a Telegram

Este documento explica el flujo técnico implementado para generar un reporte de transacciones como imagen y enviarlo automáticamente a un bot de Telegram.

## 1. Frontend: Generación y Captura de la Imagen

La lógica principal se encuentra en el archivo `src/transactions_view.py`, específicamente en la función JavaScript `exportToImage()`.

### Paso 1: Recopilación de Datos
La función primero recopila solo las filas visibles de la tabla de transacciones, respetando los filtros aplicados por el usuario (búsqueda, fecha, categoría, tipo).

```javascript
// Obtener filas visibles
const visibleRows = Array.from(document.querySelectorAll('#transactions-table tbody tr'))
    .filter(row => row.style.display !== 'none');
```

### Paso 2: Construcción del Reporte
En lugar de capturar la tabla tal como se ve en pantalla (que puede tener botones de borrar, inputs editables, etc.), creamos un contenedor temporal (`export-container`) con un diseño optimizado para reporte impreso.

Este contenedor incluye:
- Encabezado con título y subtítulo.
- Fecha y hora de generación.
- Resumen de los filtros aplicados.
- Estadísticas (Total de transacciones y Monto total).
- Una tabla limpia con solo texto (sin inputs ni botones).
- Pie de página.

Este contenedor se posiciona fuera de la pantalla (`left: -9999px`) para que el usuario no lo vea, pero el navegador sí lo renderice.

### Paso 3: Conversión a Imagen (Canvas)
Utilizamos la librería **html2canvas** para convertir este contenedor HTML en un elemento `<canvas>` (imagen).

```javascript
const canvas = await html2canvas(exportContainer, {
    backgroundColor: '#ffffff',
    scale: 2, // Mejor resolución
    logging: false
});
```

### Paso 4: Descarga Local y Envío
Una vez generada la imagen en formato Base64 (`canvas.toDataURL('image/png')`):
1. **Descarga Local:** Se crea un enlace temporal `<a>` para que el usuario descargue la imagen en su PC.
2. **Envío al Servidor:** Se envía la misma cadena Base64 al backend mediante `fetch`.

```javascript
await fetch('/api/send-to-telegram', {
    method: 'POST',
    body: JSON.stringify({ 
        image: imageData,
        caption: '📂 **Reporte de Transacciones**'
    })
});
```

---

## 2. Backend: API y Bot de Telegram

El servidor (`src/server.py`) expone un endpoint para recibir la imagen y utiliza la instancia del bot (`src/bot.py`) para enviarla.

### Endpoint `/api/send-to-telegram`
1. Recibe el JSON con la imagen en Base64.
2. Decodifica el Base64 a bytes puros de imagen.
3. Guarda la imagen en un archivo temporal (`tempfile`).
4. Obtiene la instancia del bot (`bot_instance`) que se pasó al iniciar el servidor.

### Envío Asíncrono
Dado que Flask corre en un hilo y el bot de Telegram (`python-telegram-bot`) corre en un loop asíncrono (`asyncio`), utilizamos `run_coroutine_threadsafe` para inyectar la tarea de envío en el loop del bot.

```python
# src/server.py
future = asyncio.run_coroutine_threadsafe(
    bot_instance.send_photo(tmp_path, caption=caption),
    loop
)
success, message = future.result()
```

### El Bot (`src/bot.py`)
El bot tiene un método `send_photo` que simplemente toma la ruta del archivo y lo envía al `chat_id` configurado (el último chat con el que interactuó el usuario).

```python
# src/bot.py
async def send_photo(self, photo_path, caption=None):
    await self.application.bot.send_photo(
        chat_id=self.chat_id,
        photo=open(photo_path, 'rb'),
        ...
    )
```

---

## Resumen del Flujo

1. **Usuario** hace clic en "Exportar Imagen".
2. **JS** construye un HTML limpio oculto.
3. **html2canvas** "toma una foto" de ese HTML.
4. **JS** descarga la foto al PC del usuario.
5. **JS** envía la foto (Base64) a Flask.
6. **Flask** convierte Base64 a archivo temporal.
7. **Flask** ordena al **Bot** enviar ese archivo.
8. **Bot** envía la foto al chat de Telegram del usuario.
