# Actualizaciones portátiles desde GitHub

La aplicación consulta GitHub Releases al iniciar, en un hilo separado. Esto funciona en otra computadora aunque la carpeta no tenga `.git` ni Git instalado.

## Configuración necesaria

En `.env`, indicar el repositorio real:

```env
APP_UPDATE_REPOSITORY=wbfuhn-cloud/SUPREMA-DE-GASTOS
APP_UPDATE_ENABLED=1
```

También puede guardarse `github_repository` en `src/version.json`. La variable de entorno tiene prioridad.

El repositorio `wbfuhn-cloud/SUPREMA-DE-GASTOS` también está configurado como respaldo en `src/version.json`; por eso las instalaciones portátiles funcionan aunque la variable no exista.

## Publicar una versión

1. Actualizar `app_version` en `src/version.json`.
2. Confirmar y subir los cambios al repositorio GitHub configurado.
3. Crear y subir una etiqueta semántica, por ejemplo `v3.4.0`.
4. El workflow `.github/workflows/release.yml` crea automáticamente un ZIP y lo adjunta a GitHub Releases.

En el siguiente arranque, las instalaciones remotas detectarán la etiqueta y descargarán el ZIP en `downloads/updates/`. También se genera un archivo `.sha256` y `update-status.json`.

## Seguridad y comportamiento

- La consulta tiene timeout y un fallo de Internet no bloquea el programa.
- Solo se aceptan assets `.zip` o `.exe` de la publicación más reciente.
- Se valida el tamaño anunciado por GitHub y se calcula SHA-256 local.
- La aplicación no se sobrescribe mientras está abierta. La actualización descargada se aplica manualmente con el programa cerrado.
- `APP_UPDATE_ENABLED=0` deshabilita la comprobación.
