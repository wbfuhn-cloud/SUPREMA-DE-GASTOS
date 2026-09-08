# SISTEMA DE DISEÑO FLUX ARCHIVO (TEMA.MD)
> **Especificación Técnica de UI, Paleta de Colores, Tokens de Diseño y Componentes**  
> *Documento maestro para recrear, extender o mantener con absoluta fidelidad la interfaz gráfica en cualquier LLM, framework o desarrollo frontend.*

---

## 1. Manifiesto y Filosofía Visual

La interfaz de **FLUX Archivo** está inspirada en los estándares de aplicaciones web profesionales modernas de alto rendimiento (*Linear, Immich, Vercel Dashboard, macOS Liquid Glass*):

1. **Dark-First con Soporte Dual:** El modo predeterminado es un tema oscuro profundo y frío (*Deep Slate & Navy*), con soporte para alternar a modo claro cristalino mediante el atributo `data-theme="light"` en `:root`.
2. **Glassmorphism Funcional:** Uso intensivo de `backdrop-filter: blur(...)` y capas translúcidas con bordes ultradelgados semi-transparentes (`hsla(0, 0%, 100%, 0.08)`), generando profundidad espacial sin ruido visual.
3. **Micro-interacciones Elásticas (*Spring Physics*):** Toda interacción, hover, modal o toast responde con curvas de desaceleración elástica (`cubic-bezier(0.34, 1.56, 0.64, 1)`).
4. **Cero Emojis en la UI Corporativa:** Todo elemento visual, de estado o acción utiliza **iconos SVG vectoriales limpios** (estilo *Lucide / Feather Icons*) con grosor de trazo uniforme (`stroke-width: 1.75px` o `2px`).
5. **Retroalimentación Luminosa (*Glows & Halos*):** Elementos activos, en foco o estados críticos utilizan halos suaves (`--primary-glow`, sombras `box-shadow` difusas con color de acento) para guiar la atención del usuario.

---

## 2. Paleta de Colores & Tokens CSS (`:root`)

### 2.1. Tokens en Modo Oscuro (Dark Mode - Por Defecto)

```css
:root {
  /* ── FONDOS Y SUPERFICIES (SURFACES) ── */
  --bg-main: hsl(222, 22%, 8%);              /* #0f131a — Lienzo general profundo */
  --bg-surface: hsla(222, 20%, 12%, 0.35);   /* Superficie translúcida de tarjetas */
  --bg-surface-hover: hsla(222, 20%, 16%, 0.55); /* Hover en tarjetas y filas */
  --bg-glass: hsla(222, 20%, 12%, 0.5);      /* Paneles de navegación, topbar, modales */

  /* ── BORDES Y SEPARADORES ── */
  --border-subtle: hsla(0, 0%, 100%, 0.08);  /* Borde fino blanco con baja opacidad */
  --border-focus: hsla(217, 91%, 60%, 0.5);  /* Anillo de enfoque de inputs */

  /* ── COLOR PRIMARIO / ACENTO (AZUL ELÉCTRICO / COBALTO) ── */
  --primary: hsl(217, 91%, 60%);             /* #3b82f6 — Botones principales, selección */
  --primary-hover: hsl(217, 91%, 65%);       /* #60a5fa — Hover primario */
  --primary-glow: hsla(217, 91%, 60%, 0.2);  /* Resplandor y halo luminoso */

  /* ── JERARQUÍA DE TEXTO ── */
  --text-main: hsl(0, 0%, 95%);              /* #f2f2f2 — Títulos y texto de alto contraste */
  --text-muted: hsl(220, 10%, 75%);          /* #b5bac4 — Subtítulos, labels, metadatos */
  --text-dim: hsl(220, 10%, 55%);            /* #828a99 — Badges inactivos, timestamps */

  /* ── COLORES SEMÁNTICOS (FEEDBACK) ── */
  --success: hsl(150, 70%, 40%);             /* #1fb366 — Canónico, éxito, aprobado */
  --success-bg: hsla(150, 70%, 40%, 0.1);    /* Fondo de badge de éxito */
  
  --warning: hsl(40, 90%, 50%);              /* #f29f0d — Enviado, pendiente, revisión */
  --warning-bg: hsla(40, 90%, 50%, 0.1);     /* Fondo de badge de advertencia */

  --danger: hsl(350, 80%, 55%);              /* #e83150 — Rechazado, eliminar, error */
  --danger-bg: hsla(350, 80%, 55%, 0.1);     /* Fondo de badge de error */

  /* ── RADIOS Y CURVATURAS ── */
  --radius-xl: 20px;
  --radius-lg: 16px;
  --radius-md: 12px;
  --radius-sm: 8px;

  /* ── TRANSICIONES Y FÍSICA ── */
  --transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  --spring: cubic-bezier(0.34, 1.56, 0.64, 1);

  /* ── DIMENSIONES DE LAYOUT ── */
  --sidebar-width: 260px;
  --topbar-height: 64px;
}
```

