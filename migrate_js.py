import os
import re

def migrate_js():
    filepath = r"c:\Users\i7 RTX\Desktop\SUPREMA DE GASTOS\tools\NOTIFICADOR_BOT\app.js"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Map for FontAwesome to Lucide
    content = re.sub(r'<i class="fa-solid fa-check"></i>', '<i data-lucide="check"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-spinner fa-spin"></i>', '<i data-lucide="loader" class="lucide-spin"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-bolt"></i>', '<i data-lucide="zap"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-triangle-exclamation"></i>', '<i data-lucide="alert-triangle"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-thumbs-down"></i>', '<i data-lucide="thumbs-down"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-sun".*?></i>', '<i data-lucide="sun"></i>', content)
    content = re.sub(r'<i class="fa-solid fa-moon".*?></i>', '<i data-lucide="moon"></i>', content)
    
    # Also find any other fa-solid and convert dynamically if possible
    def replace_fa(match):
        fa_class = match.group(1)
        if 'fa-spinner' in fa_class:
            return '<i data-lucide="loader" class="lucide-spin"></i>'
        elif 'fa-play' in fa_class:
            return '<i data-lucide="play"></i>'
        elif 'fa-stop' in fa_class:
            return '<i data-lucide="square"></i>'
        elif 'fa-gear' in fa_class:
            return '<i data-lucide="settings"></i>'
        elif 'fa-arrow-up' in fa_class:
            return '<i data-lucide="arrow-up"></i>'
        elif 'fa-arrow-down' in fa_class:
            return '<i data-lucide="arrow-down"></i>'
        else:
            return match.group(0) # fallback
            
    content = re.sub(r'<i class="fa-solid (.*?)"></i>', replace_fa, content)

    # We need to call lucide.createIcons() after innerHTML assignments.
    # To do this safely, we can just replace common function ends with the call, but JS functions can be tricky.
    # We can inject a mutation observer at the top of app.js to auto-run lucide on DOM changes!
    
    observer_code = """
// Auto-initialize Lucide Icons on DOM changes
const observer = new MutationObserver((mutations) => {
    let shouldUpdate = false;
    for (let mutation of mutations) {
        if (mutation.addedNodes.length) {
            shouldUpdate = true;
            break;
        }
    }
    if (shouldUpdate && window.lucide) {
        lucide.createIcons();
    }
});
observer.observe(document.body, { childList: true, subtree: true });

"""
    if 'MutationObserver' not in content:
        content = observer_code + content

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print("app.js migrado.")

migrate_js()
