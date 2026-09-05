# Despliegue web

Esta carpeta contiene la version web inicial del Asistente Financiero.

## Componentes

- `src/index.js`: API de gastos en Cloudflare Workers.
- `web/index.html`: interfaz web inicial.
- `migrations/0001_initial.sql`: esquema de Cloudflare D1.
- `wrangler.jsonc`: configuracion de Worker y D1.

## Configuracion local

1. Instalar Wrangler: `npm install`.
2. Crear una base D1: `npx wrangler d1 create gastos`.
3. Copiar el `database_id` devuelto en `wrangler.jsonc`.
4. Aplicar el esquema local: `npm run db:local`.
5. Crear un token local: `npx wrangler secret put APP_ACCESS_TOKEN`.
6. Iniciar: `npm run dev`.

El token se envia desde el navegador como `Authorization: Bearer <token>`.
No guardar el token en este repositorio.

## Publicacion

1. Iniciar sesion: `npx wrangler login`.
2. Aplicar migraciones remotas: `npm run db:remote`.
3. Guardar el secreto remoto: `npx wrangler secret put APP_ACCESS_TOKEN`.
4. Publicar: `npm run deploy`.

## Correo BAZ

La integracion del correo se agregara como una tarea programada, no como un
hilo permanente. Usara Microsoft Graph con OAuth y escribira en `email_log`
antes de crear un gasto, evitando duplicados.

La autorizacion requiere configurar una URL de retorno HTTPS en la aplicacion
de Microsoft. Las credenciales y tokens deben permanecer como secretos de
Cloudflare, nunca en `wrangler.jsonc`, HTML o Git.