### 2.2. Tokens en Modo Claro (`data-theme="light"`)

```css
:root[data-theme="light"] {
  --bg-main: hsl(220, 20%, 97%);             /* #f5f7fa — Lienzo claro y limpio */
  --bg-surface: hsla(0, 0%, 100%, 0.5);      /* Blanco lechoso translúcido */
  --bg-surface-hover: hsla(0, 0%, 100%, 0.8);
  --bg-glass: hsla(0, 0%, 100%, 0.6);
  --border-subtle: hsla(0, 0%, 100%, 0.6);

  --primary: hsl(215, 100%, 40%);            /* #0055cc — Azul cobalto de alto contraste */
  --primary-hover: hsl(215, 100%, 35%);
  --primary-glow: hsla(215, 100%, 40%, 0.15);

  --text-main: hsl(220, 20%, 20%);           /* Gris carbón oscuro para legibilidad */
  --text-muted: hsl(220, 10%, 40%);
  --text-dim: hsl(220, 10%, 60%);

  --success: hsl(150, 80%, 30%);
  --success-bg: hsla(150, 80%, 30%, 0.1);
  --warning: hsl(40, 100%, 40%);
  --warning-bg: hsla(40, 100%, 40%, 0.1);
  --danger: hsl(350, 80%, 45%);
  --danger-bg: hsla(350, 80%, 45%, 0.1);
}
```

---

## 3. Fondos Multicapa con Gradientes Radiales Fijos

El fondo característico no es plano: utiliza tres gradientes radiales colocados en la parte superior para dar un efecto de iluminación ambiental cósmica y fija:

```css
/* Modo Oscuro */
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: var(--bg-main);
  background-image: 
    radial-gradient(at 0% 0%, hsla(253, 16%, 7%, 1) 0, transparent 50%),
    radial-gradient(at 50% 0%, hsla(225, 39%, 30%, 0.4) 0, transparent 50%),
    radial-gradient(at 100% 0%, hsla(339, 49%, 30%, 0.4) 0, transparent 50%);
  background-attachment: fixed;
  color: var(--text-main);
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
  min-height: 100vh;
}

/* Modo Claro */
:root[data-theme="light"] body {
  background-image: 
    radial-gradient(at 0% 0%, hsla(253, 100%, 97%, 1) 0, transparent 50%),
    radial-gradient(at 50% 0%, hsla(225, 100%, 90%, 0.6) 0, transparent 50%),
    radial-gradient(at 100% 0%, hsla(339, 100%, 90%, 0.6) 0, transparent 50%);
}
```

---

## 4. Tipografía y Jerarquía

* **Fuente Principal:** `'Inter', sans-serif` (vía Google Fonts: `wght@300;400;500;600;700;800`).
* **Reglas de Jerarquía:**
  * **H1 / Display:** `2.0rem – 3.0rem`, `font-weight: 800`, `letter-spacing: -0.03em`, `line-height: 1.1`.
  * **H2 / Títulos de Módulo:** `1.4rem – 1.8rem`, `font-weight: 700`.
  * **H3 / Títulos de Card o Modal:** `1.05rem – 1.15rem`, `font-weight: 600 – 700`.
  * **Body / Texto General:** `0.9rem – 0.95rem`, `font-weight: 400 – 500`, `line-height: 1.5`.
  * **Kickers / Pre-títulos:** `0.68rem – 0.75rem`, `font-weight: 800`, `text-transform: uppercase`, `letter-spacing: 0.08em – 0.16em`.
  * **Metadatos y Badges:** `0.72rem – 0.8rem`, `font-weight: 600`.

---

## 5. Animaciones & Dinámica (Keyframes)

```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideInRight {
  from { opacity: 0; transform: translateX(100%); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes popIn {
  0%   { opacity: 0; transform: scale(0.95); }
  100% { opacity: 1; transform: scale(1); }
}

@keyframes shimmer {
  0%   { background-position: -1000px 0; }
  100% { background-position: 1000px 0; }
}

/* Skeleton Loading */
.skeleton {
  background: linear-gradient(90deg, var(--bg-surface) 25%, var(--bg-surface-hover) 50%, var(--bg-surface) 75%);
  background-size: 1000px 100%;
  animation: shimmer 2s infinite linear;
  border-radius: var(--radius-sm);
}
```

