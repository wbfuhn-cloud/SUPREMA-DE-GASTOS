# 📱 Guía de Optimización: Columnas de Transacciones para Móvil

Esta guía detalla los pasos para transformar una tabla de transacciones densa en una experiencia móvil fluida, optimizada y de alto impacto visual.

---

## 🎯 El Desafío
En pantallas pequeñas, una tabla con 12 columnas (como la actual) genera un "desbordamiento horizontal" que dificulta la lectura. La solución no es solo ocultar columnas, sino **reorganizar la información** de manera inteligente.

---

## 🚀 Pasos para la Optimización Suprema

### 1. Estrategia de "Información Apilada" (Stacked Info)
En lugar de una columna por cada dato, agrupamos información relacionada en una sola celda móvil.

**Ejemplo:**
- **Celda 1:** Fecha (pequeña) + Flujo (etiqueta).
- **Celda 2:** Unidad + Proveedor (en negrita) + Categoría (subtexto gris).
- **Celda 3:** Monto (grande y destacado).

### 2. Implementación Técnica (CSS & HTML)

#### Paso A: Definir el Layout de "Card" en Móvil
Modifica el CSS para que cada fila (`<tr>`) se comporte como un contenedor flexible en lugar de una fila rígida.

```css
@media (max-width: 768px) {
    /* Convertimos la tabla en un layout más flexible */
    #transactions-table thead {
        display: none; /* Ocultamos cabeceras tradicionales */
    }

    #transactions-table tr {
        display: grid;
        grid-template-areas: 
            "fecha monto"
            "info monto";
        grid-template-columns: 1fr auto;
        padding: 15px;
        border-bottom: 2px solid var(--border-color);
        gap: 5px;
    }
}
```

#### Paso B: Agrupar Elementos en el HTML
En `src/transactions_view.py`, ajusta la generación de celdas para incluir clases de visibilidad.

```python
# Pseudo-código del cambio sugerido en la fila:
f'''
<tr ...>
    <td class="mobile-info-main">
        <div class="date-badge">{short_date}</div>
        <div class="merchant-name">{val_merchant}</div>
        <div class="category-tag">{e.get('category')}</div>
    </td>
    <td class="mobile-amount-cell">
        <div class="total-value">${e.get('total')}</div>
    </td>
</tr>
'''
```

### 3. Optimización de Micro-Interacciones
- **Click en Fila:** Mantener la apertura del **Modal de Detalle** (ya implementado). Esto permite que la fila principal sea "limpia" y los cambios profundos se hagan en el popup.
- **Feedback Visual:** Añadir un efecto de `glassmorphism` o sombras sutiles al tocar una fila para mejorar la sensación de "app nativa".

---

## 🎨 Diseño Visual Premium (Tips)

1.  **Tipografía Dinámica:** Usa `font-size: 0.8rem` para metadatos (categoría, fecha) y `1rem` para el comercio.
2.  **Contrastes de Color:** El monto debe tener un color sólido (ej. `#6366F1`) para que el usuario identifique el gasto al instante.
3.  **Espaciado (Padding):** No escatimes en espacio. En móvil, el "aire" entre elementos evita errores de click y mejora la legibilidad.

---

## ✅ Resumen de Columnas Críticas para Móvil

| Prioridad | Dato | Visualización en Móvil |
| :--- | :--- | :--- |
| **Alta** | Fecha | Formato DD/MM/YY (Compacto) |
| **Alta** | Comercio / Unidad | Título Principal |
| **Alta** | Monto | Destacado a la derecha |
| **Media** | Categoría | Subtexto bajo el Comercio |
| **Baja** | ID / Método | Oculto (Ver solo en Modal) |

---
> [!TIP]
> **ProTip:** Implementar un esqueleto de carga (skeleton screen) mientras se filtran los datos mejora drásticamente la percepción de velocidad en dispositivos móviles.
