# 🚀 MonitorBaz Digital | Financial Clarity Design Blueprint

Este documento contiene las especificaciones técnicas y visuales del sistema de diseño desarrollado para el ecosistema **Suprema de Gastos**. Este diseño está optimizado para aplicaciones financieras que requieren alta legibilidad, estética premium y una experiencia de usuario fluida tanto en escritorio como en móvil.

## 🎨 Identidad Visual (Financial Clarity)

El concepto se basa en la transparencia y la profundidad, utilizando el efecto **Glassmorphism** (cristalería digital).

### Paleta de Colores
*   **Primary Purple**: `#5631E8` (Botones, acentos, énfasis).
*   **Deep Dark Background**: `#020617` (Fondo maestro del modo oscuro).
*   **Light Background**: `#F7F9FB` (Gris azulado muy suave para modo claro).
*   **Glass Card (Light)**: `rgba(255, 255, 255, 0.9)` con blur de `12px`.
*   **Glass Card (Dark)**: `rgba(15, 23, 42, 0.8)` con blur de `12px`.

---

## 🛠 Arquitectura de Código "Zero-Errors"

Para evitar que los editores de Python (como VS Code o Cursor) marquen errores falsos en el código JavaScript/CSS embebido, se utiliza el **Blindaje de Texto Plano**.

### Estructura Recomendada:
1.  **Constantes Externas**: Define el CSS y JS en constantes de clase usando `r"""` (raw strings).
2.  **Plantilla con Placeholders**: Usa una plantilla HTML pura sin `f-strings` para el bloque grande.
3.  **Ensamblaje Manual**: Usa `.replace("[[TAG]]", contenido)` para inyectar los datos.

```python
class Generator:
    CSS = r\"\"\" .clase { ... } \"\"\"
    JS = r\"\"\" function() { ... } \"\"\"
    TEMPLATE = r\"\"\" ... <style>[[CSS]]</style> ... \"\"\"

    @staticmethod
    def generate(data):
        html = Generator.TEMPLATE
        return html.replace("[[CSS]]", Generator.CSS).replace("[[ROWS]]", rows)
```

---

## 📱 Diseño Responsivo Inteligente (Table-to-Cards)

Uno de los puntos fuertes de MonitorBaz Digital es su capacidad de transformar tablas complejas en tarjetas legibles en dispositivos móviles.

### El Truco CSS (Media Queries):
Se oculta el `thead` y se redefine el `tr` como un contenedor de tipo `grid`.

```css
@media (max-width: 768px) {
    table thead { display: none; }
    table, tbody, tr, td { display: block; width: 100%; }
    tr {
        display: grid;
        grid-template-areas: 
            "header amount"
            "content content"
            "footer footer";
        grid-template-columns: 1fr auto;
        gap: 0.75rem;
        border-radius: 1.5rem;
        padding: 1.25rem;
    }
}
```

---

## ⚡ Lógica Dinámica "No-Reload"

Para una sensación de aplicación moderna, se implementa edición en tiempo real sin recargar la página.

*   **Auto-Save**: Uso de `onchange` para disparar peticiones `fetch` asíncronas.
*   **Instant Formatting**: Funciones JS como `formatDateJS` que formatean la fecha visualmente al momento de elegirla en el `input`.
*   **Toasts**: Notificaciones sutiles de "Guardado" que aparecen y desaparecen con transformaciones CSS fluidas.

---

## 💎 Tips Premium
1.  **Tipografía**: Usar siempre `Inter` para el cuerpo y `Hanken Grotesk` o similar para los títulos.
2.  **Iconografía**: `Material Symbols Outlined` con variaciones de peso (`wght` 400).
3.  **Micro-interacciones**: Añadir `hover:scale-105` y `transition-all` a todos los botones y tarjetas para que la interfaz se sienta "viva".

---
*Guardado por Antigravity para futuros proyectos de MonitorBaz Digital.*