---

## 6. Arquitectura del Layout (Shell de la Aplicación)

```text
┌────────────────────────────────────────────────────────────────────────┐
│  .app-layout (100vh, flex, overflow: hidden)                          │
├──────────────────┬─────────────────────────────────────────────────────┤
│ .sidebar-modern  │ .main-area (flex-col, 1fr)                          │
│ (width: 260px)   ├─────────────────────────────────────────────────────┤
│ • .sidebar-brand │ .topbar-modern (height: 64px, blur: 16px)           │
│ • .sidebar-nav   │ • .breadcrumb                                       │
│   (menu items)   │ • .search-bar (centrada, píldora con dropdown)      │
│ • .sidebar-user  │ • .topbar-actions (indicador NAS, theme, logout)    │
│                  ├─────────────────────────────────────────────────────┤
│                  │ .page-content (padding: 32px, scroll independiente) │
│                  │   [Vistas dinámicas, Grids, Modales, Tableros]      │
└──────────────────┴─────────────────────────────────────────────────────┘
```

### 6.1. Estilos Clave del Shell

```css
.app-layout {
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.sidebar-modern {
  width: var(--sidebar-width);
  background-color: var(--bg-glass);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  z-index: 50;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-size: 0.95rem;
  font-weight: 500;
  transition: var(--transition);
  cursor: pointer;
  text-decoration: none;
}
.menu-item:hover, .menu-item.active {
  background-color: var(--primary-glow);
  color: var(--primary);
}

.topbar-modern {
  height: var(--topbar-height);
  background-color: var(--bg-glass);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 40;
}

.page-content {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
}
```

---

## 7. Catálogo Visual de Componentes

### 7.1. Botones (`.primary-btn`, `.secondary-btn`, `.danger-btn`, `.icon-btn`)

```html
<!-- Primario -->
<button class="primary-btn">
  <svg width="18" height="18" ...></svg>
  <span>Guardar Cambios</span>
</button>

<!-- Secundario / Outline Glass -->
<button class="secondary-btn">Cancelar</button>

<!-- Peligro -->
<button class="danger-btn">Eliminar</button>

<!-- Botón de Icono Redondo (Topbar / Acciones) -->
<button class="icon-btn" title="Configurar">
  <svg width="20" height="20" ...></svg>
</button>
```

```css
.btn, .primary-btn, .secondary-btn, .danger-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  font-family: inherit;
  transition: var(--transition);
  white-space: nowrap;
}

.primary-btn {
  background: var(--primary);
  color: #ffffff;
}
.primary-btn:hover {
  background: var(--primary-hover);
  box-shadow: 0 4px 14px var(--primary-glow);
}

.secondary-btn {
  background: var(--bg-surface-hover);
  color: var(--text-main);
  border: 1px solid var(--border-subtle);
}
.secondary-btn:hover {
  background: var(--border-subtle);
}

.danger-btn {
  background: var(--danger-bg);
  color: var(--danger);
  border: 1px solid rgba(239, 68, 68, 0.2);
}
.danger-btn:hover {
  background: var(--danger);
  color: #ffffff;
}

.icon-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  transition: var(--transition);
}
.icon-btn:hover {
  background-color: var(--bg-surface);
  color: var(--text-main);
}
```

---

### 7.2. Tarjetas de Explorador y Archivos (Inspiración Immich)

```html
<!-- Card de Carpeta / Proyecto -->
<div class="folder-card">
  <div class="folder-icon">
    <!-- SVG de Carpeta -->
  </div>
  <div class="folder-info">
    <div class="folder-name">Hospital General Torre A</div>
    <div class="folder-meta">2026 • 142 activos</div>
  </div>
</div>

<!-- Card de Archivo con Preview -->
<div class="file-card">
  <div class="file-preview">
    <img src="/thumb.jpg" alt="Preview">
  </div>
  <div class="file-info">
    <div class="file-name">Plano_Estructural_RevB.dwg</div>
    <div class="file-meta">
      <span>12.4 MB</span>
      <span class="badge badge-canonico">Canónico</span>
    </div>
  </div>
</div>
```

