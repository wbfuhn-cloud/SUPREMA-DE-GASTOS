import os
import re

def migrate_html_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Replace the <style> block and add flux_theme
    # Find the start of <style> and end of </style>
    style_pattern = re.compile(r'<style>.*?</style>', re.DOTALL)
    
    # We also want to include lucide script
    head_additions = """
    <link rel="stylesheet" href="/static/flux_theme.css">
    <script src="https://unpkg.com/lucide@latest"></script>
"""
    content = style_pattern.sub(head_additions, content)

    # 2. Add lucide.createIcons() before </body>
    if 'lucide.createIcons()' not in content:
        content = content.replace('</body>', '    <script>lucide.createIcons();</script>\n</body>')

    # 3. Replace the navigation with Sidebar + Topbar Layout
    nav_pattern = re.compile(r'<!-- Header Unified Nav GBM Style -->\s*<nav class="unified-nav">.*?</nav>', re.DOTALL)
    
    sidebar_html = """
<div class="app-layout">
    <div class="sidebar-modern">
        <div class="sidebar-brand">
            <i data-lucide="wallet" style="color: var(--primary);"></i>
            <span>FLUX Archivo</span>
        </div>
        <div class="sidebar-nav">
            <a href="/dashboard" class="menu-item"><i data-lucide="layout-grid"></i> Dashboard</a>
            <a href="/transactions" class="menu-item"><i data-lucide="receipt"></i> Transacciones</a>
            <a href="/details" class="menu-item"><i data-lucide="activity"></i> Analíticos</a>
            <a href="/bolsa" class="menu-item"><i data-lucide="trending-up"></i> Inversiones IA</a>
        </div>
    </div>
    <div class="main-area">
        <div class="topbar-modern">
            <div class="breadcrumb text-sm font-semibold text-slate-400">Plataforma / Resumen</div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <button onclick="sendDashboardToTelegram()" class="icon-btn" title="Enviar a Telegram">
                    <i data-lucide="send"></i>
                </button>
                <button id="theme-btn" onclick="toggleTheme()" class="icon-btn" title="Cambiar Tema">
                    <i data-lucide="moon"></i>
                </button>
            </div>
        </div>
        <div class="page-content">
"""
    content = nav_pattern.sub(sidebar_html, content)

    # 4. Replace <main class="..."> with just a div, because page-content is already wrapping it.
    # Actually, we can just remove the <main> tag and its closing tag, or change <main ...> to <div class="max-w-[1400px] mx-auto w-full">
    main_start = re.compile(r'<main[^>]*>')
    content = main_start.sub(r'<div class="max-w-[1400px] mx-auto w-full">', content)
    
    # 5. Close the app-layout divs at the end of the body
    # We replace </main> with </div> </div> </div> (closing main container, page-content, main-area, app-layout)
    content = content.replace('</main>', '</div>\n        </div>\n    </div>\n</div>')

    # 6. Map Material Symbols to Lucide
    icon_map = {
        'account_balance_wallet': 'wallet',
        'send': 'send',
        'light_mode': 'sun',
        'dark_mode': 'moon',
        'trending_up': 'trending-up',
        'event': 'calendar',
        'payments': 'banknote',
        'outbox': 'upload',
        'stars': 'star',
        'warning': 'alert-triangle',
        'sync': 'refresh-cw',
        'add_circle': 'plus-circle',
        'grid_view': 'layout-grid',
        'receipt_long': 'receipt',
        'monitoring': 'activity',
        'close': 'x',
        'chevron_right': 'chevron-right'
    }

    def icon_replacer(match):
        icon_text = match.group(1).strip()
        lucide_icon = icon_map.get(icon_text, 'circle')
        return f'<i data-lucide="{lucide_icon}" class="w-5 h-5"></i>'

    # Pattern for <span class="material-symbols-outlined...">icon_name</span>
    content = re.sub(r'<span[^>]*material-symbols-outlined[^>]*>(.*?)</span>', icon_replacer, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

base_dir = r"c:\Users\i7 RTX\Desktop\SUPREMA DE GASTOS\src\templates"
for file in ['dashboard.html', 'transactions.html', 'details.html']:
    migrate_html_file(os.path.join(base_dir, file))
print("Migración completada.")
