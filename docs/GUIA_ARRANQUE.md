# Guía de Arranque - Suprema de Gastos

Esta guía unifica las instrucciones para arrancar los diferentes módulos del sistema (Local, Cloudflare y Visor).

## 1. Modo Local (Escritorio / Servidor Flask)
El modo local inicia el backend de Flask, la interfaz gráfica y los procesos asociados.

### Arranque recomendado
Ejecuta el archivo `iniciar.bat` en la raíz del proyecto. Este script se encarga de:
- Liberar los puertos 5000 y 5050.
- Buscar actualizaciones seguras (`git pull`).
- Crear o validar el entorno virtual (`.venv`) y las dependencias (`requirements.txt`).
- Ejecutar el servidor (`src/app.py`).

### Arranque manual
1. Activa el entorno virtual: `.\.venv\Scripts\activate`
2. Instala dependencias si es necesario: `pip install -r requirements.txt`
3. Ejecuta la aplicación: `python src/app.py`

## 2. Visor de Inversiones (Módulo Bolsa)
Actualmente el visor de inversiones se sirve a través de la misma aplicación local de Flask en la ruta `/bolsa`.
- Al iniciar `iniciar.bat`, la ruta del visor queda disponible automáticamente.
- Asegúrate de configurar tus credenciales o claves en `visor_config.json`.

## 3. Modo Cloudflare (Web remota)
El proyecto cuenta con un Worker de Cloudflare y una interfaz web remota.

### Desarrollo y pruebas locales del Worker
1. Navega a la carpeta de Cloudflare: `cd cloudflare`
2. Instala las dependencias (si no las tienes): `npm install`
3. Inicia el servidor de desarrollo de Wrangler: `npx wrangler dev`

### Despliegue a Producción
1. Para actualizar el frontend: `npm run deploy-pages` (o comando equivalente en tu pipeline).
2. Para actualizar el Worker y migraciones D1: `npx wrangler deploy`

## Recomendaciones de Seguridad
- Antes de realizar migraciones o cambios mayores, ejecuta `backup_db.bat` para respaldar las bases de datos y configuraciones.
- Nunca commitees archivos como `.env` o las bases de datos (`.db`).
