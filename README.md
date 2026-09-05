# Bot de Gastos con IA

Bot automatizado que analiza fotos de recibos usando Google Gemini AI y guarda los gastos en una base de datos SQLite.

## Características

- 📸 **Análisis de Tickets**: Sube una foto y extrae automáticamente: fecha, monto, tienda, categoría
- 🎤 **Notas de Voz**: Dicta tus gastos y el bot los procesa con IA
- ✏️ **Edición Interactiva**: Modifica datos antes de guardar con botones o texto
- 📊 **Dashboard Web**: Visualiza tus gastos con gráficos interactivos
- 🗄️ **Base de Datos SQLite**: Almacenamiento robusto y eficiente
- 🌐 **Acceso Remoto**: Dashboard accesible desde cualquier dispositivo

## Instalación

1. Clona el repositorio
2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Configura tu archivo `.env` con:
   ```
   TELEGRAM_BOT_TOKEN=tu_token_aqui
   GOOGLE_API_KEY=tu_api_key_aqui
   ```
4. Ejecuta `start.bat` o `iniciar.bat`

## Uso

1. Inicia el bot desde la GUI
2. En Telegram:
   - Envía una foto del ticket
   - El bot la analizará y guardará en la base de datos
3. Accede al dashboard web para ver tus gastos

## Estructura del Proyecto

```
├── src/
│   ├── bot.py           - Bot de Telegram
│   ├── analyzer.py      - Análisis con Gemini AI
│   ├── database.py      - Gestión de base de datos SQLite
│   ├── dashboard.py     - Generación de dashboard HTML
│   ├── server.py        - Servidor web Flask
│   ├── config.py        - Configuración centralizada
│   └── excel_export.py  - Exportación a Excel (opcional)
├── database/
│   └── expenses.db      - Base de datos SQLite
├── start.bat            - Lanzador de la aplicación
├── iniciar.bat          - Verificación y arranque
├── main.py              - Punto de entrada
└── requirements.txt     - Dependencias
```

## Solución de Problemas

### Error: "Conflict: terminated by other getUpdates request"

Este error significa que ya hay otra instancia del bot corriendo. **Solución:**

1. Ejecuta `stop_bot.bat` para detener todas las instancias
2. Espera 5 segundos
3. Ejecuta `start.bat` nuevamente

**O manualmente:**
```bash
taskkill /F /IM python.exe /T
```

### Problemas de cuota de API

Si tienes problemas de cuota en el futuro:

1. Ejecuta `python tools/check_models.py` para ver modelos disponibles
2. Actualiza `src/analyzer.py` línea 20 con otro modelo
3. Los modelos gemini-2.5-x suelen tener mejor cuota

## Archivos Importantes

- `src/bot.py` - Lógica del bot de Telegram
- `src/analyzer.py` - Análisis con Gemini
- `src/database.py` - Gestión de base de datos SQLite
- `database/expenses.db` - Base de datos de gastos
- `.env` - Configuración (tokens y claves)