```css
.grid-explorer {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}

.folder-card, .file-card {
  background-color: var(--bg-surface);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 16px;
  cursor: pointer;
  transition: var(--transition);
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

.folder-card:hover, .file-card:hover {
  border-color: var(--primary);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  background-color: var(--bg-surface-hover);
}

/* Carpeta en Estado "Propuesta / Pendiente" (Ámbar) */
.folder-card-propuesta {
  border-color: rgba(245, 158, 11, 0.55);
  background: linear-gradient(145deg, var(--bg-surface), rgba(245, 158, 11, 0.08));
}
.folder-card-propuesta:hover {
  border-color: #f59e0b;
}

/* Carpeta no revisada / urgente (Borde Rojo Neón) */
.folder-card-unreviewed {
  border: 2px solid #ef4444 !important;
  box-shadow: 0 0 16px rgba(239, 68, 68, 0.35) !important;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), var(--bg-surface)) !important;
}
```

---

### 7.3. Badges y Chips de Estado

```html
<span class="badge badge-canonico">Canónico</span>
<span class="badge badge-enviado">Enviado</span>
<span class="badge badge-rechazado">Rechazado</span>
<span class="badge badge-neutral">Borrador</span>

<!-- Status Dot con Resplandor Neón (Sin emojis) -->
<div class="status-filter-chip active">
  <span class="status-dot status-dot-canonico"></span>
  <span>Aprobados</span>
</div>
```

```css
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.badge-canonico, .badge-success { background: var(--success-bg); color: var(--success); }
.badge-enviado,  .badge-warning { background: var(--warning-bg); color: var(--warning); }
.badge-rechazado,.badge-danger  { background: var(--danger-bg);  color: var(--danger); }
.badge-neutral                  { background: var(--bg-surface-hover); color: var(--text-muted); border: 1px solid var(--border-subtle); }

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.status-dot-canonico { background: #10b981; box-shadow: 0 0 6px rgba(16, 185, 129, 0.4); }
.status-dot-enviado  { background: #f59e0b; box-shadow: 0 0 6px rgba(245, 158, 11, 0.4); }
.status-dot-rechazado{ background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.4); }
```

---

### 7.4. Formularios e Inputs

```html
<div class="form-group">
  <label for="campo">Nombre del Expediente</label>
  <input type="text" id="campo" class="form-input" placeholder="ej. CIMA-2026-OBRA">
</div>
```

```css
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
}

.form-input {
  background-color: var(--bg-main);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  color: var(--text-main);
  font-family: inherit;
  font-size: 0.9rem;
  width: 100%;
  box-sizing: border-box;
  transition: var(--transition);
}

.form-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-glow);
  background-color: var(--bg-surface-hover);
}

/* Select personalizado sin dropdown nativo tosco */
select.form-input {
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right 12px center;
  background-size: 16px;
  padding-right: 36px;
  cursor: pointer;
}
```

---

### 7.5. Modales Glassmorphism (`.modal-overlay` + `.modal-glass`)

```html
<div class="modal-overlay active" id="modal-root">
  <div class="modal-glass modal-lg">
    <div class="modal-header">
      <h3 class="modal-title">Subir Nueva Versión</h3>
      <button class="modal-close">&times;</button>
    </div>
    <div class="modal-body">
      <!-- Contenido del Modal con scroll estilizado -->
    </div>
    <div class="modal-footer">
      <button class="secondary-btn">Cancelar</button>
      <button class="primary-btn">Aceptar</button>
    </div>
  </div>
</div>
```

```css
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.25s ease;
}
.modal-overlay.active {
  opacity: 1;
  pointer-events: auto;
}

.modal-glass {
  background-color: var(--bg-glass);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.45);
  width: 100%;
  max-width: 520px;
  max-height: calc(100vh - 60px);
  transform: scale(0.96);
  transition: transform 0.25s var(--spring);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.modal-glass.modal-lg { max-width: 760px; }
.modal-glass.modal-xl { max-width: 960px; }
.modal-overlay.active .modal-glass { transform: scale(1); }

.modal-header {
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-surface);
}
.modal-body {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}
.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  background-color: var(--bg-surface);
}
```

---

### 7.6. Sistema de Notificaciones Flotantes (Toasts)

```html
<div class="toast-container" id="toast-root">
  <div class="toast toast-success active">
    <div class="toast-icon">
      <!-- SVG checkCircle -->
    </div>
    <div class="toast-message">Archivo clasificado correctamente</div>
  </div>
</div>
```

