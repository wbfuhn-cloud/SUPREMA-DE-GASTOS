import os
import re

# 1. Fix undefined variables in python files
app_py_path = r"c:\Users\i7 RTX\Desktop\SUPREMA DE GASTOS\src\app.py"
with open(app_py_path, 'r', encoding='utf-8') as f:
    app_py = f.read()
# Replace `print(f"Error procesando estado inicial de cuenta: {e}")`
# if it's in an except block without `as e`:
app_py = re.sub(r'except Exception:\s*print\([^)]*\{e\}[^)]*\)', 'except Exception as e:\n                print(f"Error procesando estado inicial de cuenta: {e}")', app_py)
# Alternative, just remove the `{e}` if `except Exception:` is used
app_py = app_py.replace('print(f"Error leyendo configuracion inicial: {e}")', 'print("Error leyendo configuracion inicial")')
app_py = app_py.replace('except Exception:\n                print(f"Error procesando estado inicial de cuenta: {e}")', 'except Exception as e:\n                print(f"Error procesando estado inicial de cuenta: {e}")')

with open(app_py_path, 'w', encoding='utf-8') as f:
    f.write(app_py)

config_manager_path = r"c:\Users\i7 RTX\Desktop\SUPREMA DE GASTOS\tools\NOTIFICADOR_BOT\config_manager.py"
with open(config_manager_path, 'r', encoding='utf-8') as f:
    config_py = f.read()
config_py = config_py.replace('logger.error', 'print')
with open(config_manager_path, 'w', encoding='utf-8') as f:
    f.write(config_py)


# 2. Fix the name "FLUX Archivo" to "Gastos Raccoon"
# 3. Fix the theme toggle in all templates
templates_dir = r"c:\Users\i7 RTX\Desktop\SUPREMA DE GASTOS\src\templates"
for t in ['dashboard.html', 'transactions.html', 'details.html']:
    p = os.path.join(templates_dir, t)
    with open(p, 'r', encoding='utf-8') as f:
        html = f.read()
    
    html = html.replace('<span>FLUX Archivo</span>', '<span>Gastos Raccoon</span>')
    html = html.replace('ASISTENTE FINANCIERO', 'Gastos Raccoon')
    html = html.replace('ASISTENTE FINANCIERO | Financial Clarity', 'Gastos Raccoon')

    # Fix updateThemeIcon
    bad_theme_func = r'function updateThemeIcon\(theme\) {.*?btn\.innerHTML = .*?;.*?}'
    good_theme_func = """function updateThemeIcon(theme) {
            const btn = document.getElementById('theme-btn');
            if(btn) {
                const icon = theme === 'dark' ? 'sun' : 'moon';
                btn.innerHTML = `<i data-lucide="${icon}"></i>`;
                if(window.lucide) { lucide.createIcons(); }
            }
        }"""
    html = re.sub(bad_theme_func, good_theme_func, html, flags=re.DOTALL)
    
    # Check if there's any toggleTheme missing setting the attribute
    html = html.replace("html.classList.add('dark');", "html.classList.add('dark'); html.setAttribute('data-theme', 'dark');")
    html = html.replace("html.classList.add('light');", "html.classList.add('light'); html.setAttribute('data-theme', 'light');")

    with open(p, 'w', encoding='utf-8') as f:
        f.write(html)

# Fix app.js for /bolsa
app_js_path = r"c:\Users\i7 RTX\Desktop\SUPREMA DE GASTOS\tools\NOTIFICADOR_BOT\app.js"
with open(app_js_path, 'r', encoding='utf-8') as f:
    app_js = f.read()

# toggleTheme in app.js
bad_toggle = r"btn\.innerHTML = theme === 'dark' \? '<i data-lucide=\"sun\"></i>' : '<i data-lucide=\"moon\"></i>';"
good_toggle = "btn.innerHTML = theme === 'dark' ? '<i data-lucide=\"sun\"></i>' : '<i data-lucide=\"moon\"></i>';\n        if(window.lucide) { lucide.createIcons(); }"
app_js = app_js.replace(bad_toggle, good_toggle)
app_js = app_js.replace("html.classList.add('dark');", "html.classList.add('dark'); html.setAttribute('data-theme', 'dark');")
app_js = app_js.replace("html.classList.add('light');", "html.classList.add('light'); html.setAttribute('data-theme', 'light');")

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(app_js)

# Fix index.html in /bolsa (FLUX Archivo -> Gastos Raccoon)
bolsa_html_path = r"c:\Users\i7 RTX\Desktop\SUPREMA DE GASTOS\tools\NOTIFICADOR_BOT\index.html"
with open(bolsa_html_path, 'r', encoding='utf-8') as f:
    bolsa_html = f.read()
bolsa_html = bolsa_html.replace('<span>FLUX Archivo</span>', '<span>Gastos Raccoon</span>')
with open(bolsa_html_path, 'w', encoding='utf-8') as f:
    f.write(bolsa_html)

print("Fixes aplicados correctamente.")
