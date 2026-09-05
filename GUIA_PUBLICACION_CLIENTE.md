# 🚀 GUÍA PASO A PASO: CÓMO SUBIR TU SIMULACIÓN Y OBTENER LA URL PARA EL CLIENTE

Esta guía explica detalladamente cómo publicar la aplicación web interactiva en 3D para que tu cliente pueda abrirla directamente desde cualquier navegador (PC, Tablet o Celular) mediante una URL pública y limpia.

---

## ⚡ MÉRITO 1: PUBLICACIÓN AUTOMÁTICA EN 1-CLIC (RECOMENDADO)

En la raíz de la carpeta de tu proyecto existe un ejecutable preparado para hacer todo el proceso en segundos:

### **`COMPARTIR_CLIENTE_CLOUDFLARE.bat`**

### **Pasos para publicar:**

1. **Prepara el archivo del cliente:**
   - Diseña o ajusta la simulación en tu programa.
   - Guarda el archivo de proyecto `.acoust` dentro de la carpeta:
     `PARA CLIENTE\Sin_t_tulo.acoust`
   
2. **Ejecuta el script:**
   - Haz **doble clic** sobre el archivo `COMPARTIR_CLIENTE_CLOUDFLARE.bat`.

3. **¿Qué hace el script automáticamente?**
   - Compila la aplicación web completa en producción (carpeta `dist`).
   - Copia los archivos 3D (`domo.obj`) y la configuración acústica del cliente.
   - Sube todo el paquete a la nube utilizando **Surge.sh** (hosting gratuito, ilimitado y ultra-rápido).

4. **Obtén la URL:**
   - Al finalizar, la consola mostrará la URL pública lista para copiar y enviar:
   ```text
   =====================================================================
   ¡LISTO! PROYECTO PUBLICADO CON ÉXITO
   =====================================================================

   COPIA Y MANDA ESTA URL A TU CLIENTE:

        https://simulacion-ondas-3d.surge.sh

   (El cliente entrará directo al simulador 3D con tus bocinas
    sin ver pantallas molestas ni advertencias raras).
   =====================================================================
   ```

---

## 🎨 CÓMO CAMBIAR LA URL O PERSONALIZAR EL NOMBRE DEL SUBDOMINIO

Si deseas que la URL tenga el nombre de tu cliente (por ejemplo: `https://evento-salom-acustica.surge.sh`), puedes personalizar el archivo `.bat`:

1. Haz clic derecho sobre `COMPARTIR_CLIENTE_CLOUDFLARE.bat` y selecciona **Editar** (o Abrir con Bloc de Notas).
2. Busca la línea 44:
   ```bat
   call %NPX_CMD% --yes surge ./dist simulacion-ondas-3d.surge.sh
   ```
3. Cambia `simulacion-ondas-3d.surge.sh` por el nombre que quieras, asegurándote de conservar el `.surge.sh` al final:
   ```bat
   call %NPX_CMD% --yes surge ./dist cliente-proyecto-x.surge.sh
   ```
4. Guarda el archivo `.bat` y vuelve a ejecutarlo.

---

## 🌐 OPCIÓN B: SUBIDA MANUAL A VERCEL / NETLIFY (DRAG & DROP)

Si prefieres usar una plataforma como **Vercel** o **Netlify**:

### **Pasos:**
1. Ejecuta primero `INICIAR_SIMULADOR.bat` o en la consola corre:
   ```bash
   npm run build
   ```
2. Esto generará la carpeta **`dist`** en tu proyecto.
3. Entra a [Vercel.com](https://vercel.com) o [Netlify.com](https://netlify.com).
4. Crea una cuenta gratuita y ve a la sección **Deploy / Add New Project**.
5. **Arrastra la carpeta `dist`** dentro de la zona de subida del navegador.
6. En menos de 10 segundos te entregará una URL como `https://tu-proyecto.vercel.app`.

---

## 📁 OPCIÓN C: COMPARTIR ARCHIVOS CRUDOS (.ACOUST / .DXF)

Si el cliente no solo quiere ver la simulación en web, sino que también tiene la aplicación instalada y desea los archivos fuente de trabajo:

1. Ve a la carpeta `PARA CLIENTE\`.
2. Ubica los archivos:
   - Archivo de simulación: `Sin_t_tulo.acoust`
   - Planos CAD / DXF: `reparado_faces.dxf` o `test5.dxf`
3. Sube los archivos a tu servicio preferido de transferencia:
   - **WeTransfer** (`wetransfer.com`)
   - **Google Drive** (`drive.google.com`)
   - **Dropbox** (`dropbox.com`)
4. Comparte el enlace de descarga directamente con el cliente.

---

## 🛠️ RESOLUCIÓN DE PROBLEMAS HABITUALES

| Problema | Causa | Solución |
| :--- | :--- | :--- |
| **Error: `'npm'` o `'npx'` no se reconoce** | Node.js no está instalado en la PC. | Descarga e instala Node.js LTS desde [https://nodejs.org/](https://nodejs.org/). |
| **El cliente entra y ve una versión vieja** | El navegador guardó caché anterior. | Pide al cliente que presione `Ctrl + F5` o use una ventana de incógnito. |
| **¿La URL caduca?** | No, las URLs creadas en Surge/Vercel son permanentes y gratuitas. | Puedes actualizar la simulación corriendo el `.bat` en cualquier momento. |
| **¿El cliente necesita instalar algo?** | No. | El cliente solo da clic al enlace web desde su celular o computadora. |

---
*Última actualización de guía: 2026-07-26*