```css
.toast-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  z-index: 1500;
  pointer-events: none;
}

.toast {
  background-color: var(--bg-surface);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 14px 20px;
  color: var(--text-main);
  font-weight: 500;
  font-size: 0.9rem;
  box-shadow: 0 8px 24px rgba(0,0,0,0.25);
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  transform: translateX(120%);
  transition: transform 0.3s var(--spring), opacity 0.3s ease;
}
.toast.active { transform: translateX(0); }
.toast.closing { transform: translateX(120%); opacity: 0; }

.toast-success .toast-icon { color: var(--success); }
.toast-error   .toast-icon { color: var(--danger); }
.toast-info    .toast-icon { color: var(--primary); }
```

---

### 7.7. Galería Insignia (Diseño Editorial Arquitectónico)

Utilizada para portadas y entregas destacadas:
* **Cabecera Kicker Editorial:** Gradiente verde azulado petróleo (`linear-gradient(125deg, #102a2b 0%, #164e4a 56%, #0f766e 100%)`).
* **Grid Asimétrico:** La primera imagen tiene clase `.insignia-card-featured` que ocupa `grid-column: span 2; grid-row: span 2;`.
* **Sombra de Fondo:** `linear-gradient(180deg, rgba(2, 6, 23, .03) 30%, rgba(2, 6, 23, .82) 100%)`.
* **Badge de Favorito:** Píldora circular con estrella amarilla y backdrop blur.

---

### 7.8. Barra Flotante de Acciones en Lote (`.bulk-action-bar`)

Cuando el usuario selecciona múltiples activos mediante checkboxes:

```css
.bulk-action-bar {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-glass);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid var(--border-subtle);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5);
  padding: 12px 24px;
  border-radius: 50px;
  display: flex;
  align-items: center;
  gap: 16px;
  z-index: 9999;
  animation: slideUp 0.3s var(--spring);
}
```

---

## 8. Biblioteca Vectorial SVG (Iconos Estilo Lucide)

Todos los iconos deben cumplir con:
* `viewBox="0 0 24 24"`
* `fill="none"`
* `stroke="currentColor"`
* `stroke-width="1.75"` (o `2` en check/x simples)
* `stroke-linecap="round"`
* `stroke-linejoin="round"`

```javascript
const Icons = {
  folder: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.172a2 2 0 0 1 1.414.586l1.828 1.828A2 2 0 0 0 13.828 6H20a2 2 0 0 1 2 2z"></path></svg>`,
  checkCircle: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="9 12 11 14 15 10"></polyline></svg>`,
  xCircle: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`,
  search: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>`
};
```

---

## 9. Prompt de Inyección para otros LLMs / Agentes

> **Copia y pega el siguiente bloque en cualquier otro modelo de IA (Claude, ChatGPT, DeepSeek, etc.) para ordenarle programar vistas con esta misma apariencia:**

```markdown
Actúa como Diseñador y Desarrollador Frontend Senior experto en el Design System "FLUX Liquid Glass".
Debes apegarte ESTRICTAMENTE a las siguientes directrices visuales para cualquier HTML, CSS o componente que generes:

1. ESTILO Y ATMÓSFERA:
   - Tema oscuro por defecto (Dark-first, fondo #0f131a con gradientes radiales superiores).
   - Glassmorphism: Usa 'backdrop-filter: blur(16px)' y fondos semitransparentes 'hsla(222, 20%, 12%, 0.35)'.
   - Bordes: '1px solid hsla(0, 0%, 100%, 0.08)'.
   - Acento primario: Azul eléctrico 'hsl(217, 91%, 60%)' (#3b82f6) con halos luminosos 'hsla(217, 91%, 60%, 0.2)'.

2. REGLAS ESTRICTAS DE UI:
   - PROHIBIDO USAR EMOJIS en la interfaz. Utiliza únicamente iconos SVG vectoriales estilo Lucide/Feather con viewBox="0 0 24 24" y stroke-width="1.75".
   - Tipografía: 'Inter', sans-serif. Títulos nítidos, kickers en mayúsculas pequeñas (0.7rem, letter-spacing: 0.1em).
   - Micro-animaciones: Curvas elásticas 'cubic-bezier(0.34, 1.56, 0.64, 1)'.
   - Botones: .primary-btn (fondo azul, texto blanco), .secondary-btn (glass hover), .icon-btn (circular 36px).
   - Badges: Píldoras con fondo al 10% de opacidad y texto saturado (.badge-canonico verde #10b981, .badge-enviado ámbar #f59e0b, .badge-rechazado rojo #ef4444).
   - Inputs: .form-input con focus ring brillante de 3px difuso.

Genera el código con la máxima elegancia, minimalismo y pulcritud corporativa.
```
