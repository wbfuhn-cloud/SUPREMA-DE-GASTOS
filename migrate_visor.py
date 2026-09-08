import os
import re

def migrate_visor():
    filepath = r"c:\Users\i7 RTX\Desktop\SUPREMA DE GASTOS\tools\NOTIFICADOR_BOT\index.html"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add flux_theme.css and lucide to head
    head_add = """
    <link rel="stylesheet" href="/static/flux_theme.css">
    <link rel="stylesheet" href="/visor/style.css">
    <script src="https://unpkg.com/lucide@latest"></script>
"""
    # Replace existing style.css link and FontAwesome
    content = re.sub(r'<link rel="stylesheet" href="/visor/style.css">', '', content)
    content = re.sub(r'<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/.*?>', head_add, content)

    # Add lucide init
    if 'lucide.createIcons()' not in content:
        content = content.replace('</body>', '    <script>lucide.createIcons();</script>\n</body>')

    # Replace Nav
    nav_pattern = re.compile(r'<!-- Header Unified Nav GBM Style -->.*?<nav class="unified-nav">.*?</nav>', re.DOTALL)
    
    sidebar_html = """
<div class="app-layout">
    <div class="sidebar-modern">
        <div class="sidebar-brand">
            <i data-lucide="trending-up" style="color: var(--primary);"></i>
            <span>FLUX Archivo</span>
        </div>
        <div class="sidebar-nav">
            <a href="/dashboard" class="menu-item"><i data-lucide="layout-grid"></i> Dashboard</a>
            <a href="/transactions" class="menu-item"><i data-lucide="receipt"></i> Transacciones</a>
            <a href="/details" class="menu-item"><i data-lucide="activity"></i> Analíticos</a>
            <a href="/bolsa" class="menu-item active"><i data-lucide="trending-up"></i> Inversiones IA</a>
        </div>
    </div>
    <div class="main-area">
        <div class="topbar-modern">
            <div class="breadcrumb text-sm font-semibold text-slate-400">Plataforma / Inversiones IA</div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <button class="icon-btn" title="Cambiar Tema" onclick="document.documentElement.classList.toggle('light')">
                    <i data-lucide="moon"></i>
                </button>
            </div>
        </div>
        <div class="page-content">
"""
    content = nav_pattern.sub(sidebar_html, content)

    # Replace <div class="app-container"> with just the div, because page-content wraps it
    content = content.replace('<div class="app-container">', '<div class="app-container" style="max-width: 1650px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px;">')
    
    # Close the app-layout at the end of the body.
    # The last closing div before scripts is the end of app-container
    content = content.replace('</div>\n\n    <!-- Template Tarjeta GBM -->', '</div>\n        </div>\n    </div>\n</div>\n\n    <!-- Template Tarjeta GBM -->')

    # Convert FontAwesome icons to Lucide in JS and HTML
    # <i class="fa-solid fa-play"></i> -> <i data-lucide="play"></i>
    content = re.sub(r'<i class="fa-solid fa-play"></i>', '<i data-lucide="play"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-stop"></i>', '<i data-lucide="square"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-sync fa-spin"></i>', '<i data-lucide="refresh-cw" class="lucide-spin"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-gear"></i>', '<i data-lucide="settings"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-download"></i>', '<i data-lucide="download"></i>', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print("Visor migrado.")

migrate_visor()
